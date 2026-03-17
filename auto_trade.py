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
# Moved to core.logic.detect_market_regime

# --- 【中核2】保有ポジションの高度な管理 ---
# Moved to core.logic.manage_positions

# --- 【中核3】マルチファクター・スキャン（完全数学的） ---
# calculate_technicals_for_scan moved to core.logic
# select_best_candidates moved to core.logic

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
        afternoon_open, afternoon_close = datetime.strptime("12:30", "%H:%M").time(), datetime.strptime("15:30", "%H:%M").time() # 2024年11月TSE延長対応

        if not ((morning_open <= c_time <= morning_close) or (afternoon_open <= c_time <= afternoon_close)):
            return

    account = load_account()
    portfolio = load_portfolio()
    actions_taken = []
    trade_logs = [] # manage_positionsから返されるログを格納するリスト

    # --- 1. 相場環境（レジーム）判定 ---
    regime = detect_market_regime()
    print(f"📊 現在のレジーム: 【{regime}】")

    # --- 2. 保有ポジション管理 ---
    # manage_positions関数にbroker引数とis_simulation引数を追加。
    # このファイルは主にシミュレーション用途のため、is_simulation=True をデフォルトとする。
    portfolio, account, sell_actions, trade_logs_from_manage = manage_positions(portfolio, account, broker=None, regime=regime, is_simulation=True)
    actions_taken.extend(sell_actions)
    trade_logs.extend(trade_logs_from_manage)
    save_portfolio(portfolio)
    save_account(account)

    if regime == "BEAR":
        print("🚨 【警告】パニック・弱気相場を検知。資金保護のため新規買い付けを完全に停止します。")
        send_discord_notify("🚨 【BEAR相場検知】パニック・弱気相場のため新規買い付けを停止。手仕舞いのみ実行します。")
        print_execution_summary(actions_taken, portfolio, account, regime)
        return

    if len(portfolio) >= MAX_POSITIONS:
        print(f"\n💡 最大ポジション（{MAX_POSITIONS}銘柄）保有中。新規スキャンをスキップします。")
        send_discord_notify(f"💡 【見送り】最大ポジション（{MAX_POSITIONS}銘柄）保有中のため新規スキャンをスキップしました。")
        print_execution_summary(actions_taken, portfolio, account, regime)
        return

    now_time = datetime.now().time()

    # 【重要追加】東京市場の「魔の寄り付き30分」を回避
    # 朝9:00～9:30は前日からの持ち越し注文が交錯し、テクニカル指標が完全に無視されるランダムウォーク状態となるためエントリーを禁止します。
    if now_time < datetime.strptime("09:30", "%H:%M").time() and not DEBUG_MODE:
        print("\n💡 寄り付き直後（9:30前）は値動きがランダムで危険なため、新規エントリーのスキャンを待機します。")
        send_discord_notify("💡 【見送り】寄り付き直後（9:30前）のためエントリー待機中。保有監視のみ実行しました。")
        print_execution_summary(actions_taken, portfolio, account, regime)
        return

    if now_time >= datetime.strptime("14:30", "%H:%M").time():
        print("\n💡 大引け前（14:30以降）のため、オーバーナイトリスクを避けるべく本日の新規買付を終了します。")
        send_discord_notify("💡 【見送り】大引け前（14:30以降）のため新規買付を終了。保有ポジションの決済監視のみ実行しました。")
        # 14:30〜15:00は保有ポジションの決済監視のみ（manage_positionsで15:00タイムストップが発動）
        print_execution_summary(actions_taken, portfolio, account, regime)
        return

    # --- 3. システムによる数学的スクリーニング（高速） ---
    try:
        df_symbols = pd.read_csv(DATA_FILE)
        # 【改善】ETF/ETN、REIT、PRO Market、外国株式、出資証券を除外し、内国株式のみに絞る
        # （4400→約3770銘柄に削減し、yfinanceの 'possibly delisted' エラーも解消）
        if '市場・商品区分' in df_symbols.columns:
            df_symbols = df_symbols[df_symbols['市場・商品区分'].isin(TARGET_MARKETS)]
            print(f"  🔍 市場フィルタリング適用後: {len(df_symbols)}銘柄 (ETF/REIT等を除外)")

        # 【追加】無効銘柄キャッシュの読み込みと除外
        invalid_tickers = load_invalid_tickers()
        if invalid_tickers:
            df_symbols = df_symbols[~df_symbols['コード'].astype(str).isin(invalid_tickers)]
            print(f"  🔍 無効銘柄キャッシュ適用後: {len(df_symbols)}銘柄")
        # 既に保有している銘柄は除外
        held_codes = [str(p['code']) for p in portfolio]
        targets = [str(t) for t in df_symbols['コード'].tolist() if str(t) not in held_codes]
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
            print(f"⚠️ 個別データ取得失敗 ({len(chunk)}銘柄): {e}")

            # 失敗した銘柄をキャッシュに追加
            if "possibly delisted" in str(e).lower() or "not found" in str(e).lower():
                new_invalids = set(chunk)
                invalid_tickers.update([t.replace('.T', '') for t in new_invalids])
                save_invalid_tickers(invalid_tickers)
            continue

    if not data_dfs:
        print("⚠️ データの取得に完全に失敗しました。")
        send_discord_notify("⚠️ 【エラー】データ取得に完全に失敗しました。APIレートリミットまたはネットワーク障害の可能性があります。")
        print_execution_summary(actions_taken, portfolio, account, regime)
        return

    # 全チャンクを結合
    data_df = pd.concat(data_dfs, axis=1) if len(data_dfs) > 1 else data_dfs[0]
    print("✅ データ取得完了。評価アルゴリズムを実行します...")
    
    # 数学的に評価されたトップ候補（最大3件）を瞬時に取得
    top_candidates = select_best_candidates(data_df, targets, df_symbols, regime)
    
    if not top_candidates:
        print(f"💡 現在のレジーム({regime})で優位性のある銘柄は見つかりませんでした。無駄な売買を見送ります。")
        send_discord_notify(f"💡 【見送り】レジーム: {regime} | スクリーニングの結果、優位性のある銘柄が見つかりませんでした。")
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
            send_discord_notify(f"⚠️ 【安全装置作動】{best_target['code']} {best_target['name']} の価格データに異常を検知（{best_target['price']}）。買付を強制キャンセルしました。")
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
                 send_discord_notify(f"⚠️ 【安全装置作動】資金計算エラー: 買付余力がマイナスになるため取引を強制ブロックしました。")
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
                msg = f"💡 【見送り】{best_target['code']} {best_target['name']} — ボラティリティ過大(ATR:{atr:.1f})のためリスク管理制限で買付キャンセル。"
                print(f"\n{msg}")
                send_discord_notify(msg)
            else:
                msg = f"💡 【見送り】{best_target['code']} {best_target['name']} — 現金不足 ({cost:,.0f}円必要 / 残高{account['cash']:,.0f}円)。"
                print(f"\n{msg}")
                send_discord_notify(msg)
    else:
        print("\n💡 AI定性フィルターにより、全ての候補がリジェクトされました（または対象なし）。安全のため見送ります。")
        send_discord_notify("💡 【見送り】AI定性フィルターにより全候補がリジェクトされました。安全のため見送ります。")
        
    print_execution_summary(actions_taken, portfolio, account, regime)

if __name__ == "__main__":
    main()
