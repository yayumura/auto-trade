import yfinance as yf
import pandas as pd
from google import genai
import feedparser
import urllib.parse
from datetime import datetime
import sys
import io
import time
import os
import re
import logging

# --- 1. 環境設定：文字コードとノイズを完全に制御 ---
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# --- 2. ファイルパスの絶対指定（実行場所のズレを防止） ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE = os.path.join(BASE_DIR, 'virtual_portfolio.csv')
ASSET_LOG_FILE = os.path.join(BASE_DIR, 'daily_assets.csv')
AI_LOG_FILE = os.path.join(BASE_DIR, 'ai_decision_log.txt')

# --- 3. AI・トレード設定 ---
GEMINI_API_KEY = "キーをここに入力"  # 【重要】実際のAPIキーを必ずここに入れてください
client = genai.Client(api_key=GEMINI_API_KEY)
# 【重要】404エラー対策：最新仕様のモデル名
MODEL_ID = "models/gemini-1.5-flash"

INITIAL_CASH = 1000000
TAX_RATE = 0.20315
HARD_STOP_LOSS = 0.93  # -7%で強制損切

def get_recent_news(code, name):
    """Googleニュースから最新情報を抽出"""
    clean_name = re.sub(r'\s+', ' ', name).strip()
    query = urllib.parse.quote(f"{code} {clean_name}")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        feed = feedparser.parse(rss_url)
        titles = [entry.title for entry in feed.entries[:3]]
        return " | ".join(titles) if titles else "関連ニュースなし"
    except: return "ニュース取得エラー"

