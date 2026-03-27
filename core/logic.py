import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

import json
import os
import time
from core.config import ATR_STOP_LOSS, RANGE_ATR_STOP_LOSS, ATR_TRAIL, TAX_RATE, EXCLUSION_CACHE_FILE, JST
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
    絶対に約定させたい(Marketable Limit Order)ため、あえて不利な方向
    （買付なら上、売却なら下）の有効な呼値に丸めます。
    """
    p = float(price)
    
    # [Professional Audit] 2024年現在の東証標準呼値（非TOPIX100銘柄用）に基づく厳格な丸め
    if p <= 3000:
        tick = 1.0
    elif p <= 5000:
        tick = 5.0
    elif p <= 10000:
        tick = 10.0
    elif p <= 30000:
        tick = 50.0
    elif p <= 50000:
        tick = 100.0
    elif p <= 100000:
        tick = 500.0
    elif p <= 1000000:
        tick = 1000.0
    else:
        tick = 5000.0
    
    if is_buy:
        # 買付：指定価格以上の最小の呼値（切り上げ）
        return int((p + tick - 0.0001) // tick * tick)
    else:
        # 売却：指定価格以下の最大の呼値（切り捨て）
        return int(p // tick * tick)

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
            close_daily_all = buffer.df['Close'].resample('D').last().dropna()
            
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
            
            if df.empty or len(df) < 14: 
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

            # --- [Phase 13] 価格入力の階層化 (Price Input Hierarchy) ---
            # 証券会社API由来のリアルタイム価格(p['current_price'])がある場合は、yfinanceの遅延データより優先する
            api_price = p.get('current_price')
            if api_price is not None and api_price > 0:
                current_price_raw = float(api_price)
            else:
                current_price_raw = float(df['Close'].iloc[-1])
                
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
                
            # [V2-M1] 動的スリッページ (ATRベース: ボラティリティの3%をスリッページとする)
            if is_simulation:
                slippage = atr * 0.03 # 0.1 から 0.03 に緩和
                current_price = max(0.1, current_price_raw - slippage)
            else:
                current_price = current_price_raw
            
            # 【新規】分割利確（スケールアウト）のステータス確認
            is_partial_sold = p.get('partial_sold', False)
            
            # トレール幅を動的に変更（半分利確後はトレール幅を1.5倍に広げて大化けを狙う）
            current_trail_mult = ATR_TRAIL * 1.5 if is_partial_sold else ATR_TRAIL

            sell_reason = None
            # レジームに応じた損切り倍率の選択
            current_stop_loss_mult = RANGE_ATR_STOP_LOSS if regime == "RANGE" else ATR_STOP_LOSS
            
            # 売却株数の決定（デフォルトは全株）
            sell_qty = current_shares

            # 【新規】フェイルセーフ：絶対ストップとタイムストップ
            hard_stop_price = buy_price * 0.98  # 買値から-2%で無条件カット
            
            # 保有期間（日数）の計算
            current_dt = current_time_override if current_time_override else datetime.now(JST)
            if hasattr(current_dt, 'to_pydatetime'):
                current_dt = current_dt.to_pydatetime()
            buy_dt = p['buy_time']
            # p['buy_time'] が文字列の場合はdatetimeに変換（通常はdatetimeオブジェクトだが念のため）
            if isinstance(buy_dt, str):
                try:
                    buy_dt = datetime.strptime(buy_dt, '%Y-%m-%d %H:%M:%S').replace(tzinfo=JST)
                except ValueError:
                    buy_dt = now_dt # 変換失敗時は現在時刻（保持0日扱い）
            if hasattr(buy_dt, 'to_pydatetime'):
                buy_dt = buy_dt.to_pydatetime()
            
            hold_days = (current_dt - buy_dt).total_seconds() / 86400

            if current_price <= hard_stop_price:
                sell_reason = "絶対損切 (-2% Hard Stop)"
            elif hold_days > 3.0: 
                sell_reason = "タイムストップ (Held > 3 days)"
            elif is_closing_time:
                sell_reason = "大引け直前決済 (Daytrade Time Stop 15:15)"
            elif current_price <= buy_price - (atr * current_stop_loss_mult):
                sell_reason = f"ボラティリティ損切 (Stop Loss ATR:{current_stop_loss_mult})"
            elif highest_price_db > buy_price and current_price <= highest_price_db - (atr * current_trail_mult):
                # 利益が出ている状態から反落した場合
                if current_price > buy_price * 1.01: # 1%以上の利益があれば「トレール利確」
                    sell_reason = f"トレール利確 (Trailing Stop from {highest_price_db:.1f})"
                else:
                    sell_reason = "建値撤退 (Break Even / Minimal Profit)"
            # --- 【新規】分割利確ロジック ---
            elif not is_partial_sold and current_price >= buy_price + (atr * 8.0):
                # 利益がATRの8.0倍（十分なトレンド）に乗ったら半分利確
                sell_reason = f"分割利確 (Scale-out TP at ATRx8.0)"
                # 100株単位に丸める。最低100株。
                half_qty = (current_shares // 2 // 100) * 100
                if half_qty >= 100:
                    sell_qty = half_qty
                else:
                    sell_qty = current_shares # 100株しか持っていない場合は全決済

            if not sell_reason:
                new_highest = max(highest_price_db, current_price) / split_ratio if split_ratio > 0 else max(highest_price_db, current_price)
                p['highest_price'] = round(new_highest, 1)
                highest_price = p['highest_price'] * split_ratio 
            else:
                highest_price = highest_price_db

            # [AI改善策2] +0.00%固定化バグの修正: ポートフォリオの現在値をライブデータで常時更新する
            p['current_price'] = round(current_price_raw / split_ratio if split_ratio > 0 else current_price_raw, 1)


            profit_pct = (current_price - buy_price) / buy_price if buy_price > 0 else 0
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
                # リアルタイム時は data_df からフィルタリングして取得
                df = data_df[data_df['コード'].astype(str) == code].copy()
            
            if df is None or df.empty:
                if current_time_override and code == targets[0] and current_time_override.minute == 0:
                    print(f"  [Scan Debug] {current_time_override} {code} data is empty")
                continue

            # テクニカル指標の計算
            df = calculate_technicals_for_scan(df)
            if df is None:
                if current_time_override and code == targets[0] and current_time_override.minute == 0:
                    print(f"  [Scan Debug] {current_time_override.strftime('%m/%d %H:%M')} {code} technicals returned None")
                continue
            
            latest = df.iloc[-1]

            score = 0
            
            reason = "Unknown"
            if regime == "BULL":
                # 【順張り戦略】上昇トレンドの「押し目」や「初動」を狙う
                if 'SMA50' in df.columns and latest['Close'] < latest['SMA50']: 
                    reason = "Below SMA50 (Macro trend is down)"
                    score -= 50
                
                vol_ratio = latest['Volume'] / latest['Avg_Vol_15m']
                if vol_ratio < 0.5:
                    reason = f"VolRatio({vol_ratio:.2f}) < 0.5"
                elif latest.get('RSI', 50) > 70: 
                    # 【重要】RSIが70以上（短期的な買われすぎ・急騰直後）は高値掴みになるので避ける
                    reason = f"RSI({latest['RSI']:.1f}) > 70 (Overbought)"
                elif latest['Close'] < latest['SMA20']:
                    reason = "Below SMA20 (Short term momentum is weak)"
                else:
                    # SMA20より上にあるが、離れすぎていない（安全なエントリーポイント）
                    deviation_from_sma20 = abs(latest['Deviation']) 
                    macd_hist = latest['MACD'] - latest['Signal']
                    
                    if macd_hist < 0:
                        reason = "MACD Histogram is negative" # 下落モメンタム中は買わない
                    else:
                        # 乖離が少ない（SMA20に近い）ほど安全として高く評価し、出来高も加味する
                        score += ( (0.02 - deviation_from_sma20) * 1000 ) + (vol_ratio * 10)
                        
                        # [Bonus] 終値がVWAPより上にある（その日強い）銘柄を加点
                        today_date = df.index[-1].date()
                        today_df = df[df.index.date == today_date]
                        if not today_df.empty:
                            vwap_vol = today_df['Volume'].sum()
                            typical_price = (today_df['High'] + today_df['Low'] + today_df['Close']) / 3
                            vwap = (typical_price * today_df['Volume']).sum() / vwap_vol if vwap_vol > 0 else latest['Close']
                            if latest['Close'] > vwap:
                                score += 20
                        reason = "Pullback / Breakout Setup"

            elif regime == "RANGE":
                # 【逆張り戦略】下落の行き過ぎ（売られすぎ）からの反発を狙う
                vol_ratio = latest['Volume'] / latest['Avg_Vol_15m']
                # 乖離率(Deviation)は SMA20 からの乖離
                deviation = latest['Deviation'] 
                
                # --- 追加: 反発の確認（陽線であり、直近の足より上昇していること） ---
                is_bouncing = (latest['Close'] > latest['Open']) and (latest['Close'] > df['Close'].iloc[-2])
                
                if latest.get('RSI', 50) > 40:
                    reason = f"RSI({latest['RSI']:.1f}) is not oversold"
                elif deviation >= -0.015:
                    reason = f"Deviation({deviation:.2%}) is not deep enough" # SMA20から1.5%以上下落していない
                elif not is_bouncing:
                    reason = "Falling Knife (No Bounce Confirmed)" # 反発未確認はスキップ
                else:
                    # マイナス乖離が深いほど高スコア（下落からのリバウンド狙い）
                    deviation_depth = abs(deviation) * 100
                    score = (deviation_depth * 20) + (vol_ratio * 5)
                    reason = "Mean Reversion (Bounce)"
            else:
                reason = f"Unsupported Regime: {regime}"

            if score > 0:
                # M-2: 出来高スパイク等によるスコア過大を防止するためキャップを設ける
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
            elif current_time_override:
                # [Debugging] 毎時0分に全銘柄の理由を出力
                if current_time_override.minute == 0 and verbose:
                    print(f"  [Scan Debug] {current_time_override.strftime('%m/%d %H:%M')} {code} rejected: {reason} (Regime:{regime})")

        except Exception as e:
            # H-2: 例外を無言でスキップせず、デバッグ可能なログを出力する
            if verbose:
                print(f"[WARNING] [Scan] {code} の評価中にエラーが発生しスキップします: {type(e).__name__}: {e}")
            continue
            
    return sorted(candidates, key=lambda x: x['score'], reverse=True)[:3]
