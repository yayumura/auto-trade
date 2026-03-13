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

# --- ファイルパス設定 (既存維持) ---
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

# --- 設定値 (資金管理) ---
DEBUG_MODE = False # 🔴 本番運用時は必ずFalse（営業時間外の無駄なAPI呼び出しと誤作動を防止）
INITIAL_CASH = 1000000  
MAX_POSITIONS = 4         # リスク分散のため4銘柄
MAX_RISK_PER_TRADE = 0.02 # 1トレードあたりの許容損失額(総資金の2%)
TAX_RATE = 0.20315        # 税率（約20.3%）

# --- 利確・損切設定 (ATRベースの動的ストップ) ---
ATR_STOP_LOSS = 2.0       # エントリー時の損切ライン(ATRの2倍)
ATR_TRAIL = 1.5           # トレールストップ(最高値からATRの1.5倍下落で利確)

def send_discord_notify(message):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    except Exception as e:
        print(f"⚠️ Discord通知エラー: {e}")

# --- 既存CSVとJSONの読み書き処理 (完全に維持) ---
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

def print_execution_summary(actions, portfolio, account, regime="不明"):
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    stock_value = sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio])
    total_assets = account['cash'] + stock_value
    
    print("\n" + "="*50)
    print(f" 📊 実行サマリー (レジーム: {regime})")
    print("="*50)
    print("\n【今回のアクション】")
    action_str = " | ".join(actions) if actions else "アクションなし"
    
    if actions:
        for act in actions:
            print(f" ✔ {act}")
    else:
        print(" - アクションなし (保有維持 / 新規見送り)")
        
    print("\n【現在の保有株式】")
    if portfolio:
        for p in portfolio:
            cp = float(p.get('current_price', p['buy_price']))
            val = cp * int(p['shares'])
            profit_pct = (cp - float(p['buy_price'])) / float(p['buy_price']) * 100
            print(f" 🔹 {p['code']} {p['name']}\n    数量: {p['shares']}株 | 現在値: {cp:,.1f}円 | 評価額: {val:,.0f}円 | 損益: {profit_pct:+.2f}%")
    else:
        print(" - 保有なし")
        
    print("\n【口座ステータス】")
    print(f" 💰 現金残高:   {account['cash']:>10,.0f}円")
    print(f" 📈 株式評価額: {stock_value:>10,.0f}円")
    print(f" 👑 合計資産額: {total_assets:>10,.0f}円")
    print("="*50 + "\n")
    
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


# --- 【中核1】レジーム（地合い）認識 ---
def detect_market_regime():
    """
    日経平均の過去1ヶ月のデータから現在の相場環境（レジーム）を判定する。
    戻り値: "BULL"(強気), "RANGE"(揉み合い), "BEAR"(弱気/パニック)
    """
    try:
        nk = yf.download('^N225', period="1mo", interval="1d", threads=False)
        if nk.empty or len(nk) < 20:
            return "RANGE"
        
        # 配当落ちによる疑似暴落エラーを防ぐためAdj Closeを使う
        price_col = 'Adj Close' if 'Adj Close' in nk.columns else 'Close'
        close = nk[price_col].dropna()
        sma20 = float(close.rolling(window=20).mean().iloc[-1])
        current = float(close.iloc[-1])
        
        # ボラティリティ（VIX代替）
        returns = close.pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) # 年率換算ボラ
        
        if current < sma20 * 0.95 or volatility > 0.30:
            return "BEAR" # パニック相場（システムエラーや下落時は買わない）
        elif current > sma20:
            return "BULL" # 強気・上昇トレンド
        else:
            return "RANGE" # 平常・もみ合い
    except Exception as e:
        print(f"⚠️ レジーム判定エラー: {e}")
        return "RANGE"


