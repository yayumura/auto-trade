# --- 0. 環境設定（【重要】他のインポートより先にUTF-8を強制する） ---
import os
import sys
import io

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"  

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# --- ここから通常のインポート ---
import yfinance as yf
import pandas as pd
import numpy as np
from google import genai
from groq import Groq  
import feedparser
import urllib.parse
from datetime import datetime
import time
import re
import warnings
import json
import requests
from dotenv import load_dotenv

warnings.filterwarnings('ignore')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data_j.csv')
PORTFOLIO_FILE = os.path.join(BASE_DIR, 'virtual_portfolio.csv')
HISTORY_FILE = os.path.join(BASE_DIR, 'trade_history.csv')
ACCOUNT_FILE = os.path.join(BASE_DIR, 'account.json')
EXECUTION_LOG_FILE = os.path.join(BASE_DIR, 'execution_log.csv') 

# --- 2. AI・トレード設定 ---
load_dotenv(os.path.join(BASE_DIR, '.env'))

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

if not GEMINI_API_KEY:
    print("⚠️ エラー: GEMINI_API_KEY が設定されていません。.envファイルを確認してください。")
    sys.exit()

gemini_client = genai.Client(api_key=GEMINI_API_KEY)
GEMINI_MODEL = "gemini-2.5-flash"

if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
else:
    groq_client = None

# 🔧 デバッグモード設定
# True にすると、休場日や取引時間外でも強制的にプログラムが実行されます。
# 本番で自動運用する際は False に戻してください。
DEBUG_MODE = True

# シミュレーション用設定
INITIAL_CASH = 1000000  
MAX_POSITIONS = 3       
INVEST_PER_TRADE = 500000 

# 税率設定（特定口座 源泉徴収あり: 20.315%）
TAX_RATE = 0.20315

# 【変更】ATR（ボラティリティ）ベースの動的ストップ設定（大化け株対応の鈍感設定）
ATR_STOP_LOSS_MULTIPLIER = 3.0  # 買値からATRの3倍下がったら損切り（ノイズ許容）
ATR_TRAIL_ACTIVATION = 4.0      # 買値からATRの4倍上がったらトレール利確準備（しっかり利益が乗るまで待つ）
ATR_TRAIL_STOP_MULTIPLIER = 2.0 # 最高値からATRの2倍下がったら利確実行（押し目を許容して波に乗る）

# AI審査の上限数
MAX_AI_CANDIDATES = 50

