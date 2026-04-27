import json
import pandas as pd
import numpy as np
from datetime import datetime as dt
from core.config import (
    STOP_LOSS_ATR, TAKE_PROFIT_ATR, JST, BREADTH_THRESHOLD,
    MAX_POSITIONS, MAX_ALLOCATION_PCT,
    MAX_ALLOCATION_AMOUNT, LIQUIDITY_LIMIT_RATE, MIN_ALLOCATION_AMOUNT,
    EXCLUSION_CACHE_FILE, SMA20_EXIT_BUFFER, MAX_HOLD_DAYS,
    SMA_SHORT_PERIOD, SMA_MEDIUM_PERIOD, SMA_LONG_PERIOD, SMA_TREND_PERIOD,
    BULL_GAP_LIMIT, RS_THRESHOLD,
    USE_COMPOUNDING, INITIAL_CASH, LEVERAGE, MIN_PRICE, MAX_PRICE
)

DAYTRADE_MIN_GAP = -0.005
DAYTRADE_MAX_GAP = 0.03
DAYTRADE_MIN_PREV_BODY_ATR = -10.0
DAYTRADE_MAX_PREV_BODY_ATR = 10.0
DAYTRADE_MIN_INTRADAY_RECOVERY_ATR = -0.05
DAYTRADE_MAX_OPEN_FROM_PREV_CLOSE_ATR = 3.00
DAYTRADE_MIN_RANGE_ATR = 0.00
DAYTRADE_MIN_TREND_GAP_ATR = -999.0
DAYTRADE_MAX_OPEN_POSITION_ATR = 999.0
DAYTRADE_MIN_RS_ALPHA = 0.0
DAYTRADE_MIN_RSI2 = 35.0
DAYTRADE_MAX_RSI2 = 80.0
DAYTRADE_MIN_SETUP_SCORE = 3.0
DAYTRADE_MIN_PREV_DAY_DROP_PCT = -0.08
DAYTRADE_MIN_PREV_DAY_RETURN_PCT = -0.005
DAYTRADE_MAX_PREV_DAY_RETURN_PCT = 0.08
DAYTRADE_MAX_DAILY_LOSS_PCT = 0.01
DAYTRADE_MAX_MONTHLY_DRAWDOWN_PCT = 0.75
DAYTRADE_RISK_PER_TRADE_PCT = 0.500
DAYTRADE_MAX_NOTIONAL_PCT = 0.15
DAYTRADE_MIN_TURNOVER = 600_000_000.0
DAYTRADE_REBOUND_CONFIRM_ATR = 0.0
DAYTRADE_STRONG_BREADTH_OVERRIDE = 0.60
DAYTRADE_WEEKLY_TARGET_PCT = 0.01
DAYTRADE_WEEKLY_CATCHUP_UNTIL_PCT = 0.005
DAYTRADE_WEEKLY_CATCHUP_LEVERAGE_MULT = 20.00


def _is_invalid_number(value):
    return value is None or pd.isna(value) or np.isinf(value)