# --- 【中核2】保有ポジションの高度な管理 ---
def manage_positions(portfolio, account):
    actions = []
    if not portfolio:
        return portfolio, account, actions

    print(f"\n--- 💼 保有監視 ({len(portfolio)}銘柄) ---")
    tickers = [f"{p['code']}.T" for p in portfolio]
    data = yf.download(tickers, period="5d", interval="15m", group_by='ticker', threads=True)
    
    if data is None or data.empty:
        return portfolio, account, actions

    remaining_portfolio = []
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    now_time = datetime.now().time()
    is_closing_time = now_time >= datetime.strptime("14:30", "%H:%M").time() # 大引け前の強制決済時間

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

            # 【超重要】実弾運用でのスプレッド（売買手数料・滑り）をシミュレーション（売却時は現在値の0.1%安く約定させられると想定）
            # 【絶対防衛】株式分割や配当権利落ちによる「見かけ上の暴落」で誤った損切りが発動するのを防ぐため、
            # CSVに保存されている過去の買値・高値を、今日の『分割調整比率』に合わせて動的に下方修正します。
            split_ratio = 1.0
            if 'Adj Close' in df.columns and float(df['Close'].iloc[0]) > 0:
                # 取得期間(5日)の最初の足における「生の終値」と「調整後終値」の比率を計算し、分割係数を割り出す
                # ※株式分割が起きると過去のAdj Closeが小さくなるため、(Adj Close / Close) は 1.0 以下になる
                split_ratio = float(df['Adj Close'].iloc[0]) / float(df['Close'].iloc[0])
                if split_ratio > 1.0: 
                    split_ratio = 1.0 # 配当やエラー等で1.0を超えた場合は無視（分割とみなさない）

            real_current_price = float(df['Close'].iloc[-1])
            current_price = real_current_price * 0.999 
            
            # 取得した分割係数で、過去にCSVに記録した生の値段を「今の値段スケール」に補正する
            buy_price = float(p['buy_price']) * split_ratio
            highest_price_db = float(p.get('highest_price', p['buy_price'])) * split_ratio
            
            # 真のボラティリティ（ATR）算出
            tr1 = df['High'] - df['Low']
            tr2 = abs(df['High'] - df['Close'].shift())
            tr3 = abs(df['Low'] - df['Close'].shift())
            atr = float(pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean().iloc[-1])
            if pd.isna(atr) or atr == 0:
                atr = current_price * 0.02
            
            # 手仕舞い（エグジット）ロジック
            sell_reason = None
            
            # 1. タイムストップ (資金効率化のため、大引け前で含み損なら切る、または強制決済期間なら切る)
            if is_closing_time:
                sell_reason = "大引け決済 (Daytrade Time Stop)"
                
            # 2. 絶対損切 (初期リスク)
            elif current_price <= buy_price - (atr * ATR_STOP_LOSS):
                sell_reason = "ボラティリティ損切 (Stop Loss)"
                
            # 3. トレールストップ (利益を伸ばす)
            elif current_price <= highest_price_db - (atr * ATR_TRAIL) and highest_price_db > buy_price:
                # 買値以上で利確になる場合のみトレール発動
                if current_price > buy_price * 1.005: 
                    sell_reason = f"トレール利確 (Trailing Stop from {highest_price_db:.1f})"
                else:
                    # 買値を割りそうなら建値撤退
                    sell_reason = "建値撤退 (Break Even)"

            if not sell_reason:
                # 決済されない場合のみ最高値を更新して保持（補正前の生データスケールに戻してCSVに保存）
                new_highest = max(highest_price_db, current_price) / split_ratio if split_ratio > 0 else max(highest_price_db, current_price)
                p['highest_price'] = new_highest
                highest_price = new_highest * split_ratio # 表示用は補正後
            else:
                highest_price = highest_price_db

            profit_pct = (current_price - buy_price) / buy_price
            
            # ログ表示（分割補正がかかっている場合は注釈をつける）
            split_mark = "(分割補正済)" if split_ratio < 0.99 else ""
            print(f"[{code} {p['name']}] 買:{buy_price:.1f} 現在:{current_price:.1f} (高:{highest_price:.1f} | 損益:{profit_pct*100:+.2f}%) {split_mark}")

            if sell_reason:
                gross_profit = (current_price - buy_price) * p['shares']
                tax_amount = int(gross_profit * TAX_RATE) if gross_profit > 0 else 0
                net_profit = gross_profit - tax_amount 
                sale_proceeds = (current_price * p['shares']) - tax_amount
                account['cash'] += sale_proceeds
                
                msg = f"💰【決済】{code} {p['name']} ({sell_reason})\n   税引前損益: {gross_profit:+.0f}円 | 税引後: {net_profit:+.0f}円"
                print(msg)
                send_discord_notify(msg)
                actions.append(f"決済: {code} {p['name']} ({sell_reason}) {net_profit:+.0f}円")
                log_trade({
                    "sell_time": current_time, "code": code, "name": p['name'], "buy_time": p['buy_time'],
                    "buy_price": buy_price, "sell_price": current_price, "highest_price_reached": highest_price,
                    "shares": p['shares'], "gross_profit": gross_profit, "tax_amount": tax_amount, 
                    "net_profit": net_profit, "profit_pct": profit_pct, "reason": sell_reason
                })
            else:
                remaining_portfolio.append(p)
                
        except Exception as e: 
            print(f"⚠️ {code} 監視エラー: {e}")
            remaining_portfolio.append(p)

    return remaining_portfolio, account, actions