# --- 通知機能 ---
def send_discord_notify(message):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    except Exception as e:
        print(f"⚠️ Discord通知エラー: {e}")

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
    actions = []
    if not portfolio: return portfolio, account, actions

    print(f"\n--- 💼 保有銘柄の監視 ({len(portfolio)}銘柄) ---")
    tickers = [f"{p['code']}.T" for p in portfolio]
    data = yf.download(tickers, period="5d", interval="15m", group_by='ticker', threads=True)
    if data is None or data.empty: return portfolio, account, actions

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
            
            if df.empty or len(df) < 14: 
                remaining_portfolio.append(p)
                continue

            current_price = float(df['Close'].iloc[-1])
            buy_price = float(p['buy_price'])
            highest_price = max(float(p.get('highest_price', buy_price)), current_price)
            p['highest_price'] = highest_price
            p['current_price'] = current_price
            
            tr1 = df['High'] - df['Low']
            tr2 = abs(df['High'] - df['Close'].shift())
            tr3 = abs(df['Low'] - df['Close'].shift())
            atr = float(pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean().iloc[-1])
            
            if pd.isna(atr) or atr == 0: 
                atr = current_price * 0.02
            
            profit_pct = (current_price - buy_price) / buy_price
            print(f"[{code} {p['name']}] 買値: {buy_price:.1f} -> 現在値: {current_price:.1f} (最高値: {highest_price:.1f} | 損益: {profit_pct*100:+.2f}%)")

            sell_reason = None
            
            if current_price <= buy_price - (atr * ATR_STOP_LOSS_MULTIPLIER):
                sell_reason = "ボラティリティ損切 (ATR Stop)"
            elif highest_price >= buy_price + (atr * ATR_TRAIL_ACTIVATION):
                if current_price <= highest_price - (atr * ATR_TRAIL_STOP_MULTIPLIER):
                    sell_reason = "トレール利確 (ATR Trailing)"

            if sell_reason:
                # 税金計算ロジック
                gross_profit = (current_price - buy_price) * p['shares']
                tax_amount = 0
                
                # 利益が出ている場合のみ税金を計算（切り捨て）
                if gross_profit > 0:
                    tax_amount = int(gross_profit * TAX_RATE)
                
                net_profit = gross_profit - tax_amount # 税引き後利益
                
                # 口座には「売却代金 - 税金」が戻る
                sale_proceeds = (current_price * p['shares']) - tax_amount
                account['cash'] += sale_proceeds
                
                msg = f"💰 【決済】{code} {p['name']} を {sell_reason} しました！\n"
                msg += f"   税引前損益: {gross_profit:+.0f}円 | 税金: -{tax_amount:,.0f}円 | 確定純利益: {net_profit:+.0f}円"
                print(msg)
                send_discord_notify(msg)
                
                actions.append(f"売却: {code} {p['name']} ({sell_reason}) 純利益: {net_profit:+.0f}円 (税金: {tax_amount:,.0f}円)")
                
                log_trade({
                    "sell_time": current_time, "code": code, "name": p['name'], "buy_time": p['buy_time'],
                    "buy_price": buy_price, "sell_price": current_price, "highest_price_reached": highest_price,
                    "shares": p['shares'], "gross_profit": gross_profit, "tax_amount": tax_amount, 
                    "net_profit": net_profit, "profit_pct": profit_pct, "reason": sell_reason
                })
            else: remaining_portfolio.append(p)
        except Exception as e: 
            print(f"⚠️ {code} の監視エラー: {e}")
            remaining_portfolio.append(p)

    return remaining_portfolio, account, actions

# --- 5. データ取得・AI判定関数 ---
def clean_text_for_ai(text):
    if not isinstance(text, str):
        return ""
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r'[^\x20-\x7E\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', '', text)
    return text.strip()

def get_recent_news(code, name):
    clean_name = re.sub(r'\s+', ' ', name).strip()
    query = urllib.parse.quote(f"{code} {clean_name}")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        feed = feedparser.parse(rss_url)
        titles = [entry.title for entry in feed.entries[:5]]
        return " | ".join(titles) if titles else "ニュースなし"
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
    
    avg_trade_value = vol_mean_5 * df['Close'].iloc[-6:-1].mean()
    if latest['Close'] < 100 or avg_trade_value < 10000000:
        return False, None
    
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

def ai_scoring(code, name, tech, news_text, max_retries=2):
    safe_name = clean_text_for_ai(name)
    safe_news = clean_text_for_ai(news_text)

    prompt = f"""
    あなたは凄腕のクオンツ・ファンドマネージャーです。以下の情報から、銘柄の「今後数日間の大化け確率(スコア)」を 1〜100 の数値で厳格に評価してください。
    
    【銘柄】 {safe_name} ({code})
    【テクニカル指標】
    出来高急増倍率: {tech['VolSurgeRatio']:.1f}倍 (直近の大口資金流入の強さ)
    RSI: {tech['RSI']:.1f}
    MACD/シグナル: {tech['MACD']:.2f} / {tech['Signal']:.2f}
    ボラ・ブレイク: {'発生中' if tech['SqueezeBreak'] else 'なし'}
    
    【最新ニュース】 {safe_news}
    
    【評価基準（以下の視点で辛口に評価してください）】
    1. 資金流入の信憑性：出来高急増を裏付ける強力なニュース（好決算、テーマ性、提携など）があるか？
    2. テーマの持続性：一過性のイナゴタワーではなく、数日間トレンドが続く材料か？
    3. ニュースがないのに急増している場合は、仕手株のダマシの可能性があるため減点。
    
    【出力ルール】
    1行目: スコア（例: 88）
    2行目: 判定理由（100文字以内の日本語で、テクニカルと材料を紐づけて説明）
    """
    
    for attempt in range(max_retries):
        try:
            response = gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            lines = response.text.strip().split('\n')
            score = int(re.sub(r'\D', '', lines[0]))
            reason = lines[1] if len(lines) > 1 else "詳細理由なし"
            return score, f"【Gemini】{reason}"
        
        except Exception as e:
            err_msg = str(e).lower()
            if "429" in err_msg or "quota" in err_msg or "rate limit" in err_msg:
                if groq_client:
                    print(f"  ⚠️ Gemini API制限(429)を検知。Groq(Llama 3.3)へ代替処理を行います...")
                    try:
                        g_response = groq_client.chat.completions.create(
                            model="llama-3.3-70b-versatile", 
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.2
                        )
                        lines = g_response.choices[0].message.content.strip().split('\n')
                        score = int(re.sub(r'\D', '', lines[0]))
                        reason = lines[1] if len(lines) > 1 else "詳細理由なし"
                        return score, f"【Groq】{reason}"
                    except Exception as ge:
                        full_error = str(ge).replace('\n', ' ')
                        return 0, f"代替AIエラー: {full_error}"
                else:
                    if attempt < max_retries - 1:
                        print(f"  ⚠️ Gemini API制限を検知。代替AIが未設定のため60秒待機します... ({attempt+1}/{max_retries})")
                        time.sleep(60)
                        continue
            
            full_error = str(e).replace('\n', ' ')
            return 0, f"AI評価エラー: {type(e).__name__} - {full_error}"
            
    return 0, "AI評価エラー: 制限による再試行上限到達"

