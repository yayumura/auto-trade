import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

import json
import os
import time
from core.config import (
    ATR_STOP_LOSS, RANGE_ATR_STOP_LOSS, ATR_TRAIL, TAX_RATE, EXCLUSION_CACHE_FILE, JST,
    MIN_VOLUME_SURGE, ATR_TARGET_MULT, ATR_STOP_MULT, BREAKEVEN_TRIGGER, TRAIL_STOP_MULT,
    MIN_MOMENTUM_THRESHOLD
)
from core.log_setup import send_discord_notify
from core.file_io import atomic_write_json, safe_read_json
from core.utils import calculate_effective_age
from collections import deque

# --- [Phase 2] リアルタイム・データバッファ管理 ---
class RealtimeBuffer:
    """
    yfinance の過去データ(15分足等)に、カブコムのリアルタイムTickを
    シームレスに結合して最新のOHLCVを生成・保持するバッファ。
    """
    def __init__(self, code, history_df, interval_mins=15):
        self.code = code
        self.interval_mins = interval_mins
        # 過去データを保持
        if isinstance(history_df.columns, pd.MultiIndex):
            ticker = f"{code}.T"
            self.df = history_df[ticker].dropna().copy() if ticker in history_df.columns.levels[0] else pd.DataFrame()
        else:
            self.df = history_df.copy()
            
        # インデックスをJSTに統一
        if not self.df.empty and self.df.index.tzinfo is None:
            self.df.index = self.df.index.map(lambda x: x.replace(tzinfo=JST) if x.tzinfo is None else x)
            
        self.last_tick_time = None
        self.last_total_volume = None # カブコム由来の当日累積出来高の前回値を保持
        self.last_update_time = None # [Professional Audit] 鮮度監視用

    def update(self, price, total_volume, timestamp, current_time_override=None):
        """ カブコムAPIの現在値(Tick)でバッファを更新または新規行追加 """
        self.last_update_time = current_time_override or datetime.now(JST) # 更新時刻を記録
        if price is None or price <= 0: return self.df
        
        # 出来高の増分（デルタ）を計算
        delta_volume = 0
        if self.last_total_volume is not None:
            if total_volume >= self.last_total_volume:
                delta_volume = total_volume - self.last_total_volume
            else:
                # [Professional Audit] ボリュームのリセット（日付変更等）を検知
                delta_volume = total_volume
        else:
            # [Professional Audit] 初期化直後は現在値をそのまま増分とする（寄付き対応）
            delta_volume = total_volume
        self.last_total_volume = total_volume

        # タイムスタンプをインターバルの開始時刻に切り捨てる
        current_dt = timestamp
        minute_offset = current_dt.minute % self.interval_mins
        bar_start = current_dt.replace(minute=current_dt.minute - minute_offset, second=0, microsecond=0)
        
        if self.df.empty:
            new_row = pd.DataFrame([{
                'Open': price, 'High': price, 'Low': price, 'Close': price, 'Volume': delta_volume
            }], index=[bar_start])
            self.df = new_row
            return self.df
        
        # [Professional Audit] OS時刻の揺らぎ（NTP同期等）によるインデックス逆転を防止
        bar_start = max(bar_start, self.df.index[-1])

        if bar_start in self.df.index:
            # 既存の最新足を更新
            idx = bar_start
            self.df.at[idx, 'High'] = max(self.df.at[idx, 'High'], price)
            self.df.at[idx, 'Low'] = min(self.df.at[idx, 'Low'], price)
            self.df.at[idx, 'Close'] = price
            self.df.at[idx, 'Volume'] += delta_volume # 増分を加算
        else:
            # 新しい足を追加
            new_row = pd.DataFrame([{
                'Open': price, 'High': price, 'Low': price, 'Close': price, 'Volume': delta_volume
            }], index=[bar_start])
            self.df = pd.concat([self.df, new_row])
            if len(self.df) > 500:
                self.df = self.df.iloc[-500:]
                
        return self.df

    def get_df(self):
        return self.df

    def is_stale(self, max_seconds=3600, current_time_override=None):
        """ [Professional Audit] データの鮮度を確認。一定時間更新がない場合は True """
        if current_time_override: return False # バックテスト時は鮮度チェックをスキップ
        if not self.last_update_time: return True
        return (datetime.now(JST) - self.last_update_time).total_seconds() > max_seconds