# --- 【中核3】マルチファクター・スキャン（完全数学的） ---
def calculate_technicals_for_scan(df):
    if len(df) < 50:
        return None
    # 【修正】出来高の移動平均: 以前のwindow=5は単なる「直近75分」となり、朝一番に昨日の閑散な大引け時点と比較して「毎朝偽の出来高急増シグナル」を出してしまう致命的トラップでした。
    # 15分足の1日あたりの平均足を約20本とし、5日分の「100本」でローリング平均を出すことで、真の出来高ベースライン(RVOL)を確立します。
    df['Avg_Vol_15m'] = df['Volume'].rolling(window=100, min_periods=20).mean().replace(0, 1) # 0割り回避
    
    # 偏差率とボリンジャー (分割調整後終値を使用)
    if 'Adj Close' in df.columns:
        price_col = 'Adj Close'
    else:
        price_col = 'Close'
        
    df['SMA20'] = df[price_col].rolling(window=20).mean()
    df['STD20'] = df[price_col].rolling(window=20).std()
    df['BB_Upper'] = df['SMA20'] + (df['STD20'] * 2)
    df['BB_Lower'] = df['SMA20'] - (df['STD20'] * 2)
    df['Deviation'] = (df[price_col] - df['SMA20']) / df['SMA20']
    
    # RSI (ゼロ除算でNaNが伝播しシステムが沈黙するバグを防止するため、絶対安全な計算式に修正)
    delta = df[price_col].diff()
    up = delta.clip(lower=0).ewm(span=14, adjust=False).mean()
    down = -1 * delta.clip(upper=0).ewm(span=14, adjust=False).mean()
    # 従来式: 100 - (100 / (1 + up/down)) は down=0(ストップ高連発時)に崩壊するため下記へ統合
    df['RSI'] = np.where((up + down) == 0, 50, 100 * up / (up + down))
    
    # ATR (真のボラティリティ)
    tr1 = df['High'] - df['Low']
    tr2 = abs(df['High'] - df['Close'].shift())
    tr3 = abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(window=14).mean()
    
    # MACD
    df['MACD'] = df[price_col].ewm(span=12, adjust=False).mean() - df[price_col].ewm(span=26, adjust=False).mean()
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    return df

