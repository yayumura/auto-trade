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

warnings.filterwarnings('ignore')

# --- 1. 環境設定（文字コード・パスの絶対指定） ---
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data_j.csv')
PORTFOLIO_FILE = os.path.join(BASE_DIR, 'virtual_portfolio.csv')

# --- 2. AI・トレード設定 ---
GEMINI_API_KEY = "ここにAPIキーを入力"  # 【重要】APIキーを入力してください

# APIキー未設定のチェック
if GEMINI_API_KEY == "ここにAPIキーを入力":
    print("⚠️ エラー: GEMINI_API_KEY が設定されていません。コード内の設定箇所にAPIキーを入力してください。")
    sys.exit()

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = "gemini-2.5-flash"  # 最新・高速モデル

# シミュレーション用の初期資金設定
INITIAL_CASH = 1000000

def get_recent_news(code, name):
    """プロBOT機能: ニュースAI・テーマ株判定のための情報収集"""
    clean_name = re.sub(r'\s+', ' ', name).strip()
    query = urllib.parse.quote(f"{code} {clean_name}")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        feed = feedparser.parse(rss_url)
        titles = [entry.title for entry in feed.entries[:5]]  # 直近5件
        return " | ".join(titles) if titles else "関連ニュースなし"
    except: 
        return "ニュース取得エラー"

