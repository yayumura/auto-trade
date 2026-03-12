# --- 0. 環境設定 ---
import os
import sys
import io
from datetime import datetime
import yfinance as yf
import pandas as pd
import numpy as np
from google import genai
from groq import Groq  
import feedparser
import urllib.parse
import time
import re
import warnings
import json
import requests
from dotenv import load_dotenv

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"  
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
warnings.filterwarnings('ignore')

# --- ログ出力の二重化設定 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
current_date = datetime.now().strftime('%Y-%m-%d')
LOG_FILE = os.path.join(LOG_DIR, f"console_{current_date}.log")

class TeeLogger:
    def __init__(self, stream, filepath):
        self.stream = stream
        self.file = open(filepath, 'a', encoding='utf-8')

    def write(self, message):
        self.stream.write(message)
        self.file.write(message)
        self.file.flush()

    def flush(self):
        self.stream.flush()
        self.file.flush()

sys.stdout = TeeLogger(sys.stdout, LOG_FILE)
sys.stderr = TeeLogger(sys.stderr, LOG_FILE)

# --- ファイルパス設定 ---
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
    print("⚠️ エラー: GEMINI_API_KEY が設定されていません。")
    sys.exit()

gemini_client = genai.Client(api_key=GEMINI_API_KEY)
GEMINI_MODEL = "gemini-2.5-flash"

if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
else:
    groq_client = None

# --- 設定値 ---
DEBUG_MODE = True
INITIAL_CASH = 1000000  
MAX_POSITIONS = 4         # リスク分散のため4銘柄
INVEST_PER_TRADE = 250000 # 1銘柄あたり25万円上限
TAX_RATE = 0.20315        # 税率（約20.3%）

# 【最適化】15分足のノイズを吸収しつつ、大ヤケドしない適正なATR設定
ATR_STOP_LOSS_MULTIPLIER = 2.5  
ATR_TRAIL_ACTIVATION = 3.0      
ATR_TRAIL_STOP_MULTIPLIER = 1.5 

MAX_AI_CANDIDATES = 50

def send_discord_notify(message):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    except Exception as e:
        print(f"⚠️ Discord通知エラー: {e}")

def check_market_trend():
    try:
        nk = yf.download('^N225', period="2d", interval="15m", threads=False)
        if nk is None or nk.empty:
            return True 
        close = nk['Close'].dropna()
        if len(close) < 20:
            return True
        sma20 = float(close.rolling(window=20).mean().iloc[-1])
        current = float(close.iloc[-1])
        return current > sma20
    except Exception:
        return True

def load_account():
    if os.path.exists(ACCOUNT_FILE) and os.path.getsize(ACCOUNT_FILE) > 0:
        try:
            with open(ACCOUNT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {"cash": INITIAL_CASH}

def save_account(account_data):
    with open(ACCOUNT_FILE, 'w', encoding='utf-8') as f:
        json.dump(account_data, f, indent=4)

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE) and os.path.getsize(PORTFOLIO_FILE) > 0:
        try:
            return pd.read_csv(PORTFOLIO_FILE).to_dict('records')
        except pd.errors.EmptyDataError:
            return []
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
    if not portfolio:
        return portfolio, account, actions

    print(f"\n--- 💼 保有銘柄の監視 ({len(portfolio)}銘柄) ---")
    tickers = [f"{p['code']}.T" for p in portfolio]
    data = yf.download(tickers, period="5d", interval="15m", group_by='ticker', threads=True)
    
    if data is None or data.empty:
        return portfolio, account, actions

    remaining_portfolio = []
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for p in portfolio:
        code = str(p['code'])
        ticker = f"{code}.T"
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if ticker not in data.columns.levels[0]:
                    remaining_portfolio.append(p)
                    continue
                df = data[ticker].dropna()
            else:
                if len(portfolio) == 1 or ticker == data.columns.name:
                    df = data.dropna()
                else:
                    remaining_portfolio.append(p)
                    continue
            
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
                gross_profit = (current_price - buy_price) * p['shares']
                tax_amount = int(gross_profit * TAX_RATE) if gross_profit > 0 else 0
                net_profit = gross_profit - tax_amount 
                sale_proceeds = (current_price * p['shares']) - tax_amount
                account['cash'] += sale_proceeds
                
                msg = f"💰 【決済】{code} {p['name']} を {sell_reason} しました！\n   税引前損益: {gross_profit:+.0f}円 | 税金: -{tax_amount:,.0f}円 | 確定純利益: {net_profit:+.0f}円"
                print(msg)
                send_discord_notify(msg)
                actions.append(f"売却: {code} {p['name']} ({sell_reason}) 純利益: {net_profit:+.0f}円")
                log_trade({
                    "sell_time": current_time, "code": code, "name": p['name'], "buy_time": p['buy_time'],
                    "buy_price": buy_price, "sell_price": current_price, "highest_price_reached": highest_price,
                    "shares": p['shares'], "gross_profit": gross_profit, "tax_amount": tax_amount, 
                    "net_profit": net_profit, "profit_pct": profit_pct, "reason": sell_reason
                })
            else:
                remaining_portfolio.append(p)
        except Exception as e: 
            print(f"⚠️ {code} の監視エラー: {e}")
            remaining_portfolio.append(p)

    return remaining_portfolio, account, actions

