import yfinance as yf
import pandas as pd
import numpy as np
from google import genai
import feedparser
import urllib.parse
from datetime import datetime
import sys
import io
import time
import os
import re
import warnings
import json

warnings.filterwarnings('ignore')

# --- 1. 環境設定（文字コード・パスの絶対指定） ---
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data_j.csv')
PORTFOLIO_FILE = os.path.join(BASE_DIR, 'virtual_portfolio.csv')
HISTORY_FILE = os.path.join(BASE_DIR, 'trade_history.csv')
ACCOUNT_FILE = os.path.join(BASE_DIR, 'account.json')

# --- 2. AI・トレード設定 ---
GEMINI_API_KEY = "ここにAPIキーを入力"  # 【重要】APIキーを入力してください

if GEMINI_API_KEY == "ここにAPIキーを入力":
    print("⚠️ エラー: GEMINI_API_KEY が設定されていません。コード内の設定箇所にAPIキーを入力してください。")
    sys.exit()

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = "gemini-2.5-flash"

# シミュレーション用設定
INITIAL_CASH = 1000000  
MAX_POSITIONS = 3       
INVEST_PER_TRADE = 300000 
STOP_LOSS_PCT = -0.03   

# トレーリングストップ設定
TRAIL_ACTIVATION_PCT = 0.02  
TRAILING_STOP_PCT = 0.02     

# AI審査の上限数（1時間ごとの実行なら50銘柄まで増やしても1日の無料枠1500回に収まります）
MAX_AI_CANDIDATES = 50

# --- 3. 地合いフィルター ---
def check_market_trend():
    try:
        nk = yf.download('^N225', period="2d", interval="15m", threads=False)
        if nk is None or nk.empty: return True 
        close = nk['Close'].dropna()
        if len(close) < 20: return True
        sma20 = float(close.rolling(window=20).mean().iloc[-1])
        current = float(close.iloc[-1])
        return current > sma20
    except Exception:
        return True

# --- 4. 口座・ポートフォリオ管理 ---
def load_account():
    if os.path.exists(ACCOUNT_FILE) and os.path.getsize(ACCOUNT_FILE) > 0:
        try:
            with open(ACCOUNT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError: pass
    return {"cash": INITIAL_CASH}

def save_account(account_data):
    with open(ACCOUNT_FILE, 'w', encoding='utf-8') as f:
        json.dump(account_data, f, indent=4)

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE) and os.path.getsize(PORTFOLIO_FILE) > 0:
        try:
            return pd.read_csv(PORTFOLIO_FILE).to_dict('records')
        except pd.errors.EmptyDataError: return []
    return []

def save_portfolio(portfolio):
    df = pd.DataFrame(portfolio)
    df.to_csv(PORTFOLIO_FILE, index=False, encoding='utf-8-sig')

def log_trade(trade_record):
    write_header = not os.path.exists(HISTORY_FILE) or os.path.getsize(HISTORY_FILE) == 0
    df = pd.DataFrame([trade_record])
    df.to_csv(HISTORY_FILE, mode='a', header=write_header, index=False, encoding='utf-8-sig')

def manage_positions(portfolio, account):
    if not portfolio: return portfolio, account

    print(f"\n--- 💼 保有銘柄の監視 ({len(portfolio)}銘柄) ---")
    tickers = [f"{p['code']}.T" for p in portfolio]
    data = yf.download(tickers, period="1d", interval="15m", group_by='ticker', threads=True)
    if data is None or data.empty: return portfolio, account

    remaining_portfolio = []
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for p in portfolio:
        code = str(p['code'])
        ticker = f"{code}.T"
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if ticker not in data.columns.levels[0]:
                    remaining_portfolio.append(p); continue
                df = data[ticker].dropna()
            else:
                if len(portfolio) == 1 or ticker == data.columns.name: df = data.dropna()
                else: remaining_portfolio.append(p); continue
            
            if df.empty: remaining_portfolio.append(p); continue

            current_price = float(df['Close'].iloc[-1])
            buy_price = float(p['buy_price'])
            highest_price = max(float(p.get('highest_price', buy_price)), current_price)
            p['highest_price'] = highest_price
            
            profit_pct = (current_price - buy_price) / buy_price
            highest_profit_pct = (highest_price - buy_price) / buy_price
            
            print(f"[{code} {p['name']}] 買値: {buy_price:.1f} -> 現在値: {current_price:.1f} (最高値: {highest_price:.1f} | 損益: {profit_pct*100:+.2f}%)")

            sell_reason = None
            if highest_profit_pct >= TRAIL_ACTIVATION_PCT:
                if current_price <= highest_price * (1.0 - TRAILING_STOP_PCT):
                    sell_reason = "トレール利確"
            
            if sell_reason is None and profit_pct <= STOP_LOSS_PCT:
                sell_reason = "損切"

            if sell_reason:
                profit_amount = (current_price - buy_price) * p['shares']
                account['cash'] += current_price * p['shares'] 
                print(f"💰 【決済】{code} {p['name']} を {sell_reason} しました！ 確定損益: {profit_amount:+.0f}円")
                log_trade({
                    "sell_time": current_time, "code": code, "name": p['name'], "buy_time": p['buy_time'],
                    "buy_price": buy_price, "sell_price": current_price, "highest_price_reached": highest_price,
                    "shares": p['shares'], "profit_amount": profit_amount, "profit_pct": profit_pct, "reason": sell_reason
                })
            else: remaining_portfolio.append(p)
        except Exception: remaining_portfolio.append(p)

    return remaining_portfolio, account