def _floor_lot(shares):
    return max(0, (int(shares) // 100) * 100)


def is_daytrade_market_allowed(breadth_val, market_open=None, prev_market_sma_trend=None):
    if _is_invalid_number(breadth_val) or float(breadth_val) < BREADTH_THRESHOLD:
        return False
    if float(breadth_val) >= DAYTRADE_STRONG_BREADTH_OVERRIDE:
        return True
    if _is_invalid_number(market_open) or _is_invalid_number(prev_market_sma_trend):
        return False
    if float(market_open) <= 0 or float(prev_market_sma_trend) <= 0:
        return False
    return float(market_open) > float(prev_market_sma_trend)


def get_daytrade_week_key(timestamp):
    iso = timestamp.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def resolve_daytrade_weekly_leverage(
    base_leverage,
    week_start_equity,
    current_equity,
    target_pct=DAYTRADE_WEEKLY_CATCHUP_UNTIL_PCT,
    catchup_mult=DAYTRADE_WEEKLY_CATCHUP_LEVERAGE_MULT,
):
    if base_leverage <= 0:
        return 0.0
    if _is_invalid_number(week_start_equity) or _is_invalid_number(current_equity):
        return float(base_leverage)
    if float(week_start_equity) <= 0:
        return float(base_leverage)
    week_return = (float(current_equity) / float(week_start_equity)) - 1.0
    if week_return + 1e-12 >= float(target_pct):
        return float(base_leverage)
    return float(base_leverage) * float(catchup_mult)


def is_daytrade_monthly_risk_blocked(
    month_start_equity,
    current_equity,
    max_drawdown_pct=DAYTRADE_MAX_MONTHLY_DRAWDOWN_PCT,
):
    if _is_invalid_number(month_start_equity) or _is_invalid_number(current_equity):
        return False
    if float(month_start_equity) <= 0:
        return False
    month_return = (float(current_equity) / float(month_start_equity)) - 1.0
    return month_return <= -float(max_drawdown_pct)


def resolve_daytrade_intraday_stop_mult(sl_mult=STOP_LOSS_ATR):
    return max(0.6, min(1.2, float(sl_mult) / 5.0))


def resolve_daytrade_intraday_target_mult(tp_mult=TAKE_PROFIT_ATR):
    return max(1.0, min(2.0, float(tp_mult) / 20.0))


def resolve_daytrade_buying_power(current_equity, account_cash, dynamic_leverage, current_exposure=0.0):
    if _is_invalid_number(current_equity) or _is_invalid_number(dynamic_leverage):
        return 0.0
    if float(current_equity) <= 0 or float(dynamic_leverage) <= 0:
        return 0.0
    exposure_budget = float(current_equity) * float(dynamic_leverage)
    available_budget = exposure_budget - max(0.0, float(current_exposure or 0.0))
    if _is_invalid_number(account_cash):
        return max(0.0, available_budget)
    if float(account_cash) < 0 and available_budget > 0:
        return max(0.0, available_budget + float(account_cash))
    return max(0.0, available_budget)


def evaluate_daytrade_setup(price, open_p, prev_close, sma_med, breadth_val,
                            prev_open=None, prev_atr=None, prev_low=None,
                            rs_alpha=None, rsi2=None, prev_prev_close=None):
    """
    Evaluate a same-day mean-reversion setup using prior-day ATR and candle state.
    Returns a metric dict when valid, otherwise None.
    """
    values = [price, open_p, prev_close, breadth_val, prev_open, prev_atr]
    if any(_is_invalid_number(v) for v in values):
        return None

    prev_atr = float(prev_atr)
    if prev_close <= 0 or open_p <= 0 or price <= 0 or prev_open <= 0 or prev_atr <= 0:
        return None

    gap_pct = (open_p / prev_close) - 1.0
    prev_return = None
    if not _is_invalid_number(prev_prev_close) and float(prev_prev_close) > 0:
        prev_return = (prev_close / float(prev_prev_close)) - 1.0
    prev_body_atr = (prev_close - prev_open) / prev_atr
    intraday_recovery_atr = (price - open_p) / prev_atr
    prev_range_atr = abs(prev_open - prev_close) / prev_atr

    if breadth_val < BREADTH_THRESHOLD:
        return None
    if not _is_invalid_number(rs_alpha) and float(rs_alpha) < DAYTRADE_MIN_RS_ALPHA:
        return None
    if not _is_invalid_number(rsi2):
        rsi2 = float(rsi2)
        if rsi2 < DAYTRADE_MIN_RSI2 or rsi2 > DAYTRADE_MAX_RSI2:
            return None
    if prev_return is not None:
        if prev_return < DAYTRADE_MIN_PREV_DAY_RETURN_PCT or prev_return > DAYTRADE_MAX_PREV_DAY_RETURN_PCT:
            return None
    if gap_pct < DAYTRADE_MIN_GAP or gap_pct > DAYTRADE_MAX_GAP:
        return None
    if prev_body_atr < DAYTRADE_MIN_PREV_BODY_ATR or prev_body_atr > DAYTRADE_MAX_PREV_BODY_ATR:
        return None
    if intraday_recovery_atr < DAYTRADE_MIN_INTRADAY_RECOVERY_ATR:
        return None
    if prev_range_atr < DAYTRADE_MIN_RANGE_ATR:
        return None

    open_from_prev_low_atr = None
    if not _is_invalid_number(prev_low):
        open_from_prev_low_atr = (open_p - prev_low) / prev_atr
        if open_from_prev_low_atr > DAYTRADE_MAX_OPEN_FROM_PREV_CLOSE_ATR:
            return None

    open_vs_sma_atr = None
    if not _is_invalid_number(sma_med) and sma_med > 0:
        open_vs_sma_atr = (prev_close - sma_med) / prev_atr
        if open_vs_sma_atr < DAYTRADE_MIN_TREND_GAP_ATR:
            return None
        if open_vs_sma_atr > DAYTRADE_MAX_OPEN_POSITION_ATR:
            return None

    return {
        "gap_pct": gap_pct,
        "prev_return": prev_return,
        "prev_body_atr": prev_body_atr,
        "intraday_recovery_atr": intraday_recovery_atr,
        "prev_range_atr": prev_range_atr,
        "open_from_prev_low_atr": open_from_prev_low_atr,
        "open_vs_sma_atr": open_vs_sma_atr,
        "rs_alpha": float(rs_alpha) if not _is_invalid_number(rs_alpha) else None,
    }


def evaluate_daytrade_open_setup(open_p, prev_close, sma_med, breadth_val,
                                 prev_open=None, prev_atr=None, prev_low=None,
                                 prev_rsi2=None, rs_alpha=None, prev_prev_close=None):
    """
    Pre-open / opening-bell evaluation using only information available at the open.
    """
    values = [open_p, prev_close, breadth_val, prev_open, prev_atr]
    if any(_is_invalid_number(v) for v in values):
        return None

    prev_atr = float(prev_atr)
    if open_p <= 0 or prev_close <= 0 or prev_open <= 0 or prev_atr <= 0:
        return None

    gap_pct = (open_p / prev_close) - 1.0
    prev_return = None
    if not _is_invalid_number(prev_prev_close) and float(prev_prev_close) > 0:
        prev_return = (prev_close / float(prev_prev_close)) - 1.0
    prev_body_atr = (prev_close - prev_open) / prev_atr
    prev_range_atr = abs(prev_open - prev_close) / prev_atr

    if breadth_val < BREADTH_THRESHOLD:
        return None
    if not _is_invalid_number(rs_alpha) and float(rs_alpha) < DAYTRADE_MIN_RS_ALPHA:
        return None
    if gap_pct < DAYTRADE_MIN_GAP or gap_pct > DAYTRADE_MAX_GAP:
        return None
    if prev_body_atr < DAYTRADE_MIN_PREV_BODY_ATR or prev_body_atr > DAYTRADE_MAX_PREV_BODY_ATR:
        return None
    if prev_range_atr < DAYTRADE_MIN_RANGE_ATR:
        return None

    if not _is_invalid_number(prev_rsi2):
        prev_rsi2 = float(prev_rsi2)
        if prev_rsi2 < DAYTRADE_MIN_RSI2 or prev_rsi2 > DAYTRADE_MAX_RSI2:
            return None

    if prev_return is not None:
        if prev_return < DAYTRADE_MIN_PREV_DAY_RETURN_PCT or prev_return > DAYTRADE_MAX_PREV_DAY_RETURN_PCT:
            return None

    open_from_prev_low_atr = None
    if not _is_invalid_number(prev_low):
        open_from_prev_low_atr = (open_p - prev_low) / prev_atr
        if open_from_prev_low_atr > (DAYTRADE_MAX_OPEN_FROM_PREV_CLOSE_ATR + 0.35):
            return None

    open_vs_sma_atr = None
    if not _is_invalid_number(sma_med) and sma_med > 0:
        open_vs_sma_atr = (prev_close - sma_med) / prev_atr
        if open_vs_sma_atr < DAYTRADE_MIN_TREND_GAP_ATR:
            return None
        if open_vs_sma_atr > DAYTRADE_MAX_OPEN_POSITION_ATR:
            return None

    return {
        "gap_pct": gap_pct,
        "prev_return": prev_return,
        "prev_body_atr": prev_body_atr,
        "prev_range_atr": prev_range_atr,
        "open_from_prev_low_atr": open_from_prev_low_atr,
        "open_vs_sma_atr": open_vs_sma_atr,
        "rs_alpha": float(rs_alpha) if not _is_invalid_number(rs_alpha) else None,
    }


def score_daytrade_setup(metrics, rsi2=None, rs_alpha=None, prev_close=None, prev_prev_close=None, prev_atr=None):
    """
    Rank same-day momentum-continuation candidates. Higher is better.
    """
    if metrics is None:
        return -np.inf

    rsi_penalty = 0.0
    if not _is_invalid_number(rsi2):
        rsi_penalty = max(0.0, float(rsi2) - 80.0) * 0.15

    rs_bonus = 0.0
    if not _is_invalid_number(rs_alpha):
        rs_bonus = max(float(rs_alpha), 0.0) * 0.08

    prev_return_bonus = 0.0
    if not any(_is_invalid_number(v) for v in [prev_close, prev_prev_close, prev_atr]) and prev_atr > 0:
        prev_return_bonus = max(0.0, (float(prev_close) / float(prev_prev_close)) - 1.0) * 90.0

    score = (
        prev_return_bonus +
        max(0.0, metrics["gap_pct"]) * 90.0 +
        rs_bonus -
        rsi_penalty
    )

    if metrics.get("open_from_prev_low_atr") is not None:
        score -= metrics["open_from_prev_low_atr"] * 0.125
    if metrics.get("open_vs_sma_atr") is not None:
        score -= abs(metrics["open_vs_sma_atr"]) * 0.15

    return float(score)


def score_daytrade_open_setup(metrics, prev_rsi2=None, prev_close=None, prev_prev_close=None, prev_atr=None, rs_alpha=None):
    if metrics is None:
        return -np.inf

    rsi_penalty = 0.0
    if not _is_invalid_number(prev_rsi2):
        rsi_penalty = max(0.0, float(prev_rsi2) - 80.0) * 0.15

    prev_return_bonus = 0.0
    if not any(_is_invalid_number(v) for v in [prev_close, prev_prev_close, prev_atr]) and prev_atr > 0:
        prev_return_bonus = max(0.0, (float(prev_close) / float(prev_prev_close)) - 1.0) * 90.0

    rs_bonus = 0.0
    if not _is_invalid_number(rs_alpha):
        rs_bonus = max(float(rs_alpha), 0.0) * 0.08

    score = (
        prev_return_bonus +
        max(0.0, metrics["gap_pct"]) * 90.0 +
        rs_bonus -
        rsi_penalty
    )

    if metrics.get("open_from_prev_low_atr") is not None:
        score -= metrics["open_from_prev_low_atr"] * 0.125
    if metrics.get("open_vs_sma_atr") is not None:
        score -= abs(metrics["open_vs_sma_atr"]) * 0.15

    return float(score)

def calculate_position_stops(buy_price, buy_atr, max_price, current_price,
                             sl_mult, tp_mult):
    """
    V17.0 Golden Exit Calculator.
    - Fixed Stop Loss based on Entry (PROTECTED by SMA20 Exit).
    - Fixed Take Profit based on Entry.
    """
    # 損切り (Fixed Stop Loss from Entry)
    tsl_price = buy_price - (buy_atr * sl_mult)
    
    # 利確ターゲット (Fixed Take Profit from Entry)
    target_price = buy_price + (buy_atr * tp_mult)
    
    return tsl_price, target_price

def manage_positions_live(portfolio, broker=None, is_simulation=True, realtime_buffers=None, sma_med_map=None):
    """
    Day-trade manager:
    - No multi-day hold.
    - Any residual position is considered invalid and should be flattened immediately.
    """
    sell_actions = []

    if not portfolio:
        return [], sell_actions

    for p in portfolio:
        code = str(p['code'])
        if realtime_buffers and code in realtime_buffers:
            current_price = realtime_buffers[code].get_latest_price()
        else:
            current_price = float(p.get('current_price', p['buy_price']))
        sell_actions.append(f"SELL {code} - Day Trade Flatten (@{current_price:,.1f})")
        if not is_simulation and broker:
            try:
                broker.execute_chase_order(code, p['shares'], side="1")
            except:
                pass

    return [], sell_actions

def calculate_dynamic_leverage(breadth_val, config_leverage=1.5):
    """V17.0 Fixed Breadth Scaling: On if >= Threshold, else Off."""
    if breadth_val >= BREADTH_THRESHOLD:
        return config_leverage
    return 0.0

def check_entry_signal(regime, price, open_p, prev_close, sma_med, breadth_val, prev_open=None, prev_atr=None, prev_low=None):
    """
    Day-trade entry signal:
    - Market breadth must not be risk-off.
    - Previous day should show downside expansion / bearish exhaustion.
    - Today should gap up moderately and hold an intraday rebound.
    """
    metrics = evaluate_daytrade_setup(
        price, open_p, prev_close, sma_med, breadth_val,
        prev_open=prev_open, prev_atr=prev_atr, prev_low=prev_low
    )
    return metrics is not None

def calculate_all_technicals_v12(data_df):
    """
    V131.1 Aegis Technical Bundle:
    - Added RS_Alpha (Absolute 60-day) for leader selection
    - Added RSI2 for mean reversion entry/exit
    """
    bundle = {}
    close = data_df.xs('Close', axis=1, level=1)
    high = data_df.xs('High', axis=1, level=1)
    low = data_df.xs('Low', axis=1, level=1)
    open_v = data_df.xs('Open', axis=1, level=1)
    vol = data_df.xs('Volume', axis=1, level=1)
    
    bundle['Close'] = close
    bundle['Open'] = open_v
    bundle['Volume'] = vol
    bundle[f'SMA{SMA_SHORT_PERIOD}'] = close.rolling(SMA_SHORT_PERIOD).mean()
    bundle[f'SMA{SMA_MEDIUM_PERIOD}'] = close.rolling(SMA_MEDIUM_PERIOD).mean()
    bundle[f'SMA{SMA_LONG_PERIOD}'] = close.rolling(SMA_LONG_PERIOD).mean()
    bundle[f'SMA{SMA_TREND_PERIOD}'] = close.rolling(SMA_TREND_PERIOD).mean()
    # Ensure specific SMAs for optimization
    for p in [50, 100, 200]:
        if f'SMA{p}' not in bundle:
            bundle[f'SMA{p}'] = close.rolling(p).mean()
    
    # RSI (2) Vectorized
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    # Wilder's smoothing equivalent via rolling
    ma_up = up.rolling(2).mean()
    ma_down = down.rolling(2).mean()
    rs_rsi = ma_up / (ma_down + 1e-9)
    bundle['RSI2'] = 100 - (100 / (1 + rs_rsi))
    
    # Bollinger Bands (20, 2sigma) for legacy compatibility and diagnostics
    bb_basis = close.rolling(20).mean()
    bb_std = close.rolling(20).std(ddof=0)
    bundle['BB_LOWER_2'] = bb_basis - (bb_std * 2.0)
    
    # ATR (20) Vectorized
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1)
    bundle['ATR'] = (high - low).rolling(20).mean() # Simple approximation for speed, or properly calculate TR
    # Proper TR calculation:
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.DataFrame(np.maximum(np.maximum(tr1.values, tr2.values), tr3.values), index=close.index, columns=close.columns)
    bundle['ATR'] = tr.rolling(20).mean()
    
    # RS_Alpha (Absolute Momentum: 3-month performance ratio)
    bundle['RS_Alpha'] = (close / close.shift(60) - 1.0) * 100

    # Turnover (Value) calculation for liquidity filtering
    if vol is not None:
        turnover = close * vol
        bundle['Turnover'] = turnover.rolling(5).median() # 5-day median turnover
    
    return bundle

def detect_market_regime(data_df=None, buffer=None):
    """
    V168.0 Strict Market Regime Filter:
    - BULL: 価格が長期SMA200を上回り、かつ長期SMAが上昇傾向
    - BEAR: 価格が長期SMA200を下回っている（この間は全エントリー停止）
    """
    regime = "NEUTRAL"
    is_trend_snapped = False
    
    if data_df is not None:
        try:
            close_all = data_df.xs('Close', axis=1, level=1)
            if '1321.T' in close_all.columns:
                c_1321 = close_all['1321.T']
                sma_trend = c_1321.rolling(SMA_TREND_PERIOD).mean()
                sma_short = c_1321.rolling(SMA_SHORT_PERIOD).mean()
                
                curr_p = c_1321.iloc[-1]
                curr_sma_trend = sma_trend.iloc[-1]
                prev_sma_trend = sma_trend.iloc[-10] # 2 weeks ago
                slope = (curr_sma_trend / prev_sma_trend - 1.0) * 100
                
                # ベア判定を厳格化: SMA200を下回ったら即座にBEAR（ブロック）
                if curr_p < curr_sma_trend:
                    regime = "BEAR"
                elif slope > 0.01: # 緩やかな上昇トレンド
                    regime = "BULL"
                
                if curr_p < sma_short.iloc[-1]:
                    is_trend_snapped = True
        except: pass
        
    return regime, is_trend_snapped

def select_best_candidates(data_df, targets, symbols_df, regime, breadth_val=0.0):
    """
    Day-trade candidate selection:
    - Prioritize oversold rebound setups instead of trend breakouts.
    - Use previous ATR and previous bearish candle for gap-up continuation.
    """
    bundle = calculate_all_technicals_v12(data_df)
    market_open = np.nan
    prev_market_sma_trend = np.nan
    try:
        if "1321.T" in bundle["Open"].columns and len(bundle["Open"]) >= 2:
            market_open = bundle["Open"]["1321.T"].iloc[-1]
            prev_market_sma_trend = bundle[f"SMA{SMA_TREND_PERIOD}"]["1321.T"].iloc[-2]
    except Exception:
        market_open = np.nan
        prev_market_sma_trend = np.nan
    if not is_daytrade_market_allowed(
        breadth_val,
        market_open=market_open,
        prev_market_sma_trend=prev_market_sma_trend,
    ):
        return []
    
    close = bundle['Close'].iloc[-1]
    prev_close = bundle['Close'].iloc[-2]  # 前日終値（ギャップ計算用）
    prev_prev_close = bundle['Close'].iloc[-3] if len(bundle['Close']) >= 3 else bundle['Close'].iloc[-2]
    open_p = bundle['Open'].iloc[-1]
    prev_open = bundle['Open'].iloc[-2]
    prev_low = data_df.xs('Low', axis=1, level=1).iloc[-2]
    rsi2 = bundle['RSI2'].iloc[-1]
    sma_med = bundle[f'SMA{SMA_MEDIUM_PERIOD}'].iloc[-1]
    sma_trend = bundle[f'SMA{SMA_TREND_PERIOD}'].iloc[-1]
    atr = bundle['ATR'].iloc[-1]
    prev_atr = bundle['ATR'].iloc[-2]
    rs_alpha = bundle['RS_Alpha'].iloc[-1]
    turnover = bundle['Turnover'].iloc[-1] if 'Turnover' in bundle else None
    
    candidates = []
    for t_with_t in [f"{t}.T" for t in targets]:
        if t_with_t not in close.index: continue
        
        p = close[t_with_t]
        o = open_p[t_with_t]
        r2 = rsi2[t_with_t]
        s_med = sma_med[t_with_t]
        s_trend = sma_trend[t_with_t] if t_with_t in sma_trend.index else np.nan
        rs = rs_alpha[t_with_t]
        pa = prev_atr[t_with_t] if t_with_t in prev_atr.index else np.nan
        po = prev_open[t_with_t] if t_with_t in prev_open.index else np.nan
        pl = prev_low[t_with_t] if t_with_t in prev_low.index else np.nan
        p_prev_prev = prev_prev_close[t_with_t] if t_with_t in prev_prev_close.index else np.nan
        
        if pd.isna(p) or p <= 0 or pd.isna(pa) or pa <= 0:
            continue
        if o < MIN_PRICE or o > MAX_PRICE:
            continue

        p_prev = prev_close[t_with_t] if t_with_t in prev_close.index else 0
        if p_prev <= 0:
            continue
        if turnover is not None and turnover[t_with_t] < DAYTRADE_MIN_TURNOVER:
            continue
        if _is_invalid_number(s_trend):
            continue
        if p_prev <= s_trend:
            continue

        metrics = evaluate_daytrade_setup(
            p, o, p_prev, s_med, breadth_val,
            prev_open=po, prev_atr=pa, prev_low=pl, rs_alpha=rs,
            rsi2=r2, prev_prev_close=p_prev_prev
        )

        if metrics is not None:
            code_only = t_with_t.replace(".T", "")
            name = "Target"
            if symbols_df is not None:
                match = symbols_df[symbols_df['コード'].astype(str) == code_only]
                if not match.empty: name = match.iloc[0]['銘柄名']

            score = score_daytrade_setup(
                metrics,
                rsi2=r2,
                rs_alpha=rs,
                prev_close=p_prev,
                prev_prev_close=p_prev_prev,
                prev_atr=pa
            )
            if score < DAYTRADE_MIN_SETUP_SCORE:
                continue
            
            candidates.append({
                "code": code_only,
                "name": name,
                "price": p,
                "atr": pa,
                "rs": rs,
                "rsi2": r2,
                "adv_yen": turnover[t_with_t] if turnover is not None else 0,
                "gap_pct": metrics["gap_pct"],
                "prev_body_atr": metrics["prev_body_atr"],
                "recovery_atr": metrics["intraday_recovery_atr"],
                "score": score
            })

    candidates = sorted(candidates, key=lambda x: x['score'], reverse=True)
    return candidates 

class RealtimeBuffer:
    def __init__(self, code, initial_df=None, interval_mins=15):
        self.code = code
        self.latest_price = 0
        self.latest_volume = 0
        self.prices = [] # Simplified history for RSI2
        self.session_open = 0
        self.session_high = 0
        self.session_low = 0
        self.last_trade_date = None
        
    def update(self, price, volume, server_time, open_price=None, high_price=None, low_price=None):
        trade_date = None
        if server_time is not None:
            trade_date = getattr(server_time, "date", lambda: None)()
        if trade_date is not None and trade_date != self.last_trade_date:
            self.session_open = 0
            self.session_high = 0
            self.session_low = 0
            self.last_trade_date = trade_date

        if price and price > 0:
            if self.latest_price != price:
                self.prices.append(price)
            self.latest_price = price
            self.latest_volume = volume
            if len(self.prices) > 20: self.prices = self.prices[-20:]
            if self.session_open <= 0:
                self.session_open = float(open_price or price)
            session_high = float(high_price or price)
            session_low = float(low_price or price)
            self.session_high = max(float(self.session_high or 0), session_high)
            if self.session_low <= 0:
                self.session_low = session_low
            else:
                self.session_low = min(float(self.session_low), session_low)
            
    def get_latest_price(self):
        return self.latest_price

    def get_session_open(self):
        return float(self.session_open or 0)

    def get_session_high(self):
        return float(self.session_high or 0)

    def get_session_low(self):
        return float(self.session_low or 0)

    def get_current_rsi2(self):
        if len(self.prices) < 3: return 50
        diffs = np.diff(self.prices[-3:])
        ups = [d if d > 0 else 0 for d in diffs]
        downs = [abs(d) if d < 0 else 0 for d in diffs]
        avg_up = np.mean(ups)
        avg_down = np.mean(downs)
        if avg_down == 0: return 100
        rs = avg_up / avg_down
        return 100 - (100 / (1 + rs))


def compute_daytrade_rebound_trigger(reference_open, atr, confirm_atr=DAYTRADE_REBOUND_CONFIRM_ATR):
    if _is_invalid_number(reference_open) or _is_invalid_number(atr):
        return 0.0
    if float(reference_open) <= 0 or float(atr) <= 0:
        return 0.0
    return float(reference_open) + (float(atr) * float(confirm_atr))


def has_daytrade_rebound_confirmation(current_price, reference_open, atr, confirm_atr=DAYTRADE_REBOUND_CONFIRM_ATR):
    trigger_price = compute_daytrade_rebound_trigger(reference_open, atr, confirm_atr=confirm_atr)
    if trigger_price <= 0:
        return False
    return float(current_price) >= float(trigger_price)

def load_invalid_tickers():
    try:
        with open(EXCLUSION_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_invalid_tickers(invalid_map):
    try:
        with open(EXCLUSION_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(invalid_map, f, indent=4)
    except:
        pass

def normalize_tick_size(price, is_buy=True):
    return round(price, 1)

def get_prime_tickers():
    from core.config import DATA_FILE
    import os
    if not os.path.exists(DATA_FILE): return []
    df = pd.read_csv(DATA_FILE)
    if '市場・商品区分' in df.columns:
        prime = df[df['市場・商品区分'].str.contains('プライム', na=False)]
        return [f"{str(code)}.T" for code in prime['コード']]
    return []

def calculate_lot_size(current_equity, atr, sl_mult, price, dynamic_leverage, 
                       max_positions, buying_power=None, turnover=None):
    """
    Shared sizing logic.
    1. Target Allocation = (Current Equity * dynamic leverage) / MAX_POSITIONS
    2. Shares = floor(Target Allocation / Close, unit=100)
    3. Minimum: 100 shares (skipped if less)
    """
    if price <= 0 or max_positions <= 0 or dynamic_leverage <= 0:
        return 0

    total_assets = current_equity if USE_COMPOUNDING else INITIAL_CASH
    target_allocation = (total_assets * float(dynamic_leverage)) / max_positions
    final_shares = _floor_lot(target_allocation // price)

    if buying_power is not None:
        max_bp_shares = _floor_lot((buying_power * 0.95) // price)
        final_shares = min(final_shares, max_bp_shares)

    return final_shares


def cap_daytrade_position_size(raw_shares, current_equity, buying_power, entry_price, stop_price):
    shares = _floor_lot(raw_shares)
    if shares < 100 or current_equity <= 0 or buying_power <= 0 or entry_price <= 0:
        return 0

    risk_per_share = max(float(entry_price) - float(stop_price), float(entry_price) * 0.001)
    if risk_per_share <= 0:
        return 0

    risk_budget_shares = _floor_lot((float(current_equity) * DAYTRADE_RISK_PER_TRADE_PCT) / risk_per_share)
    notional_cap_shares = _floor_lot((float(buying_power) * DAYTRADE_MAX_NOTIONAL_PCT) / float(entry_price))
    capped_shares = min(shares, risk_budget_shares, notional_cap_shares)
    return capped_shares if capped_shares >= 100 else 0