def clean_text_for_ai(text):
    if not isinstance(text, str):
        return ""
    text = re.sub(r'[\r\n\t]+', ' ', text)
    return re.sub(r'[^\x20-\x7E\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', '', text).strip()

def get_recent_news(code, name):
    clean_name = re.sub(r'\s+', ' ', name).strip()
    query = urllib.parse.quote(f"{code} {clean_name}")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        feed = feedparser.parse(rss_url)
        titles = [entry.title for entry in feed.entries[:5]]
        return " | ".join(titles) if titles else "ニュースなし"
    except:
        return "ニュース取得エラー"

def calculate_technicals(df):
    if len(df) < 50:
        return None
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
    
    # 1. 流動性フィルター（クズ株排除）
    vol_mean_5 = df['Volume'].iloc[-6:-1].mean()
    if vol_mean_5 == 0:
        vol_mean_5 = 1 
    avg_trade_value = vol_mean_5 * df['Close'].iloc[-6:-1].mean()
    if latest['Close'] < 100 or avg_trade_value < 10000000:
        return False, None
    
    # 2. 資金流入（出来高急増）
    vol_surge_ratio = latest['Volume'] / vol_mean_5
    vol_surge = vol_surge_ratio > 3.0
    
    # 3. ブレイクアウト判定
    lookback_5d = min(100, len(df)-1)
    break_5d = latest['Close'] > df['High'].iloc[-(lookback_5d+1):-1].max()
    squeeze_condition = df['BB_Width'].iloc[-10:-1].mean() < 0.05
    volatility_expansion = latest['BB_Width'] > df['BB_Width'].iloc[-2]
    is_breakout = break_5d or (squeeze_condition and volatility_expansion)
    
    # --- 【重要】高値掴みを防ぐ絶対防御フィルター ---
    # 防御1：VWAPからの乖離が大きすぎないか（+5%以上離れていたら手を出さない）
    vwap_diff_pct = (latest['Close'] - latest['VWAP']) / latest['VWAP']
    is_near_vwap = latest['Close'] > latest['VWAP'] and vwap_diff_pct < 0.05
    
    # 防御2：RSIが過熱していないか（75以上はイナゴタワーの危険）
    not_overbought = latest['RSI'] < 75
    
    # 防御3：長すぎる上ヒゲがないか（売り圧力が強い証拠）
    upper_shadow = latest['High'] - max(latest['Close'], latest['Open'])
    no_high_wick = upper_shadow < (latest['ATR'] * 0.4)
    
    # すべての条件を満たした「安全な初動」のみを抽出
    is_hot = vol_surge and is_breakout and is_near_vwap and not_overbought and no_high_wick
    
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
    あなたは凄腕のクオンツ・ファンドマネージャーです。以下の情報から、銘柄の「直近の急騰確率(スコア)」を 1〜100 の数値で厳格に評価してください。
    
    【銘柄】 {safe_name} ({code})
    【テクニカル指標】
    出来高急増倍率: {tech['VolSurgeRatio']:.1f}倍 (直近の大口資金流入の強さ)
    RSI: {tech['RSI']:.1f}
    MACD/シグナル: {tech['MACD']:.2f} / {tech['Signal']:.2f}
    ボラ・ブレイク: {'発生中' if tech['SqueezeBreak'] else 'なし'}
    
    【最新ニュース】 {safe_news}
    
    【評価基準（辛口に評価してください）】
    1. 資金流入の信憑性：出来高急増を裏付ける強力なニュース（好決算、テーマ性、提携など）があるか？
    2. テーマの持続性：一過性のイナゴタワーではなく、数日間トレンドが続く材料か？
    3. ニュースがないのに急騰している仕手株は大幅に減点。
    
    【出力ルール】
    1行目: スコア（例: 88）
    2行目: 判定理由（100文字以内の日本語で説明）
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
                    print(f"  ⚠️ Gemini制限検知。Groqへ代替処理...")
                    try:
                        g_response = groq_client.chat.completions.create(
                            model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], temperature=0.2
                        )
                        lines = g_response.choices[0].message.content.strip().split('\n')
                        score = int(re.sub(r'\D', '', lines[0]))
                        reason = lines[1] if len(lines) > 1 else "詳細理由なし"
                        return score, f"【Groq】{reason}"
                    except Exception as ge:
                        return 0, f"代替AIエラー: {ge}"
                else:
                    if attempt < max_retries - 1:
                        time.sleep(60)
                        continue
            return 0, f"AI評価エラー: {e}"
    return 0, "AI評価エラー: 再試行上限到達"