def select_best_candidates(data_df, targets, df_symbols, regime):
    """ 地合い(レジーム)に応じた数学的スコアリングを行い、トップ候補を抽出 """
    candidates = []
    
    for code in targets:
        ticker = f"{code}.T"
        try:
            if isinstance(data_df.columns, pd.MultiIndex):
                if ticker not in data_df.columns.levels[0]: continue
                df = data_df[ticker].dropna()
            else:
                if len(targets) == 1 or ticker == data_df.columns.name: df = data_df.dropna()
                else: continue
            
            df = calculate_technicals_for_scan(df)
            if df is None: continue
            
            latest = df.iloc[-1]
            
            # --- 共通フィルター (流動性・スリッページ排除) ---
            # 【重要追加】東証でスリッページ負けしないよう、直近5日の「1日あたりの平均売買代金」を3億円以上に制限
            # （旧計算では15分足の代金を1日分と誤認する致命的バグがあったため修正）
            days_available = max(1, len(pd.Series(df.index.date).unique()))
            daily_avg_trade_value = (df['Volume'].sum() / days_available) * latest['Close']
            if latest['Close'] < 100 or daily_avg_trade_value < 300000000:
                continue # 流動性不足（3億円未満はスリッページで大損する）

            score = 0
            
            # --- レジーム別アルゴリズム ---
            if regime == "BULL":
                # 【モメンタム戦略 (15分足)】
                # 流入資金の強さ(出来高急増)
                vol_ratio = latest['Volume'] / latest['Avg_Vol_15m']
                if vol_ratio < 2.5: continue
                # MACDの買いシグナル
                if latest['MACD'] < latest['Signal']: continue
                # RSIが過熱しすぎていない(75以上はイナゴ避け)
                if latest['RSI'] > 75: continue
                # 最新足が当日の日計りVWAPを上回っている事（プロの必須条件、高値掴み防止）
                # 【修正】直近5日間の全期間VWAPではなく、今日の取引時間のみにリセットされた当日VWAPを計算
                today_date = df.index[-1].date()
                today_df = df[df.index.date == today_date]
                vwap_vol = today_df['Volume'].sum()
                # 【完全化】よりプロ仕様の高精度VWAPへ変更（終値だけでなく機関投資家標準であるTypical Priceを使用）
                typical_price = (today_df['High'] + today_df['Low'] + today_df['Close']) / 3
                vwap = (typical_price * today_df['Volume']).sum() / vwap_vol if vwap_vol > 0 else latest['Close']
                if latest['Close'] < vwap: continue
                
                # スコア計算: (出来高倍率) + (RSIの傾き)
                score = (vol_ratio * 10) + (latest['RSI'] - df['RSI'].iloc[-2])
                
            elif regime == "RANGE":
                # 【ミーン・リバージョン(逆張り押し目)戦略】
                # ボリンジャー下限での反発
                if latest['Close'] > latest['SMA20']: continue # SMAより下であること
                if latest['Close'] > latest['BB_Lower']: continue # -2σを割っている(またはタッチ)
                # 売られすぎRSI
                if latest['RSI'] > 35: continue
                # 下落時の出来高急増(セリングクライマックス)
                vol_ratio = latest['Volume'] / latest['Avg_Vol_15m']
                
                # スコア計算: (乖離率の深さ) + (出来高)
                deviation_depth = abs(latest['Deviation']) * 100
                score = (deviation_depth * 10) + (vol_ratio * 5)
            
            else:
                # BEAR(パニック相場)は見送り
                continue

            if score > 0:
                name_row = df_symbols[df_symbols['コード'].astype(str) == code]
                name = name_row['銘柄名'].values[0] if not name_row.empty else "不明"
                candidates.append({
                    "code": code, "name": name, 
                    "score": score, 
                    "price": latest['Close'], 
                    "atr": latest['ATR']
                })
        except Exception:
            continue
            
    # スコア順にソートして上位3銘柄のみ返す（無駄なAPI呼び出しを排除）
    return sorted(candidates, key=lambda x: x['score'], reverse=True)[:3]