def ai_judge_exit(name, code, current_profit_ratio, news_text):
    """AIに出口判断を仰ぎ、日本語ログを確実に保存"""
    prompt = f"""
    Command: Decide to SELL or HOLD for the following stock.
    Stock: {name}({code})
    Current Profit: {current_profit_ratio:+.1%}
    Latest News: {news_text}
    Instructions:
    1. Reply 'SELL' or 'HOLD' at the first line.
    2. Provide a short reason in Japanese at the next line.
    """
    try:
        # 404対策済みのAPI呼び出し
        response = client.models.generate_content(model=MODEL_ID, contents=prompt)
        res_text = response.text.strip()
        
        # ログへの書き込み（asciiエラー対策のencoding='utf-8'）
        with open(AI_LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(f"--- {datetime.now()} ---\n{name}({code}): {res_text}\n\n")
            f.flush()
            
        decision = res_text.upper()
        # 画面表示用に1行目以降の理由部分を取得
        reason = res_text.split('\n')[-1][:40] if '\n' in res_text else res_text[:40]
        return "SELL" in decision, reason
    except Exception as e:
        return False, f"AI通信エラー: {str(e)[:15]}"

def execute_sell(df, idx, sell_price, reason_text):
    """売却処理：CSVを更新し、利益を確定"""
    buy_price = float(df.at[idx, '買値'])
    # 簡易シミュレーションとして1銘柄1株分を計算
    gross_p = sell_price - buy_price
    tax = max(0, gross_p * TAX_RATE) if gross_p > 0 else 0
    net_p = gross_p - tax
    
    df.at[idx, '状態'] = '売却済'
    df.at[idx, '売値'] = sell_price
    df.at[idx, '確定損益(税引後)'] = net_p
    df.at[idx, '売却理由'] = reason_text
    print(f"💰 【決済実行】{df.at[idx, '銘柄名']}: {reason_text} (損益: {net_p:,.0f}円)")

def manage_portfolio_hybrid():
    """保有銘柄のAI出口戦略チェック"""
    if not os.path.exists(PORTFOLIO_FILE): return
    
    # 区切り文字自動判別読み込み（タブ区切り対策）
    try:
        df = pd.read_csv(PORTFOLIO_FILE, sep=None, engine='python', encoding='utf-8-sig')
    except:
        df = pd.read_csv(PORTFOLIO_FILE, sep=None, engine='python', encoding='cp932')

    df.columns = df.columns.str.strip()
    df['状態'] = df['状態'].astype(str).str.strip()
    df['コード'] = df['コード'].astype(str).str.strip()
    active_mask = df['状態'].str.contains('保有', na=False)

    if not active_mask.any():
        print("📊 現在、保有銘柄はありません。")
        return

    print(f"\n--- AI出口戦略パトロール中 (対象: {active_mask.sum()}銘柄) ---")
    for idx, row in df[active_mask].iterrows():
        try:
            code_pure = str(row['コード']).split('.')[0]
            ticker = yf.Ticker(f"{code_pure}.T")
            hist = ticker.history(period="1d")
            if hist.empty: continue
            
            curr_p = hist['Close'].iloc[-1]
            buy_p = float(row['買値'])
            ratio = curr_p / buy_p
            
            print(f"🔍 {row['銘柄名']} を分析中... (株価: {curr_p:,.0f}円 / 損益: {ratio-1:+.1%})")
            
            # 1. 絶対防衛ライン（強制損切）
            if ratio <= HARD_STOP_LOSS:
                execute_sell(df, idx, curr_p, "絶対損切ライン到達")
                continue
            
            # 2. AIによる複合判断
            news = get_recent_news(code_pure, row['銘柄名'])
            should_sell, reason = ai_judge_exit(row['銘柄名'], code_pure, ratio-1, news)
            
            if should_sell:
                execute_sell(df, idx, curr_p, reason)
            else:
                print(f"  [維持] {row['銘柄名']}: {reason}")
        except Exception as e:
            print(f"  [エラー] {row['銘柄名']}: {e}")
    
    df.to_csv(PORTFOLIO_FILE, index=False, encoding='utf-8-sig')

def scan_and_buy_hybrid(master_df):
    """新規銘柄のAIエントリー判定"""
    all_codes = [f"{c}.T" for c in master_df['コード']]
    target_codes = all_codes[:1000] 
    print(f"\n--- AIエントリー判定スキャン中 ---")
    
    batch_size = 50
    new_buys = []
    for i in range(0, len(target_codes), batch_size):
        batch = target_codes[i:i+batch_size]
        try:
            data = yf.download(batch, period="2d", interval="15m", progress=False)
            if data.empty: continue
            close, vol = data['Close'], data['Volume']
            for code in batch:
                if code not in close.columns: continue
                p, v = close[code].dropna(), vol[code].dropna()
                if len(p) < 5: continue
                
                # 急騰・出来高急増を検知
                if (p.iloc[-1] / p.iloc[-2] > 1.005) and (v.iloc[-1] / v.iloc[-11:-1].mean() > 3.0):
                    pure_code = str(code).replace(".T", "")
                    info = master_df[master_df['コード'] == pure_code].iloc[0]
                    news = get_recent_news(pure_code, info['銘柄名'])
                    
                    # AIスコアリング（期待値を1-10で評価）
                    prompt = f"{info['銘柄名']}のニュース:{news}\n期待値を1-10で数字のみ回答。"
                    res = client.models.generate_content(model=MODEL_ID, contents=prompt)
                    score_match = re.search(r'\d+', res.text)
                    score = int(score_match.group()) if score_match else 5
                    
                    if score >= 8:
                        print(f"🚀 AI GO! スコア{score}: {info['銘柄名']}")
                        new_buys.append({
                            '購入日': datetime.now().strftime('%Y/%m/%d'),
                            'コード': pure_code, '銘柄名': info['銘柄名'], '業種': info['33業種区分'],
                            '買値': round(p.iloc[-1], 1), '状態': '保有', '売値': 0, 
                            '確定損益(税引後)': 0, '売却理由': ''
                        })
            time.sleep(1)
        except: continue
    
    if new_buys:
        df_new = pd.DataFrame(new_buys)
        if os.path.exists(PORTFOLIO_FILE):
            try:
                df_old = pd.read_csv(PORTFOLIO_FILE, sep=None, engine='python', encoding='utf-8-sig')
            except:
                df_old = pd.read_csv(PORTFOLIO_FILE, sep=None, engine='python', encoding='cp932')
            df_final = pd.concat([df_old, df_new], ignore_index=True)
        else: df_final = df_new
        df_final.to_csv(PORTFOLIO_FILE, index=False, encoding='utf-8-sig')

def record_daily_assets():
    """現在の総資産を計算して保存"""
    current_cash = INITIAL_CASH
    holding_value = 0
    if os.path.exists(PORTFOLIO_FILE):
        try:
            df = pd.read_csv(PORTFOLIO_FILE, sep=None, engine='python', encoding='utf-8-sig')
            # 数値列の強制変換
            df['確定損益(税引後)'] = pd.to_numeric(df['確定損益(税引後)'], errors='coerce').fillna(0)
            current_cash += df['確定損益(税引後)'].sum()
            
            active = df[df['状態'].astype(str).str.contains('保有')]
            for _, row in active.iterrows():
                try:
                    ticker = yf.Ticker(f"{row['コード']}.T")
                    curr = ticker.history(period="1d")['Close'].iloc[-1]
                    holding_value += curr
                except: pass
        except Exception as e:
            print(f"📊 資産計算中にエラー: {e}")
    
    total = current_cash + holding_value
    print(f"💰 総資産: {total:,.0f}円 (現金: {current_cash:,.0f} / 評価: {holding_value:,.0f})")
    
    # 資産推移ログを保存
    new_log = pd.DataFrame([{'日時': datetime.now().strftime('%Y-%m-%d %H:%M'), '総資産': total}])
    if os.path.exists(ASSET_LOG_FILE):
        log_df = pd.read_csv(ASSET_LOG_FILE, encoding='utf-8-sig')
        log_df = pd.concat([log_df, new_log], ignore_index=True)
    else: log_df = new_log
    log_df.to_csv(ASSET_LOG_FILE, index=False, encoding='utf-8-sig')

def load_master_data():
    """銘柄マスター(data_j.csv)の読み込み"""
    file_path = os.path.join(BASE_DIR, 'data_j.csv')
    try:
        try:
            df = pd.read_csv(file_path, encoding='utf-8-sig')
        except:
            df = pd.read_csv(file_path, encoding='cp932')
        df['コード'] = df['コード'].astype(str).str.strip()
        return df[['コード', '銘柄名', '33業種区分']]
    except:
        print("⚠️ data_j.csv の読み込みに失敗しました。")
        return pd.DataFrame()

if __name__ == "__main__":
    master = load_master_data()
    if not master.empty:
        manage_portfolio_hybrid()  # 1. 保有株のAI出口戦略
        scan_and_buy_hybrid(master) # 2. 新規銘柄のAI買い判定
        record_daily_assets()      # 3. 資産の自動記録
    print("\n=== AIハイブリッド運用・統合完全版 完了 ===")