def normalize_tick_size(price: float, is_buy: bool) -> int:
    """
    東証の呼値ルールに合わせて指値価格を安全かつ有効な価格に丸める。
    """
    p = float(price)
    tick = get_tick_size(p)
    
    if is_buy:
        # 買付：指定価格以上の最小の呼値（切り上げ）
        return int((p + tick - 0.0001) // tick * tick)
    else:
        # 売却：指定価格以下の最大の呼値（切り捨て）
        return int(p // tick * tick)

def get_tick_size(price: float) -> float:
    """ [Professional Audit] 2024年現在の東証標準呼値（非TOPIX100銘柄用） """
    p = float(price)
    if p <= 3000: return 1.0
    if p <= 5000: return 5.0
    if p <= 10000: return 10.0
    if p <= 30000: return 50.0
    if p <= 50000: return 100.0
    if p <= 100000: return 500.0
    if p <= 1000000: return 1000.0
    return 5000.0

# --- 【中核1】レジーム（地合い）認識 ---
def detect_market_regime(broker=None, buffer=None, current_time_override=None, verbose=True):
    """
    市場の地合い（Regime）を推定する。
    """
    etf_ticker = '1321.T'
    try:
        # ヒストリカルデータ（日足）を取得してSMA20を計算
        if buffer is not None and not buffer.df.empty:
            close_daily_all = buffer.df['Close'].resample('B').last().ffill().dropna()
            
            if len(close_daily_all) < 20:
                if current_time_override:
                    nk = pd.DataFrame(close_daily_all)
                    data_source_base = "RealtimeBuffer (Backtest)"
                else:
                    nk = yf.download(etf_ticker, period="1mo", interval="1d", threads=False, progress=False)
                    data_source_base = "yfinance (Daily)"
            else:
                nk = pd.DataFrame(close_daily_all)
                data_source_base = "RealtimeBuffer"
        else:
            if current_time_override:
                return "RANGE" 
            nk = yf.download(etf_ticker, period="1mo", interval="1d", threads=False, progress=False)
            data_source_base = "yfinance (Daily)"

        if nk is None or nk.empty:
            return "RANGE"
            
        if isinstance(nk.columns, pd.MultiIndex):
            nk.columns = nk.columns.droplevel('Ticker')
            
        price_col = 'Adj Close' if 'Adj Close' in nk.columns else 'Close'
        close_daily = nk[price_col].dropna()

        if len(close_daily) < 20:
            return "RANGE"
        
        sma20 = float(close_daily.rolling(window=20).mean().iloc[-1])
        
        current = float(close_daily.iloc[-1])
        data_source = data_source_base

        if broker and hasattr(broker, 'get_board_data'):
            board = broker.get_board_data(['1321'])
            b_info = board.get('1321')
            if b_info and b_info.get('price') and b_info.get('price') > 0:
                current = float(b_info['price'])
                data_source = "Kabucom API (Real-time)"
            elif b_info and b_info.get('bid') and b_info.get('ask'):
                current = (float(b_info['bid']) + float(b_info['ask'])) / 2
                data_source = "Kabucom API (Mid)"

        temp_close = close_daily.copy()
        if "Kabucom" in data_source:
            now_jst = current_time_override or datetime.now(JST)
            today_date = now_jst.date()
            
            if temp_close.index[-1].date() < today_date:
                new_ts = pd.Timestamp(today_date)
                if temp_close.index.tzinfo is not None:
                    new_ts = new_ts.tz_localize(temp_close.index.tzinfo)
                temp_close[new_ts] = current
            else:
                temp_close.iloc[-1] = current
        
        volatility = float(temp_close.pct_change().dropna().std()) * np.sqrt(252)

        if verbose:
            print(f"  [Regime] {etf_ticker}: 現在値={current:.1f} ({data_source}) SMA20={sma20:.1f} Vol={volatility:.2f}")

        if current < sma20 * 0.95 and volatility > 0.30:
            return "BEAR" 
        elif current > sma20:
            return "BULL"
        else:
            return "RANGE"

    except Exception as e:
        if verbose:
            print(f"[RE-C-ERR] 地合い認識中にエラー: {e}")
        return "RANGE"

# --- 【補助】無効銘柄キャッシュ管理 ---
def load_invalid_tickers():
    return set(safe_read_json(EXCLUSION_CACHE_FILE, default=[]))

def save_invalid_tickers(invalid_set):
    try:
        atomic_write_json(EXCLUSION_CACHE_FILE, list(invalid_set))
    except Exception as e:
        print(f"[Error] キャッシュ保存エラー: {e}")

# --- 【中核2】保有ポジションの高度な管理 ---
def manage_positions(portfolio: list, account: dict, broker, regime: str = "RANGE", is_simulation: bool = True, realtime_buffers: dict = None, current_time_override=None, verbose=True, delay_sim_execution=False):
    """
    保有株式の利確・損切判定し、売却処理を行う。
    """
    actions = []
    trade_logs = []
    
    if not portfolio:
        return portfolio, account, actions, trade_logs

    if verbose:
        print(f"\n--- [Portfolio] 保有監視 ({len(portfolio)}銘柄) ---")
    
    data_map = {} 
    
    tickers_to_download = []
    for p in portfolio:
        code = str(p['code'])
        if realtime_buffers and code in realtime_buffers:
            data_map[code] = realtime_buffers[code].get_df()
        else:
            tickers_to_download.append(f"{code}.T")

    if tickers_to_download:
        try:
            downloaded = yf.download(tickers_to_download, period="5d", interval="1d", group_by='ticker', threads=False, progress=False)
            if not downloaded.empty:
                for t in tickers_to_download:
                    code = t.replace(".T", "")
                    if isinstance(downloaded.columns, pd.MultiIndex):
                        data_map[code] = downloaded[t].dropna()
                    else:
                        data_map[code] = downloaded.dropna()
        except Exception as e:
            if verbose:
                print(f"[WARNING] 保有銘柄のデータ取得に失敗: {e}")

    if not data_map:
        if verbose:
            print("[WARNING] 判定用のデータが取得できませんでした")
        return portfolio, account, actions, trade_logs

    remaining_portfolio = []
    now_dt = current_time_override or datetime.now(JST)
    current_time = now_dt.strftime('%Y-%m-%d %H:%M:%S')

    for p in portfolio:
        code = str(p['code'])
        try:
            if code not in data_map:
                remaining_portfolio.append(p)
                continue
            df = data_map[code]
            
            if df.empty or len(df) < 20: 
                remaining_portfolio.append(p)
                continue
            
            df = calculate_technicals_for_scan(df)
            if df is None or 'ATR' not in df.columns:
                remaining_portfolio.append(p)
                continue

            split_ratio = 1.0
            if is_simulation and 'Adj Close' in df.columns and float(df['Close'].iloc[0]) > 0:
                split_ratio = float(df['Adj Close'].iloc[0]) / float(df['Close'].iloc[0])
                if split_ratio > 1.0: split_ratio = 1.0 

            if split_ratio < 0.99 and not p.get('split_adjusted'):
                original_shares = int(p.get('shares', 0))
                p['shares'] = int(original_shares / split_ratio)
                p['split_adjusted'] = True 
                if verbose:
                    print(f"🔄 [{code}] 株式分割を検知: {original_shares}株 -> {p['shares']}株 に価格と共に補正しました。")

            current_shares = int(p['shares'])
            buy_price = float(p.get('buy_price', 0)) * split_ratio
            highest_price_db = float(p.get('highest_price', buy_price)) * split_ratio

            api_price = p.get('current_price')
            if not is_simulation and api_price is not None and api_price > 0:
                current_price_raw = float(api_price)
                open_price = current_price_raw
                high_price = current_price_raw
                low_price = current_price_raw
            else:
                current_price_raw = float(df['Close'].iloc[-1])
                open_price = float(df['Open'].iloc[-1])
                high_price = float(df['High'].iloc[-1])
                low_price = float(df['Low'].iloc[-1])
                
            atr = float(df['ATR'].iloc[-1]) if not pd.isna(df['ATR'].iloc[-1]) else current_price_raw * 0.05
            low_10 = float(df['Low_10'].iloc[-1]) if 'Low_10' in df.columns and not pd.isna(df['Low_10'].iloc[-1]) else buy_price * 0.9

            if is_simulation:
                tick_size = get_tick_size(current_price_raw)
                slippage = max(tick_size, atr * 0.01) 
                current_price = max(0.1, current_price_raw - slippage)
            else:
                slippage = 0
                current_price = current_price_raw
            
            profit_pct = (current_price - buy_price) / buy_price if buy_price > 0 else 0

            sell_reason = None
            sell_qty = current_shares

            # ==========================================
            # フェーズ22: ドンチャン・エグジット（損小利大の極み）
            # ==========================================
            
            # 1. 初期損切り（リスク固定）
            # エントリー価格からATRの2.0倍下がったら、ブレイクアウト失敗とみなして即撤退
            initial_stop = buy_price - (atr * 2.0)
            
            if is_simulation and open_price <= initial_stop:
                sell_reason = f"窓開け損切 (Open {open_price:,.1f} <= Stop {initial_stop:,.1f})"
                current_price_raw = open_price 
                current_price = max(low_price, open_price - slippage)
            elif current_price <= initial_stop:
                sell_reason = f"ブレイクアウト失敗 / 絶対損切 (Stop at {initial_stop:,.1f})"

            # 2. トレンド終了利確（10日安値割れ）
            # 株価が過去10日間の最安値を下回ったら、上昇トレンドが終わったとみなして利益確定
            elif current_price < low_10:
                if current_price > buy_price:
                    sell_reason = f"トレンド終了・大波利確 (Low10 Break at {low_10:,.1f})"
                else:
                    sell_reason = f"トレンド終了・微損撤退 (Low10 Break at {low_10:,.1f})"

            if not sell_reason:
                new_highest = max(highest_price_db, current_price) / split_ratio if split_ratio > 0 else max(highest_price_db, current_price)
                p['highest_price'] = round(new_highest, 1)
                remaining_portfolio.append(p)
            else:
                # 実行フェーズ
                price_final = current_price
                qty_final = sell_qty
                
                if not is_simulation:
                    broker.send_order(code, "SELL", qty_final, price_final)
                
                gross_profit = (price_final - buy_price) * qty_final
                tax = max(0, gross_profit * TAX_RATE) if gross_profit > 0 else 0
                net_profit = gross_profit - tax
                
                if not delay_sim_execution:
                    account['cash'] += (price_final * qty_final) - tax
                
                log_entry = {
                    "time": current_time,
                    "code": code,
                    "name": p.get('name', '不明'),
                    "action": "SELL",
                    "shares": qty_final,
                    "price": price_final,
                    "profit": net_profit,
                    "profit_pct": f"{profit_pct:.2%}",
                    "reason": sell_reason,
                    "atr": atr, 
                    "buy_price": buy_price 
                }
                trade_logs.append(log_entry)
                
                if verbose:
                    print(f"  [SELL] {code} {p.get('name')} x{qty_final} @ {price_final:,.1f} ({profit_pct:+.2%}) [{sell_reason}]")
                
                if not is_simulation:
                    send_discord_notify(f"【売却】{code} {p.get('name')}\n価格: {price_final:,.1f}\n損益: {net_profit:,.0f} ({profit_pct:+.2%})\n理由: {sell_reason}")

        except Exception as e:
            if verbose:
                print(f"[RE-P-ERR] {code} の判定中にエラー: {e}")
            remaining_portfolio.append(p)

    return remaining_portfolio, account, actions, trade_logs

# --- 【中核3】銘柄スキャン＆期待値評価 ---
def select_best_candidates(data_df: pd.DataFrame, targets: list, df_symbols=None, regime: str = "RANGE", is_simulation: bool = True, realtime_buffers: dict = None, current_time_override=None, verbose=True):
    """
    複数銘柄からテクニカル分析を行い、スコアの高い上位3銘柄を返す。
    """
    candidates = []
    
    data_map = {}
    is_multi = isinstance(data_df.columns, pd.MultiIndex) if data_df is not None and not data_df.empty else False
    
    # --- フェーズ17: マクロ（全体相場）のレジーム・フィルター（Risk-Off判定） ---
    df_1321 = None
    if realtime_buffers and '1321' in realtime_buffers:
        df_1321 = realtime_buffers['1321'].get_df()
    elif is_multi and '1321.T' in data_df.columns.get_level_values(0):
        df_1321 = data_df['1321.T'].dropna()
        
    nk_risk_off = False
    if df_1321 is not None and len(df_1321) >= 200:
        nk_sma100 = df_1321['Close'].rolling(window=100).mean().iloc[-1]
        nk_sma200 = df_1321['Close'].rolling(window=200).mean().iloc[-1]
        nk_close = df_1321['Close'].iloc[-1]
        if pd.notna(nk_sma100) and pd.notna(nk_sma200) and pd.notna(nk_close):
            if nk_close < nk_sma100 or nk_close < nk_sma200:
                nk_risk_off = True

    if nk_risk_off:
        if verbose:
            print("[Regime] Risk-Off Mode: Nikkei 1321 (Close < SMA100 or SMA200). Skipping ALL entries.")
        return []
    # -------------------------------------------------------------------------
    for code_item in targets:
        code = str(code_item)
        if realtime_buffers and code in realtime_buffers:
            data_map[code] = realtime_buffers[code].get_df()
        elif data_df is not None and not data_df.empty:
            ticker = f"{code}.T"
            if is_multi:
                if ticker in data_df.columns.get_level_values(0):
                    data_map[code] = data_df[ticker].dropna()
            else:
                if len(targets) == 1:
                    data_map[code] = data_df.dropna()

    for code_item in targets:
        code = str(code_item)
        try:
            df = data_map.get(code)
            if df is None or df.empty:
                continue
            
            df = calculate_technicals_for_scan(df)
            if df is None or len(df) < 20:
                continue
            
            latest = df.iloc[-1]

            # ==========================================
            # フェーズ22: 日足ブレイクアウト・エントリー
            # ==========================================
            close_price = latest.get('Close')
            sma50 = latest.get('SMA50')
            sma200 = latest.get('SMA200')
            high_20 = latest.get('High_20')

            if pd.isna(sma50) or pd.isna(sma200) or pd.isna(high_20) or pd.isna(close_price):
                if verbose:
                    print(f"  [Scan] {code}: Not enough data for indicators")
                continue

            score = 0
            reason = "Unknown"

            # 【資金管理フィルター】1単元30万円以下の銘柄に強制制限（100万円で複数分散するため）
            if close_price > 3000:
                reason = f"資金管理エラー (Price: {close_price:.1f} > 3000)"
                if verbose:
                    print(f"  [Scan] {code}: {reason}")
                continue

            # 【MTFフィルター】長期トレンドが上向きであること（パーフェクトオーダー）
            if not (sma50 > sma200 and close_price > sma200):
                reason = "MTF Downtrend Rejection (SMA50 <= SMA200 or Close <= SMA200)"
                if verbose:
                    print(f"  [Scan] {code}: {reason}")
                continue

            # 【トリガー】今日の終値が、過去20日間の最高値をブレイクアウトしたか
            if close_price > high_20:
                # ブレイクアウトの勢い（乖離率）をスコア化
                score = (close_price / high_20) * 100 
                reason = f"Breakout 20-Day High (Price: {close_price:.1f} > High20: {high_20:.1f})"
            else:
                reason = f"ブレイクアウト未確認 (Price: {close_price:.1f} <= High20: {high_20:.1f})"

            if score > 0:
                name = "不明"
                if df_symbols is not None:
                    name_row = df_symbols[df_symbols['コード'].astype(str) == code]
                    name = name_row['銘柄名'].values[0] if not name_row.empty else "不明"
                candidates.append({
                    "code": code, "name": name, 
                    "score": score, 
                    "price": latest['Close'], 
                    "atr": latest['ATR'],
                    "reason": reason
                })
                if verbose:
                    print(f"  [Scan] {code}: {reason} (Score: {score:.1f})")
            elif verbose:
                print(f"  [Scan] {code}: {reason}")

        except Exception as e:
            if verbose:
                print(f"[WARNING] [Scan] {code} の評価中にエラーが発生しスキップします: {type(e).__name__}: {e}")
            continue
            
    return sorted(candidates, key=lambda x: x['score'], reverse=True)[:3]

def calculate_technicals_for_scan(df):
    """ スキャンおよび保有ポジ監視用のテクニカル指標一括計算 """
    if df is None or len(df) < 20: return None
    df = df.copy()
    
    # 出来高の移動平均（20本分）
    df['Avg_Vol_15m'] = df['Volume'].rolling(window=20).mean()
    
    # RSI (14)
    delta = df['Close'].diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ema_up = up.ewm(com=13, adjust=False).mean()
    ema_down = down.ewm(com=13, adjust=False).mean()
    rs = ema_up / ema_down
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # SMA (20, 50, 100, 200, 400)
    df['SMA5'] = df['Close'].rolling(window=5).mean()
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['SMA100'] = df['Close'].rolling(window=100).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean()
    df['SMA400'] = df['Close'].rolling(window=400).mean()
    
    # --- フェーズ22: ブレイクアウト指標（ドンチャン・チャネル）の追加 ---
    # 過去20日間の最高値（前日まで。ルックアヘッド・バイアス防止のためshift(1)）
    df['High_20'] = df['High'].rolling(window=20).max().shift(1)
    # 過去10日間の最安値（前日まで。ルックアヘッド・バイアス防止のためshift(1)）
    df['Low_10'] = df['Low'].rolling(window=10).min().shift(1)
    
    # ATR (14)
    tr1 = df['High'] - df['Low']
    tr2 = abs(df['High'] - df['Close'].shift())
    tr3 = abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()
    df['ATR'] = df['ATR'].ffill().fillna(df['Close'] * 0.02) # 安全策
    df['ATR'] = df['ATR'].clip(lower=1.0) # 0回避
    
    return df