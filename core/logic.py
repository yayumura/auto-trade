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

def normalize_tick_size(price: float, is_buy: bool) -> int:
    """
    東証の呼値ルールに合わせて指値価格を安全かつ有効な価格に丸める。
    絶対に約定させたい(Marketable Limit Order)ため、あえて不利な方向
    （買付なら上、売却なら下）の有効な呼値に丸めます。
    """
    p = float(price)
    if p <= 3000:
        tick = 1
    elif p <= 5000:
        tick = 5
    elif p <= 10000:
        tick = 10
    elif p <= 30000:
        tick = 50
    elif p <= 50000:
        tick = 100
    else:
        tick = 100 # 簡易版

    if is_buy:
        # 買付：指定価格以上の最小の呼値（切り上げ）
        return int((p + tick - 0.0001) // tick * tick)
    else:
        # 売却：指定価格以下の最大の呼値（切り捨て）
        return int(p // tick * tick)

# --- 【中核1】レジーム（地合い）認識 ---
def detect_market_regime():
    """
    日経平均の過去1ヶ月のデータから現在の相場環境（レジーム）を判定する。
    戻り値: "BULL"(強気), "RANGE"(揉み合い), "BEAR"(弱気/パニック)
    """
    try:
        nk = yf.download('^N225', period="1mo", interval="1d", threads=False, progress=False)
        if nk.empty or len(nk) < 20:
            return "RANGE"
        
        # 【修正】朝イチの誤作動を防ぐため、安易な日付比較によるHOLIDAY判定を削除しました
        
        # yfinance v0.2.31以降はMultiIndex列を返すため、フラット化
        if isinstance(nk.columns, pd.MultiIndex):
            nk.columns = nk.columns.droplevel('Ticker')
        
        price_col = 'Adj Close' if 'Adj Close' in nk.columns else 'Close'
        close = nk[price_col].dropna()
        sma20 = float(close.rolling(window=20).mean().iloc[-1])
        
        current = float(close.iloc[-1])
        volatility = float(close.pct_change().dropna().std()) * np.sqrt(252)
        
        print(f"  📈 N225: 現在値={current:.0f} SMA20={sma20:.0f} Vol={volatility:.2f}")
        
        # --- [Phase 13] データの鮮度チェック ---
        last_date = close.index[-1].date()
        today = datetime.now(JST).date()
        # 平日（月ー金）かつ市場が開いている時間帯で、データが昨日以前なら警告
        now_time = datetime.now(JST).time()
        if today.weekday() < 5 and now_time > datetime.strptime("09:15", "%H:%M").time() and last_date < today:
             print(f"⚠️ [Data Stale] 指数データが古すぎます(最終更新: {last_date})。レジーム判定が不正確な可能性があります。")

        if current < sma20 * 0.95 and volatility > 0.30:
            return "BEAR" 
        elif current > sma20:
            return "BULL"
        else:
            return "RANGE"
    except Exception as e:
        print(f"⚠️ レジーム判定エラー: {e}")
        raise ConnectionError(f"日経平均データの取得に失敗しました: {e}")

# --- 【補助】無効銘柄キャッシュ管理 ---
def load_invalid_tickers():
    return set(safe_read_json(EXCLUSION_CACHE_FILE, default=[]))

def save_invalid_tickers(invalid_set):
    try:
        atomic_write_json(EXCLUSION_CACHE_FILE, list(invalid_set))
    except Exception as e:
        print(f"⚠️ キャッシュ保存エラー: {e}")

# --- 【中核2】保有ポジションの高度な管理 ---
def manage_positions(portfolio: list, account: dict, broker, regime: str = "RANGE", is_simulation: bool = True):
    """
    保有株式の利確・損切・タイムストップを判定し、売却処理を行う。
    is_simulation = False の場合は broker.execute_market_order() を叩いて実際の売り注文を出す。
    """
    actions = []
    trade_logs = []
    
    if not portfolio:
        return portfolio, account, actions, trade_logs

    print(f"\n--- 💼 保有監視 ({len(portfolio)}銘柄) ---")
    tickers = [f"{p['code']}.T" for p in portfolio]
    
    # ✅ try-exceptで囲み、一時的な通信エラーでBOTが落ちるのを防ぐ
    data = None
    for retry in range(3):
        try:
            data = yf.download(tickers, period="5d", interval="15m", group_by='ticker', threads=False, progress=False)
            break
        except Exception as e:
            print(f"⚠️ 保有銘柄のデータ取得に一時的なエラー ({retry+1}/3): {e}")
            time.sleep(2)

    if data is None or data.empty:
        print("⚠️ 規定回数リトライしましたがデータが取得できませんでした(次回リトライへ持ち越し)")
        return portfolio, account, actions, trade_logs

    remaining_portfolio = []
    current_time = datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')
    now_time = datetime.now(JST).time()
    # 2024年11月の東証取引時間延長(15:30)に対応。15:15を大引け直前の手仕舞いラインとする。
    is_closing_time = now_time >= datetime.strptime("15:15", "%H:%M").time() 

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
                # yfinanceが単一銘柄でMultiIndexでなくFlatなDFを返すケース
                # H-1: columns.nameはNoneのことが多いため、len(portfolio)==1のみで判定する
                if len(portfolio) == 1:
                    df = data.dropna()
                else:
                    # 複数銘柄なのにMultiIndexでない = 想定外のデータ形式。安全に保持継続
                    print(f"⚠️ [{code}] 想定外のデータ形式(non-MultiIndex with multiple positions)。保持継続。")
                    remaining_portfolio.append(p)
                    continue
            
            if df.empty or len(df) < 14: 
                remaining_portfolio.append(p)
                continue

            split_ratio = 1.0
            # リアルAPIモードの場合はAPI側ですでに調整済みのため、二重調整を避ける
            if is_simulation and 'Adj Close' in df.columns and float(df['Close'].iloc[0]) > 0:
                split_ratio = float(df['Adj Close'].iloc[0]) / float(df['Close'].iloc[0])
                if split_ratio > 1.0: split_ratio = 1.0 

            # ポジション情報の復元と分割補正
            buy_price = float(p.get('buy_price', 0)) * split_ratio
            highest_price_db = float(p.get('highest_price', buy_price)) * split_ratio

            # 【AI指摘対応】株式分割時に保有株数も逆数で補正する
            if split_ratio < 0.99:
                original_shares = int(p.get('shares', 0))
                p['shares'] = int(original_shares / split_ratio)
                print(f"🔄 [{code}] 株式分割を検知: {original_shares}株 -> {p['shares']}株 に価格と共に補正しました。")

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
                
            # [V2-M1] 動的スリッページ (ATRベース: ボラティリティの10%をスリッページとする)
            if is_simulation:
                slippage = atr * 0.1
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
            sell_qty = int(p['shares'])
            
            if is_closing_time:
                sell_reason = "大引け直前決済 (Daytrade Time Stop 15:15)"
            elif current_price <= buy_price - (atr * current_stop_loss_mult):
                sell_reason = f"ボラティリティ損切 (Stop Loss ATR:{current_stop_loss_mult})"
            elif current_price <= highest_price_db - (atr * current_trail_mult) and highest_price_db > buy_price:
                if current_price > buy_price * 1.005: 
                    sell_reason = f"トレール利確 (Trailing Stop from {highest_price_db:.1f})"
                else:
                    sell_reason = "建値撤退 (Break Even)"
            # --- 【新規】分割利確ロジック ---
            elif not is_partial_sold and current_price >= buy_price + (atr * 1.5):
                # 利益がATRの1.5倍に乗ったら、確実な利益ロックのために半分だけ利確する
                sell_reason = f"分割利確 (Scale-out TP at ATRx1.5)"
                # 100株単位に丸める。最低100株。
                half_qty = (int(p['shares']) // 2 // 100) * 100
                if half_qty >= 100:
                    sell_qty = half_qty
                else:
                    sell_qty = int(p['shares']) # 100株しか持っていない場合は全決済

            if not sell_reason:
                new_highest = max(highest_price_db, current_price) / split_ratio if split_ratio > 0 else max(highest_price_db, current_price)
                p['highest_price'] = round(new_highest, 1)
                highest_price = p['highest_price'] * split_ratio 
            else:
                highest_price = highest_price_db

            # [AI改善策2] +0.00%固定化バグの修正: ポートフォリオの現在値をライブデータで常時更新する
            p['current_price'] = round(current_price_raw / split_ratio if split_ratio > 0 else current_price_raw, 1)


            profit_pct = (current_price - buy_price) / buy_price
            split_mark = "(分割補正済)" if split_ratio < 0.99 else ""
            print(f"[{code} {p['name']}] 買:{buy_price:,.1f} 現在:{current_price:,.1f} (高:{highest_price:,.1f} | 損益:{profit_pct*100:+.2f}%) {split_mark}")

            if sell_reason:
                if is_volume_zero:
                    print(f"⚠️ [{code}] 出来高0(特別気配等)ですが、{sell_reason} のため決済注文を強行します。")

                # リアルAPI運用ならここで売却命令を出し、非同期に結果を得ることになる。
                if is_simulation:
                    actual_qty = sell_qty # 【修正】決定した売却株数を適用
                    exec_price = current_price
                else:
                    if broker:
                        # [V2-M2] 決済時にもスリッページを制限した指値（Marketable Limit Order）を使用
                        # ATRの半分(0.5)を下限価格として設定し、それより下では絶対に売らない防波堤を作る
                        limit_sell_price = normalize_tick_size(current_price_raw - (atr * 0.5), is_buy=False)
                        order_id = broker.execute_market_order(code, sell_qty, side="1", price=limit_sell_price) # 【修正】sell_qty を指定
                        if not order_id:
                            print(f"⚠️ {code} の売却注文が証券会社APIで拒否・失敗しました。")
                            remaining_portfolio.append(p)
                            continue
                        
                        # 決済時は確実に約定を確認 (Phase 11)
                        details = broker.wait_for_execution(order_id)
                        if not details or details.get('State') != 6:
                            print(f"⚠️ {code} の約定が確認できませんでした。手動確認が必要です。")
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
                        
                        actual_qty = int(details.get('Qty', sell_qty)) # 【修正】sell_qty をデフォルトに
                        
                    else:
                        print(f"⚠️ エラー: {code} の本番決済が必要ですが、Brokerが提供されていません。")
                        remaining_portfolio.append(p)
                        continue

                # 実際の約定値に基づいて損益計算
                gross_profit = (exec_price - buy_price) * actual_qty
                tax_amount = int(gross_profit * TAX_RATE) if gross_profit > 0 else 0
                
                # ✅ SIMモードの場合は売却手数料(最近のゼロ手数料コースを考慮し0.000とする)
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
                    # 本番APIの場合は broker.get_account_balance() が最新を反映するので本来不要だが、
                    # 同一ループ内の計算のためにローカル変数も一応更新しておく
                    account['cash'] += sale_proceeds

                # 一部約定（または分割利確）のケースでの残存株の扱い
                if actual_qty < int(p['shares']):
                    remaining_p = p.copy()
                    remaining_p['shares'] = int(p['shares']) - actual_qty
                    
                    # 【新規】スケールアウト成功の場合、残りのポジションにフラグを立てる
                    if "分割利確" in sell_reason:
                        remaining_p['partial_sold'] = True
                        
                    remaining_portfolio.append(remaining_p)
                    print(f"⚠️ [{code}] 一部約定 ({actual_qty}株売却済, {remaining_p['shares']}株残存)。残りは継続保有します。")
                
                msg = f"💰【決済】{code} {p['name']} ({sell_reason})\n   約定単価: {exec_price:,.1f}円 × {actual_qty}株 | 税引前損益: {gross_profit:+.0f}円 | 税引後: {net_profit:+.0f}円"
                print(msg)
                send_discord_notify(msg)
                
                act_str = f"決済: {code} {p['name']} {actual_qty}株 ({sell_reason}) {net_profit:+.0f}円"
                actions.append(act_str)
                
                actual_profit_pct = (exec_price - buy_price) / buy_price
                
                trade_record = {
                    "sell_time": current_time, "code": code, "name": p['name'], "buy_time": p['buy_time'],
                    "buy_price": buy_price, "sell_price": exec_price, "highest_price_reached": highest_price,
                    "shares": actual_qty, "gross_profit": gross_profit, "tax_amount": tax_amount, 
                    "net_profit": net_profit, "profit_pct": actual_profit_pct, "reason": sell_reason
                }
                trade_logs.append(trade_record)
            else:
                remaining_portfolio.append(p)
                
        except Exception as e: 
            print(f"⚠️ {code} 監視エラー: {e}")
            remaining_portfolio.append(p)

    return remaining_portfolio, account, actions, trade_logs

# --- 【中核3】マルチファクター・スキャン ---
def calculate_technicals_for_scan(df):
    if len(df) < 50:
        return None
    df['Avg_Vol_15m'] = df['Volume'].rolling(window=100, min_periods=20).mean().replace(0, 1) 
    
    price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
    df['SMA20'] = df[price_col].rolling(window=20).mean()
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
            days_available = max(1, len(pd.Series(df.index.date).unique()))
            daily_avg_trade_value = (df['Volume'].sum() / days_available) * latest['Close']
            
            # --- [Phase 12] 流動性・スパイクガード ---
            # 1. 売買代金制限 (10億円以上)
            if latest['Close'] < 100 or daily_avg_trade_value < 1000000000:
                continue 

            # 2. スパイク・ガード: 直近15分で異常な価格変化(5%以上)がないか
            if len(df) >= 2:
                p_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
                prev_close = df[p_col].iloc[-2]
                current_change = abs(latest[p_col] - prev_close) / prev_close
                if current_change > 0.05:
                    print(f"⚠️ [Spike Guard] {code} の急激な価格変化({current_change*100:.1f}%)を検知。リスク回避のため除外します。")
                    continue

            # 3. ボラティリティ制限 (ATRが株価の15%を超えたら除外)
            if latest['ATR'] > latest['Close'] * 0.15:
                continue

            score = 0
            
            if regime == "BULL":
                # 1. MTFA（マルチタイムフレーム分析）: 15分足での中期トレンド確認
                if 'SMA50' in df.columns and latest['Close'] < latest['SMA50']: 
                    continue # 日足は強気でも、当日の日中がダウントレンド（落ちるナイフ）なら見送り
                
                today_date = df.index[-1].date()
                today_df = df[df.index.date == today_date]
                vwap_vol = today_df['Volume'].sum()
                typical_price = (today_df['High'] + today_df['Low'] + today_df['Close']) / 3
                vwap = (typical_price * today_df['Volume']).sum() / vwap_vol if vwap_vol > 0 else latest['Close']
                
                # 2. VWAP条件: 当日の買い手が勝っている状態を確認
                if latest['Close'] < vwap: 
                    continue
                
                # 3. 押し目買い（Pullback）判定: VWAPからの乖離率を計算
                vwap_dev = (latest['Close'] - vwap) / vwap
                
                # 高値掴み防止: VWAPから+3%以上上に飛んでいる銘柄は反落リスクが高いため見送り
                if vwap_dev > 0.03: 
                    continue
                    
                vol_ratio = latest['Volume'] / latest['Avg_Vol_15m']
                if vol_ratio < 1.5: # 押し目狙いのため、ブレイクアウト時(2.5)より出来高条件を緩和
                    continue
                
                if latest['MACD'] < latest['Signal']: continue
                if latest['RSI'] > 75: continue

                # スコアリング: VWAPに近い（押し目）ほど高得点、かつRSIの過熱ペナルティ
                # RSIが50(ニュートラル)に近いほどペナルティが少なくなる
                rsi_penalty = abs(50 - latest['RSI']) 
                pullback_bonus = (0.03 - vwap_dev) * 1000 # 乖離0(VWAPぴったり)で30点のボーナス
                
                score = pullback_bonus + (vol_ratio * 5) - rsi_penalty
                
            elif regime == "RANGE":
                if latest['Close'] > latest['SMA20']: continue 
                if latest['Close'] > latest['BB_Lower']: continue 
                if latest['RSI'] > 35: continue
                # [AI改善策3] 落ちるナイフを防ぐため、直近足が陽線(Open < Close)であることを要求
                if 'Open' in df.columns and latest['Close'] <= latest['Open']: continue

                vol_ratio = latest['Volume'] / latest['Avg_Vol_15m']
                
                deviation_depth = abs(latest['Deviation']) * 100
                score = (deviation_depth * 10) + (vol_ratio * 5)
            
            else:
                continue

            if score > 0:
                # M-2: 出来高スパイク等によるスコア過大を防止するためキャップを設ける
                score = min(score, 500)
                name_row = df_symbols[df_symbols['コード'].astype(str) == code]
                name = name_row['銘柄名'].values[0] if not name_row.empty else "不明"
                candidates.append({
                    "code": code, "name": name, 
                    "score": score, 
                    "price": latest['Close'], 
                    "atr": latest['ATR']
                })
        except Exception as e:
            # H-2: 例外を無言でスキップせず、デバッグ可能なログを出力する
            print(f"⚠️ [Scan] {code} の評価中にエラーが発生しスキップします: {type(e).__name__}: {e}")
            continue
            
    return sorted(candidates, key=lambda x: x['score'], reverse=True)[:3]
