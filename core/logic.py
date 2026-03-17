import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

import json
import os
from core.config import ATR_STOP_LOSS, RANGE_ATR_STOP_LOSS, ATR_TRAIL, TAX_RATE, EXCLUSION_CACHE_FILE, JST
from core.log_setup import send_discord_notify
from core.file_io import atomic_write_json, safe_read_json

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
        
        # 【追加】市場休業日（祝日）の判定
        # 最新のデータが「今日」のものでない場合は休場とみなす
        latest_date = nk.index[-1].date()
        today_date = datetime.now(JST).date()
        if latest_date < today_date:
            print(f"  🏖️ 市場は休場です (最新データ: {latest_date})")
            return "HOLIDAY"
        
        # 【修正】yfinance v0.2.31以降はMultiIndex列を返すため、フラット化
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

        if current < sma20 * 0.95 or volatility > 0.30:
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
    data = yf.download(tickers, period="5d", interval="15m", group_by='ticker', threads=True, progress=False)
    
    if data is None or data.empty:
        return portfolio, account, actions, trade_logs

    remaining_portfolio = []
    current_time = datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')
    now_time = datetime.now(JST).time()
    # 2024年11月の東証取引時間延長(15:30)に対応。15:25を大引け直前の手仕舞いラインとする。
    is_closing_time = now_time >= datetime.strptime("15:25", "%H:%M").time() 

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

            split_ratio = 1.0
            # リアルAPIモードの場合はAPI側ですでに調整済みのため、二重調整を避ける
            if is_simulation and 'Adj Close' in df.columns and float(df['Close'].iloc[0]) > 0:
                split_ratio = float(df['Adj Close'].iloc[0]) / float(df['Close'].iloc[0])
                if split_ratio > 1.0: split_ratio = 1.0 

            # --- [Phase 13] 価格入力の階層化 (Price Input Hierarchy) ---
            # 証券会社API由来のリアルタイム価格(p['current_price'])がある場合は、yfinanceの遅延データより優先する
            api_price = p.get('current_price')
            if api_price is not None and api_price > 0:
                current_price_raw = float(api_price)
            else:
                current_price_raw = float(df['Close'].iloc[-1])
                
            # シミュレーション用スリッページ
            current_price = current_price_raw * 0.999 if is_simulation else current_price_raw 
            
            buy_price = float(p['buy_price']) * split_ratio
            highest_price_db = float(p.get('highest_price', p['buy_price'])) * split_ratio
            
            tr1 = df['High'] - df['Low']
            tr2 = abs(df['High'] - df['Close'].shift())
            tr3 = abs(df['Low'] - df['Close'].shift())
            atr = float(pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean().iloc[-1])
            if pd.isna(atr) or atr == 0:
                atr = current_price * 0.02
            
            sell_reason = None
            # レジームに応じた損切り倍率の選択
            current_stop_loss_mult = RANGE_ATR_STOP_LOSS if regime == "RANGE" else ATR_STOP_LOSS
            
            if is_closing_time:
                sell_reason = "大引け直前決済 (Daytrade Time Stop 15:25)"
            elif current_price <= buy_price - (atr * current_stop_loss_mult):
                sell_reason = f"ボラティリティ損切 (Stop Loss ATR:{current_stop_loss_mult})"
            elif current_price <= highest_price_db - (atr * ATR_TRAIL) and highest_price_db > buy_price:
                if current_price > buy_price * 1.005: 
                    sell_reason = f"トレール利確 (Trailing Stop from {highest_price_db:.1f})"
                else:
                    sell_reason = "建値撤退 (Break Even)"

            if not sell_reason:
                new_highest = max(highest_price_db, current_price) / split_ratio if split_ratio > 0 else max(highest_price_db, current_price)
                p['highest_price'] = round(new_highest, 1)
                highest_price = p['highest_price'] * split_ratio 
            else:
                highest_price = highest_price_db

            profit_pct = (current_price - buy_price) / buy_price
            split_mark = "(分割補正済)" if split_ratio < 0.99 else ""
            print(f"[{code} {p['name']}] 買:{buy_price:,.1f} 現在:{current_price:,.1f} (高:{highest_price:,.1f} | 損益:{profit_pct*100:+.2f}%) {split_mark}")

            if sell_reason:
                gross_profit = (current_price - buy_price) * p['shares']
                tax_amount = int(gross_profit * TAX_RATE) if gross_profit > 0 else 0
                net_profit = gross_profit - tax_amount 
                
                # リアルAPI運用ならここで売却命令を出し、非同期に結果を得ることになる。
                if is_simulation:
                    sale_proceeds = (current_price * p['shares']) - tax_amount
                    account['cash'] += sale_proceeds
                else:
                    if broker:
                        order_id = broker.execute_market_order(code, int(p['shares']), side="1") # 1: 売り
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
                            
                        # 【修正追加】リアル取引でも約定完了したらローカル残高を回復させる
                        sale_proceeds = (current_price * p['shares']) - tax_amount
                        account['cash'] += sale_proceeds
                        
                    else:
                        print(f"⚠️ エラー: {code} の本番決済が必要ですが、Brokerが提供されていません。")
                        remaining_portfolio.append(p)
                        continue
                
                msg = f"💰【決済】{code} {p['name']} ({sell_reason})\n   税引前損益: {gross_profit:+.0f}円 | 税引後: {net_profit:+.0f}円"
                print(msg)
                send_discord_notify(msg)
                
                act_str = f"決済: {code} {p['name']} ({sell_reason}) {net_profit:+.0f}円"
                actions.append(act_str)
                
                trade_record = {
                    "sell_time": current_time, "code": code, "name": p['name'], "buy_time": p['buy_time'],
                    "buy_price": buy_price, "sell_price": current_price, "highest_price_reached": highest_price,
                    "shares": p['shares'], "gross_profit": gross_profit, "tax_amount": tax_amount, 
                    "net_profit": net_profit, "profit_pct": profit_pct, "reason": sell_reason
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
    df['STD20'] = df[price_col].rolling(window=20).std()
    df['BB_Upper'] = df['SMA20'] + (df['STD20'] * 2)
    df['BB_Lower'] = df['SMA20'] - (df['STD20'] * 2)
    df['Deviation'] = (df[price_col] - df['SMA20']) / df['SMA20']
    
    delta = df[price_col].diff()
    up = delta.clip(lower=0).ewm(span=14, adjust=False).mean()
    down = -1 * delta.clip(upper=0).ewm(span=14, adjust=False).mean()
    df['RSI'] = np.where((up + down) == 0, 50, 100 * up / (up + down))
    
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
            # 1. 売買代金制限 (3億円以上)
            if latest['Close'] < 100 or daily_avg_trade_value < 300000000:
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
                vol_ratio = latest['Volume'] / latest['Avg_Vol_15m']
                if vol_ratio < 2.5: continue
                if latest['MACD'] < latest['Signal']: continue
                if latest['RSI'] > 75: continue
                
                today_date = df.index[-1].date()
                today_df = df[df.index.date == today_date]
                vwap_vol = today_df['Volume'].sum()
                typical_price = (today_df['High'] + today_df['Low'] + today_df['Close']) / 3
                vwap = (typical_price * today_df['Volume']).sum() / vwap_vol if vwap_vol > 0 else latest['Close']
                if latest['Close'] < vwap: continue
                
                score = (vol_ratio * 10) + (latest['RSI'] - df['RSI'].iloc[-2])
                
            elif regime == "RANGE":
                if latest['Close'] > latest['SMA20']: continue 
                if latest['Close'] > latest['BB_Lower']: continue 
                if latest['RSI'] > 35: continue
                vol_ratio = latest['Volume'] / latest['Avg_Vol_15m']
                
                deviation_depth = abs(latest['Deviation']) * 100
                score = (deviation_depth * 10) + (vol_ratio * 5)
            
            else:
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
            
    return sorted(candidates, key=lambda x: x['score'], reverse=True)[:3]
