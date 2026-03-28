import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

import json
import os
import time
from core.config import (
    ATR_STOP_LOSS, RANGE_ATR_STOP_LOSS, ATR_TRAIL, TAX_RATE, EXCLUSION_CACHE_FILE, JST,
    MIN_VOLUME_SURGE, ATR_TARGET_MULT, ATR_STOP_MULT, BREAKEVEN_TRIGGER, TRAIL_STOP_MULT
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
            if len(self.df) > 200:
                self.df = self.df.iloc[-200:]
                
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
    buffer が提供されている場合は、yfinance の代わりにリアルタイムバッファを使用する。
    """
    etf_ticker = '1321.T'
    try:
        # ヒストリカルデータ（日足）を取得してSMA20を計算
        if buffer is not None and not buffer.df.empty:
            # [Professional Audit] 15分足から日次ベースに変換する際、十分な履歴があるか確認
            # 不要時不要日(土日祝日)の欠欠を正しく補完するために、「'B'」(営業日のみ)リサンプリングを使用しffillする
            close_daily_all = buffer.df['Close'].resample('B').last().ffill().dropna()
            
            # 履歴が20日分に満たない場合は yfinance で補完を試みる（バックテスト時は外部通信を抑制）
            if len(close_daily_all) < 20:
                if current_time_override:
                    # バックテスト時は不足していても、ある分だけで計算する
                    nk = pd.DataFrame(close_daily_all)
                    data_source_base = "RealtimeBuffer (Backtest)"
                else:
                    print(f"[INFO] バッファの履歴不足 ({len(close_daily_all)}D < 20D)。yfinance で補完データを取得します。")
                    nk = yf.download(etf_ticker, period="1mo", interval="1d", threads=False, progress=False)
                    data_source_base = "yfinance (Daily)"
            else:
                nk = pd.DataFrame(close_daily_all)
                data_source_base = "RealtimeBuffer"
        else:
            if current_time_override:
                return "RANGE" # データがないバックテストは判定不可
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
        
        # --- [Phase 1.1] リアルタイム価格の取得 (Hybrid) ---
        current = float(close_daily.iloc[-1])
        data_source = data_source_base

        if broker and hasattr(broker, 'get_board_data'):
            # カブコムAPIから1321（ETF）の最良気配/現在値を取得
            board = broker.get_board_data(['1321'])
            b_info = board.get('1321')
            if b_info and b_info.get('price') and b_info.get('price') > 0:
                current = float(b_info['price'])
                data_source = "Kabucom API (Real-time)"
            elif b_info and b_info.get('bid') and b_info.get('ask'):
                # 現在値が0（寄付前など）の場合は、気配の仲値を採用
                current = (float(b_info['bid']) + float(b_info['ask'])) / 2
                data_source = "Kabucom API (Mid)"

        # ボラティリティ（日次ベースの年率換算）
        # --- [Phase 1.2] 当日価格を結合してボラティリティの精度を向上 ---
        temp_close = close_daily.copy()
        if "Kabucom" in data_source:
            # [Professional Audit] タイムゾーンの整合性を確保
            now_jst = current_time_override or datetime.now(JST)
            today_date = now_jst.date()
            
            # インデックスがタイムゾーンを持っていたら、新しいタイムスタンプにも合わせる
            if temp_close.index[-1].date() < today_date:
                new_ts = pd.Timestamp(today_date)
                if temp_close.index.tzinfo is not None:
                    # インデックスと同じタイムゾーンを適用
                    new_ts = new_ts.tz_localize(temp_close.index.tzinfo)
                temp_close[new_ts] = current
            else:
                temp_close.iloc[-1] = current
        
        volatility = float(temp_close.pct_change().dropna().std()) * np.sqrt(252)

        if verbose:
            print(f"  [Regime] {etf_ticker}: 現在値={current:.1f} ({data_source}) SMA20={sma20:.1f} Vol={volatility:.2f}")

        # レジーム判定ロジック（パーセンテージベースでスケール不変）
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
def manage_positions(portfolio: list, account: dict, broker, regime: str = "RANGE", is_simulation: bool = True, realtime_buffers: dict = None, current_time_override=None, verbose=True):
    """
    保有株式の利確・損切・タイムストップを判定し、売却処理を行う。
    realtime_buffers: { code: RealtimeBuffer } の辞書。存在すれば yfinance 通信を回避する。
    """
    actions = []
    trade_logs = []
    
    if not portfolio:
        return portfolio, account, actions, trade_logs

    if verbose:
        print(f"\n--- [Portfolio] 保有監視 ({len(portfolio)}銘柄) ---")
    
    # リアルタイムバッファがある場合はそれを使用し、ない場合は一括取得を試みる
    data_map = {} # { code: DataFrame }
    
    tickers_to_download = []
    for p in portfolio:
        code = str(p['code'])
        if realtime_buffers and code in realtime_buffers:
            data_map[code] = realtime_buffers[code].get_df()
        else:
            tickers_to_download.append(f"{code}.T")

    if tickers_to_download:
        # [OK] 足りない分だけ一括取得
        try:
            downloaded = yf.download(tickers_to_download, period="5d", interval="15m", group_by='ticker', threads=False, progress=False)
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
            print("[WARNING] 判定用のデータが取得できませんでした(次回リトライへ持ち越し)")
        return portfolio, account, actions, trade_logs

    remaining_portfolio = []
    # 仮想時間の注入
    now_dt = current_time_override or datetime.now(JST)
    current_time = now_dt.strftime('%Y-%m-%d %H:%M:%S')
    now_time = now_dt.time()
    # 2024年11月の東証取引時間延長(15:30)に対応。15:15を大引け直前の手仕舞いラインとする。
    # is_closing_time = now_time >= datetime.strptime("15:15", "%H:%M").time() 
    is_closing_time = False # デイトレ強制決済を無効化（スイングトレード化）

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
            
            # 【重要】テクニカル指標の計算（SMA5等を使用するため）
            df = calculate_technicals_for_scan(df)
            if df is None or 'SMA5' not in df.columns:
                remaining_portfolio.append(p)
                continue

            split_ratio = 1.0
            # リアルAPIモードの場合はAPI側ですでに調整済みのため、二重調整を避ける
            if is_simulation and 'Adj Close' in df.columns and float(df['Close'].iloc[0]) > 0:
                split_ratio = float(df['Adj Close'].iloc[0]) / float(df['Close'].iloc[0])
                if split_ratio > 1.0: split_ratio = 1.0 

            # 【修正】株式分割補正 ( compounded growth 防止のため、in-place ではなく local で扱うか、フラグ管理する )
            # 実際には p['shares'] は整数であるべきなので、補正が必要な場合のみ一度だけ適用するロジックにする
            if split_ratio < 0.99 and not p.get('split_adjusted'):
                original_shares = int(p.get('shares', 0))
                p['shares'] = int(original_shares / split_ratio)
                p['split_adjusted'] = True # 二重適用防止フラグ
                if verbose:
                    print(f"🔄 [{code}] 株式分割を検知: {original_shares}株 -> {p['shares']}株 に価格と共に補正しました。")

            # 以共の計算で使う内部変数
            current_shares = int(p['shares'])
            buy_price = float(p.get('buy_price', 0)) * split_ratio
            highest_price_db = float(p.get('highest_price', buy_price)) * split_ratio

            # --- 価格入力の階層化 (Price Input Hierarchy) ---
            # シミュレーション時は常に df の最新値を使用する（ stales 防止）
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
                
            # [V2-C3] ストップ高/安張り付き（流動性枯渇）のフェイルセーフ
            is_volume_zero = False
            if 'Volume' in df.columns and float(df['Volume'].iloc[-1]) == 0:
                is_volume_zero = True


            # --- ATR(Average True Range)の計算 ---
            tr1 = df['High'] - df['Low']
            tr2 = abs(df['High'] - df['Close'].shift())
            tr3 = abs(df['Low'] - df['Close'].shift())
            atr = float(pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean().iloc[-1])
            if pd.isna(atr) or atr == 0:
                atr = current_price_raw * 0.02
                
            # [V2-M1] 動的スリッページ (ATRベース: ボラティリティの1%をスリッページとする)
            # Strategy 2.0: 0.03 から 0.01 に緩和 (1 tick程度の実勢に合わせる)
            if is_simulation:
                tick_size = get_tick_size(current_price_raw)
                slippage = max(tick_size, atr * 0.01) 
                current_price = max(0.1, current_price_raw - slippage)
            else:
                slippage = 0
                current_price = current_price_raw
            
            # 【修正】profit_pct をここで定義（後の sell_reason で参照するため）
            profit_pct = (current_price - buy_price) / buy_price if buy_price > 0 else 0

            # 【新規】分割利確（スケールアウト）のステータス確認
            is_partial_sold = p.get('partial_sold', False)
            
            # トレール幅を動的に変更
            current_trail_mult = ATR_TRAIL * 1.5 if is_partial_sold else ATR_TRAIL

            sell_reason = None
            # レジームに応じた損切り倍率の選択
            current_stop_loss_mult = RANGE_ATR_STOP_LOSS if regime == "RANGE" else ATR_STOP_LOSS
            
            # --- 【ピボット修正】VWAP Pullback戦略用の売却ロジック ---
            sell_qty = current_shares

            # 【修正1】絶対ストップを -4.0% に広げ、日中のノイズ（ダマシ）で死なないようにする
            hard_stop_price = buy_price * 0.96  
            
            current_dt = current_time_override if current_time_override else datetime.now(JST)
            if hasattr(current_dt, 'to_pydatetime'):
                current_dt = current_dt.to_pydatetime()
            buy_dt = p['buy_time']
            if isinstance(buy_dt, str):
                try:
                    buy_dt = datetime.strptime(buy_dt, '%Y-%m-%d %H:%M:%S').replace(tzinfo=JST)
                except ValueError:
                    buy_dt = now_dt 
            if hasattr(buy_dt, 'to_pydatetime'):
                buy_dt = buy_dt.to_pydatetime()
            hold_days = (current_dt - buy_dt).total_seconds() / 86400

            # --- 決済ロジック: 優先度順に展開 ---
            
            # [Optimization] ボラティリティに基づいた初期損切り (ATR 1.6倍)
            initial_stop_price = buy_price - (atr * ATR_STOP_MULT)
            # [Optimization] 絶対ハードストップ (-4.0%) とのタイトな方を選択
            hard_stop_price = max(buy_price * 0.96, initial_stop_price)

            # [Optimization] 建値決済（ブレイクイーブン）の設定
            # 1%以上の含み益が出た後は、損切りラインを建値（+手数料分）に引き上げる
            if profit_pct >= BREAKEVEN_TRIGGER:
                hard_stop_price = max(hard_stop_price, buy_price * 1.001)

            # [Optimization] 多段階利確・トレールロジック
            # 高値が目標値 (ATR 1.5倍) を超えたらトレールモードをよりタイトにする
            target_price = buy_price + (atr * ATR_TARGET_MULT)
            is_target_reached = highest_price_db >= target_price
            
            if is_target_reached:
                # 目標達成後は最高値から ATR 2.0倍で利益確保
                chandelier_stop = highest_price_db - (atr * 2.0)
            else:
                # 目標未達時は最高値から ATR 2.5倍（ゆったり）
                chandelier_stop = highest_price_db - (atr * TRAIL_STOP_MULT)

            # 【重要】損切り判定（窓開け考慮）
            if is_simulation and open_price <= hard_stop_price:
                sell_reason = f"窓開け損切 (Open {open_price:,.1f} <= Stop {hard_stop_price:,.1f})"
                current_price_raw = open_price # 執行ベース価格を始値に修正
                current_price = max(low_price, open_price - slippage) # クリップ処理
            elif current_price <= hard_stop_price:
                if current_price > buy_price:
                    sell_reason = f"建値守備決済 (Breakeven at {hard_stop_price:,.1f})"
                else:
                    sell_reason = f"絶対損切 (Hard/Initial Stop at {hard_stop_price:,.1f})"
            elif current_price <= chandelier_stop:
                if current_price > buy_price:
                    sell_reason = f"トレール利確 (Trail Stop from {highest_price_db:,.1f})"
                else:
                    sell_reason = f"下降トレンド転換損切 (Trail Stop below Buy)"
            elif hold_days > 5.0: 
                # 【Strategy 4.2】時間切れのさらなる柔軟化 (4 -> 5 days)
                # 5日経っても勢いがない（SMA5を下回った、かつ利益が0.5%未満）場合に効率化撤退
                is_momentum_lost = current_price < df['SMA5'].iloc[-1]
                if is_momentum_lost and profit_pct < 0.005:
                    sell_reason = f"効率化撤退 (5 days & no momentum)"
            elif not is_partial_sold and current_price >= target_price:
                # ATRターゲット達成で半分利確
                sell_reason = f"第一目標達成・半分利確 (+{ATR_TARGET_MULT}xATR)"
                half_qty = (current_shares // 2 // 100) * 100
                if half_qty >= 100:
                    sell_qty = half_qty
                else:
                    # 最小単位なら全決済
                    sell_qty = current_shares

            if not sell_reason:
                new_highest = max(highest_price_db, current_price) / split_ratio if split_ratio > 0 else max(highest_price_db, current_price)
                p['highest_price'] = round(new_highest, 1)
                highest_price = p['highest_price'] * split_ratio 
            else:
                highest_price = highest_price_db

            # [AI改善策2] +0.00%固定化バグの修正: ポートフォリオの現在値をライブデータで常時更新する
            p['current_price'] = round(current_price_raw / split_ratio if split_ratio > 0 else current_price_raw, 1)

            split_mark = "(分割補正済)" if split_ratio < 0.99 else ""
            if verbose:
                print(f"[{code} {p['name']}] 買:{buy_price:,.1f} 現在:{current_price:,.1f} (高:{highest_price:,.1f} | 損益:{profit_pct*100:+.2f}%) {split_mark}")

            if sell_reason:
                if is_volume_zero and verbose:
                    print(f"[WARNING] [{code}] 出来高0(特別気配等)ですが、{sell_reason} のため決済注文を強行します。")

                # リアルAPI運用ならここで売却命令を出し、非同期に結果を得ることになる。
                if is_simulation:
                    actual_qty = sell_qty # 【修正】決定した売却株数を適用
                    exec_price = current_price
                else:
                    if broker:
                        if verbose:
                            print(f"[OMS売却発動] 追従型指値注文（Chase Order）で売却を開始します")
                        # 売却時は side="1" (売)
                        details = broker.execute_chase_order(code, sell_qty, side="1", atr=atr)
                        
                        # [Professional Audit Round 2] 部分約定 (State=7) を受容し、データ不整合を防ぐ
                        state = details.get('State') if details else None
                        actual_qty = int(details.get('Qty', 0)) if details else 0
                        
                        if not details or state not in [6, 7] or actual_qty == 0:
                            if verbose:
                                print(f"[WARNING] {code} の売却が完了しませんでした（約定0株）。次サイクルで再試行します。")
                            remaining_portfolio.append(p)
                            continue
                            
                        # APIからの約定データをパースする
                        exec_price = float(details.get('Price', 0))
                        if exec_price == 0:
                            exec_price = current_price
                            exec_details = details.get('Details', [])
                            if exec_details:
                                total_val = sum(float(d.get('Price', 0)) * float(d.get('Qty', 0)) for d in exec_details)
                                total_qty = sum(float(d.get('Qty', 0)) for d in exec_details)
                                if total_qty > 0:
                                    exec_price = total_val / total_qty
                        
                        actual_qty = int(details.get('Qty', sell_qty))
                        
                    else:
                        if verbose:
                            print(f"[WARNING] エラー: {code} の本番決済が必要ですが、Brokerが提供されていません。")
                        remaining_portfolio.append(p)
                        continue

                # 実際の約定値に基づいて損益計算
                gross_profit = (exec_price - buy_price) * actual_qty
                tax_amount = int(gross_profit * TAX_RATE) if gross_profit > 0 else 0
                
                # [OK] SIMモードの場合は売却手数料(最近のゼロ手数料コースを考慮し0.000とする)
                if is_simulation:
                    COMMISSION_RATE = 0.000  # [AI改善策1] 手数料ゼロコースに合わせてコストを排除
                    sell_commission = int((exec_price * actual_qty) * COMMISSION_RATE)
                    buy_commission = int((buy_price * actual_qty) * COMMISSION_RATE)
                    sale_proceeds = (exec_price * actual_qty) - tax_amount - sell_commission
                    net_profit = gross_profit - tax_amount - sell_commission - buy_commission

                else:
                    # 実運用時はAPIが正のためそのまま計算ベースとして扱う
                    sale_proceeds = (exec_price * actual_qty) - tax_amount
                    net_profit = gross_profit - tax_amount 

                
                if is_simulation:
                    account['cash'] += sale_proceeds
                else:
                    account['cash'] += sale_proceeds

                # [Robust Update] Once cash is updated, we MUST ensure the portfolio is updated correctly
                if actual_qty < current_shares:
                    remaining_p = p.copy()
                    remaining_p['shares'] = current_shares - actual_qty
                    if "分割利確" in sell_reason:
                        remaining_p['partial_sold'] = True
                    remaining_portfolio.append(remaining_p)
                
                # Notification and Logging (should not block the state update)
                try:
                    log_msg = f"[TRADE]【決済】{code} {p['name']} ({sell_reason})"
                    details_msg = f"   約定単価: {exec_price:,.1f}円 × {actual_qty}株 | 税引前損益: {int(gross_profit):+d}円 | 税引後: {int(net_profit):+d}円"
                    if verbose:
                        print(log_msg)
                        print(details_msg)
                    if not current_time_override:
                        send_discord_notify(log_msg + "\n" + details_msg)
                    
                    act_str = f"決済: {code} {p['name']} {actual_qty}株 ({sell_reason}) {net_profit:+.0f}円"
                    actions.append(act_str)
                    
                    actual_profit_pct = (exec_price - buy_price) / buy_price if buy_price > 0 else 0
                    trade_record = {
                        "sell_time": current_time, "code": code, "name": p['name'], "buy_time": p['buy_time'],
                        "buy_price": buy_price, "sell_price": exec_price, "highest_price_reached": highest_price,
                        "shares": actual_qty, "gross_profit": gross_profit, "tax_amount": tax_amount, 
                        "net_profit": net_profit, "profit_pct": actual_profit_pct, "reason": sell_reason
                    }
                    trade_logs.append(trade_record)
                except Exception as log_err:
                    if verbose:
                        print(f"[ERROR] ログ記録/通知中にエラー（取引自体は実行済）: {log_err}")
            else:
                remaining_portfolio.append(p)
                
        except Exception as e: 
            if verbose:
                print(f"[WARNING] {code} 監視エラー: {e}")
            remaining_portfolio.append(p)

    return remaining_portfolio, account, actions, trade_logs

# --- 【中核3】マルチファクター・スキャン ---
def calculate_technicals_for_scan(df):
    if len(df) < 50:
        return None
    
    price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
    if price_col not in df.columns or df[price_col].isnull().all():
        return None
    df['SMA20'] = df[price_col].rolling(window=20).mean().replace(0, np.nan)
    df['SMA50'] = df[price_col].rolling(window=50).mean() # 【新規】MTFA用の50期間線を追加
    df['STD20'] = df[price_col].rolling(window=20).std()
    df['BB_Upper'] = df['SMA20'] + (df['STD20'] * 2)
    df['BB_Lower'] = df['SMA20'] - (df['STD20'] * 2)
    df['Deviation'] = (df[price_col] - df['SMA20']) / df['SMA20']
    
    delta = df[price_col].diff()
    up = delta.clip(lower=0).ewm(span=14, adjust=False).mean()
    down = -1 * delta.clip(upper=0).ewm(span=14, adjust=False).mean()
    # M-4: np.where→pd.Series.whereに変更し、pandas Seriesの型一貫性を保つ
    rsi_denominator = up + down
    df['RSI'] = (100 * up / rsi_denominator).where(rsi_denominator != 0, other=50.0)
    
    tr1 = df['High'] - df['Low']
    tr2 = abs(df['High'] - df['Close'].shift())
    tr3 = abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(window=14).mean()
    
    df['MACD'] = df[price_col].ewm(span=12, adjust=False).mean() - df[price_col].ewm(span=26, adjust=False).mean()
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # --- [Phase 12] ボリューム解析の追加 ---
    df['Avg_Vol_15m'] = df['Volume'].rolling(window=20).mean()
    
    # VWAP (Volume Weighted Average Price) の簡易計算
    df['VWAP'] = (df[price_col] * df['Volume']).cumsum() / df['Volume'].cumsum()
    
    # 【新規】移動平均線の拡張
    df['SMA5'] = df[price_col].rolling(window=5).mean()
    
    # 乖離率
    df['ROC_4h'] = df[price_col].pct_change(periods=16) # 15分足×16 = 約4時間 (1日相当の勢い)
    
    return df

def select_best_candidates(broker, targets, df_symbols, regime, realtime_buffers=None, current_time_override=None, verbose=True):
    """ 地合い(レジーム)に応じた数学的スコアリングを行い、トップ候補を抽出 """
    candidates = []
    
    for code in targets:
        try:
            # バックテスト時は realtime_buffers からデータを取得
            if realtime_buffers and code in realtime_buffers:
                buf_entry = realtime_buffers[code]
                df = buf_entry.df if hasattr(buf_entry, 'df') else buf_entry
            else:
                # リアルタイム時は yfinance から取得
                df = yf.download(f"{code}.T", period="5d", interval="15m", progress=False, threads=False)
                # [FIX] yfinance の MultiIndex 対策：Ticker レベルを削除してフラットにする
                if df is not None and not df.empty and isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel('Ticker')
            
            if df is None or df.empty:
                continue

            # テクニカル指標の計算
            df = calculate_technicals_for_scan(df)
            if df is None:
                continue
            
            latest = df.iloc[-1]

            # 【新規】市場トレンドフィルター (Nikkei 1321.T)
            # 15分足ベースで日経平均が下げている時は、買いを控える（レンジ相場は除く）
            market_ok = True
            if regime == "BULL" and realtime_buffers and '1321' in realtime_buffers:
                nk_df = realtime_buffers['1321'].df
                if len(nk_df) > 20:
                    nk_sma20 = nk_df['Close'].rolling(window=20).mean().iloc[-1]
                    if nk_df['Close'].iloc[-1] < nk_sma20:
                        market_ok = False

            # 【新規】出来高フィルタ
            vol_surge = False
            if 'Avg_Vol_15m' in latest and latest['Volume'] > 0:
                if latest['Volume'] > latest['Avg_Vol_15m'] * MIN_VOLUME_SURGE:
                    vol_surge = True

            score = 0
            reason = "Unknown"
            
            # 【Strategy 4.2】ハードフィルターを緩和し、スコアリングベースに変更
            if regime == "BULL":
                # 【SMA20押し目買い戦略 (Strategy 4.2)】
                if len(df) < 50:
                    reason = "Not enough data"
                    continue

                sma20 = latest['SMA20']
                sma50 = latest.get('SMA50', sma20)
                rsi = latest.get('RSI', 50)
                momentum_50 = (latest['Close'] - df['Close'].iloc[-50]) / df['Close'].iloc[-50]
                is_yang_sen = latest['Close'] > latest['Open']
                is_sma5_up = latest['SMA5'] > df['SMA5'].iloc[-2] if len(df) > 2 else True

                # 必須条件（これらを満たさない場合は足切り）
                if momentum_50 < -0.02: # 緩やかな下落なら許容
                    reason = f"Weak Momentum ({momentum_50:.2%})"
                elif latest['Close'] < sma50 * 0.98: # 多少の下抜けは許容
                    reason = "Below Anchor SMA50"
                elif rsi > 70: # 70までは許容
                    reason = f"RSI Too High ({rsi:.0f})"
                elif not is_yang_sen and not is_sma5_up: # どちらかは必須
                    reason = "No Bounce Confirmation"
                else:
                    # 【合格】スコア計算
                    dist_sma20 = (latest['Close'] - sma20) / sma20
                    # 基本スコア
                    score = (momentum_50 * 5000) + ((0.03 - abs(dist_sma20)) * 1000)
                    # ボーナス
                    if vol_surge: score += 100
                    if market_ok: score += 50
                    if is_yang_sen and is_sma5_up: score += 50
                    
                    reason = "Strategy 4.2 Bull Entry"

            elif regime == "RANGE":
                # 【RSI平均回帰戦略 (Strategy 4.0)】
                if len(df) < 20: 
                    reason = "Not enough data"
                    continue

                rsi = latest.get('RSI', 50)
                sma20 = latest['SMA20']
                is_yang_sen = latest['Close'] > latest['Open']

                if rsi > 30: # より厳格に (35 -> 30)
                    reason = f"RSI({rsi:.1f}) not oversold enough"
                elif latest['Close'] >= sma20:
                    reason = "Above SMA20"
                elif not is_yang_sen:
                    reason = "Falling (Yin-sen)"
                else:
                    score = (30 - rsi) * 30 + (latest['Volume'] / latest['Avg_Vol_15m'] * 50)
                    reason = "RSI Oversold Bounce"
            else:
                reason = f"Unsupported Regime: {regime}"

            if score > 0:
                score = min(score, 500)
                name = "不明"
                if df_symbols is not None:
                    name_row = df_symbols[df_symbols['コード'].astype(str) == code]
                    name = name_row['銘柄名'].values[0] if not name_row.empty else "不明"
                candidates.append({
                    "code": code, "name": name, 
                    "score": score, 
                    "price": latest['Close'], 
                    "atr": latest['ATR']
                })

        except Exception as e:
            if verbose:
                print(f"[WARNING] [Scan] {code} の評価中にエラーが発生しスキップします: {type(e).__name__}: {e}")
            continue
            
    return sorted(candidates, key=lambda x: x['score'], reverse=True)[:3]