def print_execution_summary(actions, portfolio, account):
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    stock_value = sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio])
    total_assets = account['cash'] + stock_value
    
    print("\n" + "="*45)
    print(" 📊 実行結果サマリー (初動ブレイクアウト完成形)")
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
            print(f" 🔹 {p['code']} {p['name']}\n    数量: {p['shares']}株 | 現在値: {cp:,.1f}円 | 評価額: {val:,.0f}円 | 損益: {profit_pct:+.2f}%")
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

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚀 東証最強BOT 起動 (初動ブレイクアウト完成版)")
    
    if not DEBUG_MODE:
        now = datetime.now()
        if now.weekday() >= 5:
            return
        
        current_time = now.time()
        morning_open = datetime.strptime("09:00", "%H:%M").time()
        morning_close = datetime.strptime("11:30", "%H:%M").time()
        afternoon_open = datetime.strptime("12:30", "%H:%M").time()
        afternoon_close = datetime.strptime("15:30", "%H:%M").time()
        
        if not ((morning_open <= current_time <= morning_close) or (afternoon_open <= current_time <= afternoon_close)):
            return

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

    if not check_market_trend():
        print("\n📉 地合いフィルター発動: 日経平均が短期下落トレンドのため、リスク回避として新規エントリーを見送ります。")
        print_execution_summary(actions_taken, portfolio, account)
        return

    try:
        df_symbols = pd.read_csv(DATA_FILE)
        targets = [str(t) for t in df_symbols['コード'].tolist() if str(t) not in [str(p['code']) for p in portfolio]]
    except Exception as e:
        print(f"⚠️ 銘柄リスト読み込みエラー: {e}")
        return

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
                if ticker not in data.columns.levels[0]:
                    continue
                df = data[ticker].dropna()
            else:
                if len(targets) == 1 or ticker == data.columns.name:
                    df = data.dropna()
                else:
                    continue
            
            if df.empty or len(df) < 50:
                continue
                
            df = calculate_technicals(df)
            if df is None:
                continue
            
            is_hot, tech_data = scan_initial_breakout(df)
            if is_hot:
                name_row = df_symbols[df_symbols['コード'].astype(str) == code]
                name = name_row['銘柄名'].values[0] if not name_row.empty else "不明"
                hot_candidates.append({"code": code, "name": name, "tech": tech_data})
        except Exception:
            continue

    if not hot_candidates:
        print("💡 現在の15分足で「安全な初動ブレイクアウト」を満たす新規銘柄はありません。")
        print_execution_summary(actions_taken, portfolio, account)
        return

    hot_candidates = sorted(hot_candidates, key=lambda x: x['tech']['VolSurgeRatio'], reverse=True)
    if len(hot_candidates) > MAX_AI_CANDIDATES:
        hot_candidates = hot_candidates[:MAX_AI_CANDIDATES]

    print(f"\n--- 🤖 AIスコアリング (審査対象: {len(hot_candidates)}銘柄) ---")
    scored_list = []
    
    for idx, item in enumerate(hot_candidates, 1):
        news = get_recent_news(item['code'], item['name'])
        score, reason = ai_scoring(item['code'], item['name'], item['tech'], news)
        item['ai_score'], item['ai_reason'] = score, reason
        scored_list.append(item)
        print(f"[{idx}/{len(hot_candidates)}] {item['code']} {item['name']} | 急増: {item['tech']['VolSurgeRatio']:.1f}倍 | スコア: {score}点 | 理由: {reason}")
        time.sleep(20) 

    best = sorted(scored_list, key=lambda x: x['ai_score'], reverse=True)[0]
    
    if best['ai_score'] >= 80:
        buy_price = best['tech']['CurrentPrice']
        budget = min(INVEST_PER_TRADE, account['cash'])
        
        if buy_price <= budget:
            shares_to_buy = max(1, int(budget // buy_price))
            cost = buy_price * shares_to_buy
            
            print(f"\n🏆 【新規買付発動】最強銘柄確定: {best['code']} {best['name']}")
            print(f"判定理由: {best['ai_reason']}")
            print(f"🛒 買付価格: {buy_price:.1f}円 | 数量: {shares_to_buy}株 | 概算代金: {cost:,.0f}円")
            
            notify_msg = f"🏆 **【新規買付】{best['code']} {best['name']}**\n🛒 買付: {buy_price:.1f}円 × {shares_to_buy}株 (概算: {cost:,.0f}円)\n📝 理由: {best['ai_reason']}"
            send_discord_notify(notify_msg)
            
            actions_taken.append(f"買付: {best['code']} {best['name']} {shares_to_buy}株 (概算: {cost:,.0f}円)")
            
            account['cash'] -= cost
            portfolio.append({
                "code": best['code'], "name": best['name'], 
                "buy_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                "buy_price": buy_price, "highest_price": buy_price, 
                "current_price": buy_price, "shares": shares_to_buy
            })
            save_portfolio(portfolio)
            save_account(account)
    else:
        print("\n💡 エントリー基準(AIスコア80以上)を満たす銘柄はありませんでした。見送ります。")

    print_execution_summary(actions_taken, portfolio, account)

if __name__ == "__main__":
    main()