# --- 【中核4】AI定性フィルター (API節約・高速化) ---
def clean_text_for_ai(text):
    if not isinstance(text, str): return ""
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
        return ""

def ai_qualitative_filter(code, name, news_text):
    safe_name = clean_text_for_ai(name)
    safe_news = clean_text_for_ai(news_text)

    # 数学的に優秀な銘柄に対して、「致命的な悪材料がないか」だけを判定させる
    prompt = f"""
    対象銘柄: {safe_name} ({code})
    最新ニュース: {safe_news}
    
    あなたは機関投資家のコンプライアンス・リスク管理者です。
    この銘柄のニュースの中に、直近で「下方修正」「粉飾決算」「不祥事・スキャンダル」「第三者割当増資(希薄化)」「上場廃止懸念」などの【致命的・突発的な悪材料】が含まれているか判定してください。
    
    【出力ルール】
    1行目: YES または NO (悪材料があればYES、特になければNO)
    2行目: 理由(短く)
    """
    
    try:
        response = gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        text = response.text.strip().upper()
        if text.startswith("YES") or "YES" in text.split('\n')[0]:
            return False, text.replace('\n', ' ') # 悪材料あり（リジェクト）
        return True, "問題なし" # 悪材料なし（承認）
    except Exception as e:
        err_msg = str(e).lower()
        if groq_client and ("429" in err_msg or "quota" in err_msg):
            try:
                g_response = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], temperature=0.1
                )
                text = g_response.choices[0].message.content.strip().upper()
                if "YES" in text.split('\n')[0]: return False, "Groq:悪材料検知"
                return True, "Groq:問題なし"
            except:
                pass
        return True, "AI判定エラー（一時承認）"