def print_execution_summary(actions, portfolio, account):
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    stock_value = 0
    for p in portfolio:
        cp = float(p.get('current_price', p['buy_price']))
        stock_value += cp * int(p['shares'])
        
    total_assets = account['cash'] + stock_value
    
    print("\n" + "="*45)
    print(" 📊 実行結果サマリー")
    print("="*45)
    
    print("\n【今回の実行アクション】")
    action_str = " | ".join(actions) if actions else "アクションなし"
    if actions:
        for act in actions:
            print(f" ✔ {act}")
    else:
        print(" - アクションなし (保有継続 / 新規見送り)")
        
    print("\n【現在の保有株式】")
    if portfolio:
        for p in portfolio:
            cp = float(p.get('current_price', p['buy_price']))
            val = cp * int(p['shares'])
            profit_pct = (cp - float(p['buy_price'])) / float(p['buy_price']) * 100
            print(f" 🔹 {p['code']} {p['name']}")
            print(f"    数量: {p['shares']}株 | 現在値: {cp:,.1f}円 | 評価額: {val:,.0f}円 | 損益: {profit_pct:+.2f}%")
    else:
        print(" - 保有銘柄なし")
        
    print("\n【口座ステータス】")
    print(f" 💰 現金残高:   {account['cash']:>10,.0f}円")
    print(f" 📈 株式評価額: {stock_value:>10,.0f}円")
    print(f" 👑 合計資産額: {total_assets:>10,.0f}円")
    print("="*45 + "\n")
    
    write_header = not os.path.exists(EXECUTION_LOG_FILE) or os.path.getsize(EXECUTION_LOG_FILE) == 0
    df_log = pd.DataFrame([{
        "time": current_time,
        "actions": action_str,
        "portfolio_count": len(portfolio),
        "stock_value_yen": stock_value,
        "cash_yen": account['cash'],
        "total_assets_yen": total_assets
    }])
    df_log.to_csv(EXECUTION_LOG_FILE, mode='a', header=write_header, index=False, encoding='utf-8-sig')