# --- 5. データ取得・AI判定関数 ---
def get_recent_news(code, name):
    clean_name = re.sub(r'\s+', ' ', name).strip()
    query = urllib.parse.quote(f"{code} {clean_name}")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        feed = feedparser.parse(rss_url)
        titles = [entry.title for entry in feed.entries[:5]]
        return " | ".join(titles) if titles else "関連ニュースなし"
    except: return "ニュース取得エラー"

def calculate_technicals(df):
    if len(df) < 50: return None
    delta = df['Close'].diff()
    up = delta.clip(lower=0).ewm(span=14, adjust=False).mean()
    down = -1 * delta.clip(upper=0).ewm(span=14, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + up / down))
    df['MACD'] = df['Close'].ewm(span=12, adjust=False).mean() - df['Close'].ewm(span=26, adjust=False).mean()
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['STD20'] = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['SMA20'] + (df['STD20'] * 2)
    df['BB_Lower'] = df['SMA20'] - (df['STD20'] * 2)
    df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['SMA20']
    
    tr1 = df['High'] - df['Low']
    tr2 = abs(df['High'] - df['Close'].shift())
    tr3 = abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(window=14).mean()
    
    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (df['Typical_Price'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    return df

def scan_initial_breakout(df):
    latest = df.iloc[-1]
    vol_mean_5 = df['Volume'].iloc[-6:-1].mean()
    if vol_mean_5 == 0: vol_mean_5 = 1 
    
    vol_surge_ratio = latest['Volume'] / vol_mean_5
    vol_surge = vol_surge_ratio > 3.0
    
    lookback_5d = min(100, len(df)-1)
    break_5d = latest['Close'] > df['High'].iloc[-(lookback_5d+1):-1].max()
    squeeze_condition = df['BB_Width'].iloc[-10:-1].mean() < 0.05
    volatility_expansion = latest['BB_Width'] > df['BB_Width'].iloc[-2]
    
    vwap_condition = latest['Close'] > latest['VWAP']
    upper_shadow = latest['High'] - max(latest['Close'], latest['Open'])
    no_high_wick = upper_shadow < (latest['ATR'] * 0.5)
    
    is_hot = vol_surge and (break_5d or (squeeze_condition and volatility_expansion)) and vwap_condition and no_high_wick
    
    tech_data = {
        "RSI": latest['RSI'],
        "MACD": latest['MACD'],
        "Signal": latest['Signal'],
        "VolSurgeRatio": vol_surge_ratio, 
        "SqueezeBreak": squeeze_condition and volatility_expansion,
        "Breakout": break_5d,
        "CurrentPrice": latest['Close']
    }
    return is_hot, tech_data

def ai_scoring(code, name, tech, news_text, max_retries=3):
    prompt = f"""
    あなたは機関投資家レベルの株価予測AIです。以下の情報から、銘柄の「直近の急騰確率(スコア)」を 1〜100 の数値で評価してください。
    【銘柄】 {name} ({code})
    【テクニカル指標】
    出来高急増倍率: {tech['VolSurgeRatio']:.1f}倍 (資金流入の強さ)
    RSI: {tech['RSI']:.1f}
    MACD/シグナル: {tech['MACD']:.2f} / {tech['Signal']:.2f}
    ボラ・ブレイク: {'発生中' if tech['SqueezeBreak'] else 'なし'}
    【最新ニュース】 {news_text}
    【出力ルール】
    1行目: スコア（例: 88）
    2行目: 判定理由（100文字以内の日本語）
    """
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(model=MODEL_ID, contents=prompt)
            lines = response.text.strip().split('\n')
            score = int(re.sub(r'\D', '', lines[0]))
            reason = lines[1] if len(lines) > 1 else "詳細理由なし"
            return score, reason
        except Exception as e:
            err_msg = str(e).lower()
            if "429" in err_msg or "quota" in err_msg or "rate limit" in err_msg:
                if attempt < max_retries - 1:
                    print(f"  ⚠️ API制限(429)を検知。20秒待機して再試行します... ({attempt+1}/{max_retries})")
                    time.sleep(20)
                    continue
            return 0, f"AI評価エラー: {str(e)[:50]}"
    return 0, "AI評価エラー: 再試行上限到達"

# --- 6. メイン処理 ---
def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚀 東証最強BOT 起動")
    
    account = load_account()
    portfolio = load_portfolio()
    print(f"🏦 現在の口座残高: {account['cash']:,.0f}円")

    portfolio, account = manage_positions(portfolio, account)
    save_portfolio(portfolio)
    save_account(account)

    if len(portfolio) >= MAX_POSITIONS:
        print(f"\n💡 現在最大ポジション数（{MAX_POSITIONS}銘柄）を保有中のため、新規スキャンをスキップします。")
        return

    is_market_good = check_market_trend()
    if not is_market_good:
        print("\n📉 地合いフィルター発動: 日経平均が短期下落トレンドのため、リスク回避として新規エントリーを見送ります。")
        return

    try:
        df_symbols = pd.read_csv(DATA_FILE)
        targets = df_symbols['コード'].astype(str).tolist()
    except Exception as e:
        print(f"⚠️ 銘柄リスト読み込みエラー: {e}")
        return

    holdings = [str(p['code']) for p in portfolio]
    targets = [t for t in targets if t not in holdings]

    hot_candidates = []
    tickers = [f"{code}.T" for code in targets]
    
    print(f"\n--- 15分足データ一括ダウンロード (新規対象: {len(tickers)}銘柄) ---")
    data = yf.download(tickers, period="5d", interval="15m", group_by='ticker', threads=True)
    if data is None or data.empty: return

    for code in targets:
        ticker = f"{code}.T"
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if ticker not in data.columns.levels[0]: continue
                df = data[ticker].dropna()
            else:
                if len(targets) == 1 or ticker == data.columns.name: df = data.dropna()
                else: continue
            
            if df.empty or len(df) < 50: continue
            df = calculate_technicals(df)
            if df is None: continue
            
            is_hot, tech_data = scan_initial_breakout(df)
            if is_hot:
                name_row = df_symbols[df_symbols['コード'].astype(str) == code]
                name = name_row['銘柄名'].values[0] if not name_row.empty else "不明"
                hot_candidates.append({"code": code, "name": name, "tech": tech_data})
        except Exception:
            continue

    if not hot_candidates:
        print("💡 現在の15分足で急騰初動シグナルを満たす新規銘柄はありません。")
        return

    # 出来高急増倍率でソートし、設定した上限数で絞り込む
    hot_candidates = sorted(hot_candidates, key=lambda x: x['tech']['VolSurgeRatio'], reverse=True)
    if len(hot_candidates) > MAX_AI_CANDIDATES:
        print(f"\n⚠️ スクリーニング通過が {len(hot_candidates)}銘柄 と多いため、資金流入(出来高急増率) 上位{MAX_AI_CANDIDATES}銘柄 に絞ってAI審査を行います。")
        hot_candidates = hot_candidates[:MAX_AI_CANDIDATES]
    else:
        print(f"\n💡 スクリーニング通過: {len(hot_candidates)}銘柄")

    print(f"\n--- 🤖 AIスコアリング (審査対象: {len(hot_candidates)}銘柄) ---")
    scored_list = []
    
    for idx, item in enumerate(hot_candidates, 1):
        news = get_recent_news(item['code'], item['name'])
        score, reason = ai_scoring(item['code'], item['name'], item['tech'], news)
        
        item['ai_score'] = score
        item['ai_reason'] = reason
        scored_list.append(item)
        print(f"[{idx}/{len(hot_candidates)}] {item['code']} {item['name']} | 急増: {item['tech']['VolSurgeRatio']:.1f}倍 | スコア: {score}点 | 理由: {reason}")
        
        # API制限回避のための待機（1分あたり15リクエスト以内に抑える）
        time.sleep(4.5)

    scored_list = sorted(scored_list, key=lambda x: x['ai_score'], reverse=True)
    best = scored_list[0]
    
    if best['ai_score'] >= 80:
        buy_price = best['tech']['CurrentPrice']
        budget = min(INVEST_PER_TRADE, account['cash'])
        
        if buy_price * 100 > budget:
            print(f"\n💡 最低購入金額({buy_price * 100:,.0f}円)が現在の投資可能額({budget:,.0f}円)を上回っているため見送ります。")
        else:
            shares_to_buy = max(100, int(budget // (buy_price * 100)) * 100)
            cost = buy_price * shares_to_buy
            
            print(f"\n🏆 【シミュレーション買付発動】最強銘柄確定: {best['code']} {best['name']}")
            print(f"判定理由: {best['ai_reason']}")
            print(f"🛒 買付価格: {buy_price:.1f}円 | 数量: {shares_to_buy}株 | 概算代金: {cost:,.0f}円")
            
            account['cash'] -= cost
            portfolio.append({
                "code": best['code'], "name": best['name'], "buy_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "buy_price": buy_price, "highest_price": buy_price, "shares": shares_to_buy
            })
            save_portfolio(portfolio)
            save_account(account)
    else:
        print("\n💡 エントリー基準(AIスコア80以上)を満たす銘柄はありませんでした。見送ります。")

if __name__ == "__main__":
    main()