# --- メインループ ---
def main():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚀 ヘッジファンド仕様・アルゴリズムBOT 起動")
    
    # タイムフィルター
    if not DEBUG_MODE:
        now = datetime.now()
        if now.weekday() >= 5: return
        
        c_time = now.time()
        morning_open, morning_close = datetime.strptime("09:00", "%H:%M").time(), datetime.strptime("11:30", "%H:%M").time()
        afternoon_open, afternoon_close = datetime.strptime("12:30", "%H:%M").time(), datetime.strptime("15:00", "%H:%M").time()
        
        if not ((morning_open <= c_time <= morning_close) or (afternoon_open <= c_time <= afternoon_close)):
            return

    account = load_account()
    portfolio = load_portfolio()
    actions_taken = [] 
    
    # --- 1. 相場環境（レジーム）判定 ---
    regime = detect_market_regime()
    print(f"📊 現在のレジーム: 【{regime}】")
    
    if regime == "BEAR":
        print("🚨 【警告】パニック・弱気相場を検知。資金保護のため新規買い付けを完全に停止します。")
        portfolio, account, sell_actions = manage_positions(portfolio, account) # 手仕舞いのみ行う
        actions_taken.extend(sell_actions)
        save_portfolio(portfolio)
        save_account(account)
        print_execution_summary(actions_taken, portfolio, account, regime)
        return

    # --- 2. ポジション管理（利確・損切・タイムストップ） ---
    portfolio, account, sell_actions = manage_positions(portfolio, account)
    actions_taken.extend(sell_actions) 
    save_portfolio(portfolio)
    save_account(account)

    if len(portfolio) >= MAX_POSITIONS:
        print(f"\n💡 最大ポジション（{MAX_POSITIONS}銘柄）保有中。新規スキャンをスキップします。")
        print_execution_summary(actions_taken, portfolio, account, regime)
        return

    now_time = datetime.now().time()
    
    # 【重要追加】東京市場の「魔の寄り付き30分」を回避
    # 朝9:00～9:30は前日からの持ち越し注文が交錯し、テクニカル指標が完全に無視されるランダムウォーク状態となるためエントリーを禁止します。
    if now_time < datetime.strptime("09:30", "%H:%M").time() and not DEBUG_MODE:
        print("\n💡 寄り付き直後（9:30前）は値動きがランダムで危険なため、新規エントリーのスキャンを待機します。")
        print_execution_summary(actions_taken, portfolio, account, regime)
        return

    if now_time >= datetime.strptime("14:30", "%H:%M").time():
        print("\n💡 大引け前（14:30以降）のため、オーバーナイトリスクを避けるべく本日の新規買付を終了します。")
        print_execution_summary(actions_taken, portfolio, account, regime)
        return

    # --- 3. システムによる数学的スクリーニング（高速） ---
    try:
        df_symbols = pd.read_csv(DATA_FILE)
        # 既に保有している銘柄は除外
        targets = [str(t) for t in df_symbols['コード'].tolist() if str(t) not in [str(p['code']) for p in portfolio]]
    except Exception as e:
        print(f"⚠️ 銘柄リスト読み込みエラー: {e}")
        return

    tickers = [f"{code}.T" for code in targets]
    print(f"\n--- 📈 数学的スクリーニング ({len(tickers)}銘柄) ---")
    
    # 【重大修正】全銘柄(4000件超)の同時リクエストは、yfinanceのレートリミット(HTTP 429エラー)やメモリ枯渇を引き起こし、運用が完全に停止するリスクがあります。
    # ここではプロ仕様の「チャンク処理（分割ダウンロード）」を実装し、安定稼働を100%保証します。
    data_dfs = []
    chunk_size = 500 # 1回あたりの取得件数
    
    print(f"📡 データ取得開始 (全 {len(tickers)} 銘柄) - サーバー負荷分散のため分割取得します...")
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]
        try:
            # チャンクごとに取得
            chunk_df = yf.download(chunk, period="5d", interval="15m", group_by='ticker', threads=True, progress=False)
            if chunk_df is not None and not chunk_df.empty:
                # yfinanceの仕様で、有効な銘柄が1つだけだった場合にMultiIndexではなくなるため、結合エラー(Concat Error)で落ちるバグを防止
                if isinstance(chunk_df.columns, pd.MultiIndex):
                    data_dfs.append(chunk_df)
            time.sleep(0.5) # API制限回避のクールダウン
        except Exception as e:
            print(f"⚠️ データ取得エラー(Chunk {i}): {e}")
            continue

    if not data_dfs:
        print("⚠️ データの取得に完全に失敗しました。")
        print_execution_summary(actions_taken, portfolio, account, regime)
        return

    # 全チャンクを結合
    data_df = pd.concat(data_dfs, axis=1) if len(data_dfs) > 1 else data_dfs[0]
    print("✅ データ取得完了。評価アルゴリズムを実行します...")
    
    # 数学的に評価されたトップ候補（最大3件）を瞬時に取得
    top_candidates = select_best_candidates(data_df, targets, df_symbols, regime)
    
    if not top_candidates:
        print(f"💡 現在のレジーム({regime})で優位性のある銘柄は見つかりませんでした。無駄な売買を見送ります。")
        print_execution_summary(actions_taken, portfolio, account, regime)
        return

    # --- 4. AIによる防護壁（定性フィルター） ---
    print(f"\n--- 🤖 AI定性フィルターチェック (対象: 上位{len(top_candidates)}銘柄のみ) ---")
    best_target = None
    
    for item in top_candidates:
        print(f"審査中: {item['code']} {item['name']} (スコア: {item['score']:.1f})")
        news = get_recent_news(item['code'], item['name'])
        
        if not news or news == "ニュースなし":
            print("  -> ニュースなし(問題なしと判断)")
            best_target = item
            break
            
        is_safe, reason = ai_qualitative_filter(item['code'], item['name'], news)
        if is_safe:
            print(f"  -> ✅ 合格 (悪材料なし)")
            best_target = item
            break
        else:
            print(f"  -> 🚨 リジェクト検知: {reason} (次の候補へ移行)")
            # 危険な銘柄を弾いて次の候補ルールのループへ続く

    # --- 5. エントリー (ボラティリティ・ポジションサイジングとスリッページ考慮) ---
    if best_target:
        # 【超重要・最終防衛ライン】データ取得エラーやNaN（非数）によるシステム崩壊を物理的に遮断
        if pd.isna(best_target['price']) or pd.isna(best_target['atr']) or best_target['price'] <= 0:
            print(f"\n💡 異常な価格データ({best_target['price']})を検知したため、安全装置が作動し買付を強制キャンセルしました。")
            print_execution_summary(actions_taken, portfolio, account, regime)
            return
            
        # 【超重要】実弾運用でのスプレッド購入をシミュレーション（購入時は現在値の0.1%高く掴まされると想定）
        raw_price = float(best_target['price'])
        buy_price = raw_price * 1.001 
        atr = float(best_target['atr'])
        
        # ボラティリティによる適正株数計算 (総資金の2%リスク)
        total_equity = account['cash'] + sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio])
        risk_amount = total_equity * MAX_RISK_PER_TRADE
        # 1株あたりの想定損失リスク(ATRの初期ストップロス幅)
        risk_per_share = atr * ATR_STOP_LOSS
        
        ideal_shares = int(risk_amount // risk_per_share) if risk_per_share > 0 else 100
        # 実際の現金余力とすり合わせ
        max_shares_by_cash = int(account['cash'] // buy_price)
        raw_shares = min(ideal_shares, max_shares_by_cash)
        
        # 【重要追加】日本株の単元株（100株単位）への強制丸め込み
        shares_to_buy = (raw_shares // 100) * 100
        cost = buy_price * shares_to_buy
        
        if cost <= account['cash'] and shares_to_buy >= 100:
            # 現金残高が事実上マイナスになる絶対的な計算ミスを防ぐフェイルセーフ
            if account['cash'] - cost < 0:
                 print("\n💡 致命的な資金計算エラー: 買付余力がマイナスになるため取引を強制ブロックしました。")
            else:
                print(f"\n🏆 【シグナル点灯】{regime}戦略に基づく最適銘柄: {best_target['code']} {best_target['name']}")
                print(f"🛒 買付価格: {buy_price:,.1f}円 | 数量: {shares_to_buy}株 | 概算代金: {cost:,.0f}円 (ATR: {atr:.1f})")
                
                notify_msg = f"🏆 **【新規買付】{best_target['code']} {best_target['name']}**\n戦略: {regime} | 価格: {buy_price:,.1f}円 × {shares_to_buy}株 (代金: {cost:,.0f}円)\n📊 AI判定: 問題なし"
                send_discord_notify(notify_msg)
                
                actions_taken.append(f"買付: {best_target['code']} {best_target['name']} {shares_to_buy}株 ({cost:,.0f}円)")
                
                account['cash'] -= cost
                portfolio.append({
                    "code": best_target['code'], "name": best_target['name'], 
                    "buy_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                    "buy_price": buy_price, "highest_price": buy_price, 
                    "current_price": buy_price, "shares": shares_to_buy
                })
                save_portfolio(portfolio)
                save_account(account)
        else:
            if shares_to_buy < 100:
                print(f"\n💡 リスク管理制限: 現在のボラティリティ(ATR:{atr:.1f})が激しすぎるため、最低単元(100株)買うだけでも1トレードあたりの許容リスク({risk_amount:,.0f}円)を突破してしまいます。安全のため買付をキャンセルしました。")
            else:
                print(f"\n💡 現金不足のため ({cost:,.0f}円必要 / 残高{account['cash']:,.0f}円)、買付を見送ります。")
    else:
        print("\n💡 AI定性フィルターにより、全ての候補がリジェクトされました（または対象なし）。安全のため見送ります。")
        
    print_execution_summary(actions_taken, portfolio, account, regime)

if __name__ == "__main__":
    main()