# --- 6. メイン処理 ---
def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚀 東証最強BOT 起動 (最強ロジック+通知版)")
    
    if not DEBUG_MODE:
        now = datetime.now()
        if now.weekday() >= 5:
            print("💤 本日は休場日（土日）のため、スキャンをスキップして終了します。")
            return
            
        current_time = now.time()
        morning_open = datetime.strptime("09:00", "%H:%M").time()
        morning_close = datetime.strptime("11:30", "%H:%M").time()
        afternoon_open = datetime.strptime("12:30", "%H:%M").time()
        afternoon_close = datetime.strptime("15:30", "%H:%M").time()
        
        is_open = (morning_open <= current_time <= morning_close) or (afternoon_open <= current_time <= afternoon_close)
        
        if not is_open:
            print("💤 現在は東証の取引時間外のため、スキャンをスキップして終了します。")
            return
    else:
        print("🔧 デバッグモード有効: 営業時間フィルターを無視して強制実行します。")

    account = load_account()
    portfolio = load_portfolio()
    actions_taken = [] 
    
    print(f"🏦 現在の現金残高: {account['cash']:,.0f}円")

    portfolio, account, sell_actions = manage_positions(portfolio, account)
    actions_taken.extend(sell_actions) 
    
    save_portfolio(portfolio)
    save_account(account)

    if len(portfolio) >= MAX_POSITIONS:
        print(f"\n💡 現在最大ポジション数（{MAX_POSITIONS}銘柄）を保有中のため、新規スキャンをスキップします。")
        print_execution_summary(actions_taken, portfolio, account)
        return

    is_market_good = check_market_trend()
    if not is_market_good:
        print("\n📉 地合いフィルター発動: 日経平均が短期下落トレンドのため、リスク回避として新規エントリーを見送ります。")
        print_execution_summary(actions_taken, portfolio, account)
        return

    try:
        df_symbols = pd.read_csv(DATA_FILE)
        targets = df_symbols['コード'].astype(str).tolist()
    except Exception as e:
        print(f"⚠️ 銘柄リスト読み込みエラー: {e}")
        print_execution_summary(actions_taken, portfolio, account)
        return

    holdings = [str(p['code']) for p in portfolio]
    targets = [t for t in targets if t not in holdings]

    hot_candidates = []
    tickers = [f"{code}.T" for code in targets]
    
    print(f"\n--- 15分足データ一括ダウンロード (新規対象: {len(tickers)}銘柄) ---")
    data = yf.download(tickers, period="5d", interval="15m", group_by='ticker', threads=True)
    if data is None or data.empty: 
        print_execution_summary(actions_taken, portfolio, account)
        return

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
        print_execution_summary(actions_taken, portfolio, account)
        return

    hot_candidates = sorted(hot_candidates, key=lambda x: x['tech']['VolSurgeRatio'], reverse=True)
    if len(hot_candidates) > MAX_AI_CANDIDATES:
        print(f"\n⚠️ スクリーニング通過が {len(hot_candidates)}銘柄 と多いため、資金流入 上位{MAX_AI_CANDIDATES}銘柄 に絞ってAI審査を行います。")
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
        
        time.sleep(20) 

    scored_list = sorted(scored_list, key=lambda x: x['ai_score'], reverse=True)
    best = scored_list[0]
    
    if best['ai_score'] >= 80:
        buy_price = best['tech']['CurrentPrice']
        budget = min(INVEST_PER_TRADE, account['cash'])
        
        if buy_price > budget:
            print(f"\n💡 株価({buy_price:,.1f}円)が現在の投資可能額({budget:,.0f}円)を上回っているため見送ります。")
        else:
            shares_to_buy = max(1, int(budget // buy_price))
            cost = buy_price * shares_to_buy
            
            print(f"\n🏆 【シミュレーション買付発動】最強銘柄確定: {best['code']} {best['name']}")
            print(f"判定理由: {best['ai_reason']}")
            print(f"🛒 買付価格: {buy_price:.1f}円 | 数量: {shares_to_buy}株 | 概算代金: {cost:,.0f}円")
            
            notify_msg = f"🏆 **【新規買付】{best['code']} {best['name']}**\n🛒 買値: {buy_price:.1f}円 × {shares_to_buy}株 (概算: {cost:,.0f}円)\n📝 理由: {best['ai_reason']}"
            send_discord_notify(notify_msg)
            
            actions_taken.append(f"買付: {best['code']} {best['name']} {shares_to_buy}株 (概算: {cost:,.0f}円)")
            
            account['cash'] -= cost
            portfolio.append({
                "code": best['code'], "name": best['name'], "buy_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "buy_price": buy_price, "highest_price": buy_price, "current_price": buy_price, "shares": shares_to_buy
            })
            save_portfolio(portfolio)
            save_account(account)
    else:
        print("\n💡 エントリー基準(AIスコア80以上)を満たす銘柄はありませんでした。見送ります。")

    print_execution_summary(actions_taken, portfolio, account)

if __name__ == "__main__":
    main()