def calculate_technicals(df):
    """① テクニカル拡張 & ④ ボラティリティ計算"""
    if len(df) < 50:
        return None
    
    # RSI (14期間)
    delta = df['Close'].diff()
    up = delta.clip(lower=0).ewm(span=14, adjust=False).mean()
    down = -1 * delta.clip(upper=0).ewm(span=14, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + up / down))
    
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # ボリンジャーバンド & スクイーズ判定用
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['STD20'] = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['SMA20'] + (df['STD20'] * 2)
    df['BB_Lower'] = df['SMA20'] - (df['STD20'] * 2)
    df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['SMA20'] # ボラ収縮検知用
    
    # ATR (アベレージ・トゥルー・レンジ)
    tr1 = df['High'] - df['Low']
    tr2 = abs(df['High'] - df['Close'].shift())
    tr3 = abs(df['Low'] - df['Close'].shift())
    df['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(window=14).mean()
    
    # VWAP (日中平均約定価格 - 15分足ベースの近似)
    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (df['Typical_Price'] * df['Volume']).cumsum() / df['Volume'].cumsum()

    return df

def scan_initial_breakout(df):
    """② 資金流入検知 & ③ トレンド検知の統合ロジック"""
    latest = df.iloc[-1]
    
    # 【資金流入検知】出来高急増 & 出来高加速度
    vol_mean_5 = df['Volume'].iloc[-6:-1].mean()
    vol_surge = latest['Volume'] > (vol_mean_5 * 3.0)  # 過去5期間の3倍の出来高
    
    # 【トレンド検知】ブレイクアウト (15分足を日足相当期間で計算)
    lookback_5d = min(100, len(df)-1)
    break_5d = latest['Close'] > df['High'].iloc[-(lookback_5d+1):-1].max()
    
    # 【ボラティリティ】スクイーズ(収縮)からのブレイク検知
    squeeze_condition = df['BB_Width'].iloc[-10:-1].mean() < 0.05 # バンド幅が狭い状態
    volatility_expansion = latest['BB_Width'] > df['BB_Width'].iloc[-2] # 急拡大
    
    # 「出来高急増」かつ「スクイーズからのブレイク or 高値更新」を初動と判定
    is_hot = vol_surge and (break_5d or (squeeze_condition and volatility_expansion))
    
    tech_data = {
        "RSI": latest['RSI'],
        "MACD": latest['MACD'],
        "Signal": latest['Signal'],
        "VolSurge": vol_surge,
        "SqueezeBreak": squeeze_condition and volatility_expansion,
        "Breakout": break_5d
    }
    
    return is_hot, tech_data

def ai_scoring(code, name, tech, news_text):
    """⑤ AIスコア & ⑥ プロBOT拡張 (テーマ・決算・SNSトレンド判定)"""
    prompt = f"""
    あなたは機関投資家レベルの株価予測AIです。以下の情報から、銘柄の「直近の急騰確率(スコア)」を 1〜100 の数値で評価してください。
    
    【銘柄】 {name} ({code})
    
    【テクニカル指標 (初動検知ツールより)】
    RSI: {tech['RSI']:.1f}
    MACD/シグナル: {tech['MACD']:.2f} / {tech['Signal']:.2f}
    資金流入(出来高急増): {'発生中' if tech['VolSurge'] else 'なし'}
    ボラティリティ・ブレイク: {'発生中' if tech['SqueezeBreak'] else 'なし'}
    直近高値ブレイク: {'発生中' if tech['Breakout'] else 'なし'}
    
    【最新ニュース・テーマ株判定】
    {news_text}
    
    【判定基準】
    - 「AI、半導体、防衛、量子、宇宙、バイオ」などの強力なテーマ資金流入があるか？
    - 決算のサプライズイベントや、SNSで話題になりやすい材料が含まれているか？
    - テクニカルな初動シグナルとファンダメンタルズが合致しているか？
    
    【出力ルール】
    1行目: スコア（例: 88）
    2行目: 判定理由（簡潔に100文字以内の日本語で）
    """
    try:
        response = client.models.generate_content(model=MODEL_ID, contents=prompt)
        lines = response.text.strip().split('\n')
        score = int(re.sub(r'\D', '', lines[0]))
        reason = lines[1] if len(lines) > 1 else "詳細理由なし"
        return score, reason
    except Exception as e:
        return 0, f"AI評価エラー"

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚀 東証最強BOT 高速スキャン開始")
    
    # data_j.csvから銘柄リストを取得
    try:
        df_symbols = pd.read_csv(DATA_FILE)
        # 15分以内の実行を担保するため、プライム市場とスタンダードなど流動性の高い銘柄へ絞り込み
        targets = df_symbols[df_symbols['市場・商品区分'].str.contains('プライム|スタンダード', na=False)]['コード'].astype(str).tolist()
        targets = targets[:200]  # 検証用にサンプリング
    except Exception as e:
        print(f"⚠️ 銘柄リスト読み込みエラー: {e}")
        return

    hot_candidates = []
    tickers = [f"{code}.T" for code in targets]
    
    print(f"--- 15分足データ一括ダウンロード (対象: {len(tickers)}銘柄) ---")
    
    # 修正箇所: show_errors を削除
    data = yf.download(tickers, period="5d", interval="15m", group_by='ticker', threads=True)
    
    # 修正箇所: データが空の場合のクラッシュ回避（休場日など）
    if data is None or data.empty:
        print("💡 株価データを取得できませんでした。休場日、もしくは通信状況を確認してください。")
        return

    for code in targets:
        ticker = f"{code}.T"
        try:
            # 修正箇所: yfinanceの取得結果構造のブレに強いデータ抽出方法に変更
            if isinstance(data.columns, pd.MultiIndex):
                if ticker not in data.columns.levels[0]: continue
                df = data[ticker].dropna()
            else:
                if len(targets) == 1 or ticker == data.columns.name:
                    df = data.dropna()
                else:
                    continue
            
            # データ件数が少ない場合はスキップ
            if df.empty or len(df) < 50:
                continue

            df = calculate_technicals(df)
            if df is None: continue
            
            # 初動シグナル検知
            is_hot, tech_data = scan_initial_breakout(df)
            
            if is_hot:
                name_row = df_symbols[df_symbols['コード'].astype(str) == code]
                name = name_row['銘柄名'].values[0] if not name_row.empty else "不明"
                print(f"🔥 初動検知: {code} {name} (出来高急増)")
                
                news = get_recent_news(code, name)
                hot_candidates.append({
                    "code": code,
                    "name": name,
                    "tech": tech_data,
                    "news": news
                })
        except Exception as e:
            # 個別銘柄のエラーは止まらずにスキップ
            continue

    if not hot_candidates:
        print("💡 現在の15分足で急騰初動シグナルを満たす銘柄はありません。")
        return

    print(f"\n--- 🤖 AIスコアリング & ランキング (候補: {len(hot_candidates)}銘柄) ---")
    scored_list = []
    for item in hot_candidates:
        score, reason = ai_scoring(item['code'], item['name'], item['tech'], item['news'])
        item['ai_score'] = score
        item['ai_reason'] = reason
        scored_list.append(item)
        print(f"[{item['code']} {item['name']}] AIスコア: {score}点 | 理由: {reason}")
        time.sleep(2) # APIのレートリミット対策

    # スコアで降順ソート
    scored_list = sorted(scored_list, key=lambda x: x['ai_score'], reverse=True)
    
    best = scored_list[0]
    if best['ai_score'] >= 80:
        print(f"\n🏆 【シミュレーション買付発動】最強銘柄確定: {best['code']} {best['name']}")
        print(f"判定理由: {best['ai_reason']}")
        # ※ ここにポートフォリオ(virtual_portfolio.csv)への書込処理を追加することで自動売買化
    else:
        print("\n💡 エントリー基準(AIスコア80以上)を満たす強力なテーマ株はありませんでした。ホールド(見送り)します。")

if __name__ == "__main__":
    main()