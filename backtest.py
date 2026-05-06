import numpy as np
import pandas as pd
from core.logic import (
    calculate_dynamic_leverage, calculate_lot_size, calculate_position_stops,
    evaluate_daytrade_open_setup, score_daytrade_open_setup,
    evaluate_daytrade_fallback_open_setup, score_daytrade_fallback_open_setup,
    evaluate_daytrade_strong_oversold_open_setup, score_daytrade_strong_oversold_open_setup,
    evaluate_daytrade_catchup_open_setups, score_daytrade_catchup_open_setup,
    evaluate_daytrade_inverse_open_setup, score_daytrade_inverse_open_setup,
    is_daytrade_market_allowed, is_daytrade_fallback_market_allowed,
    is_daytrade_strong_oversold_market_allowed,
    is_daytrade_catchup_market_allowed, is_daytrade_inverse_market_allowed,
    is_daytrade_inverse_pullback_market_allowed,
    is_daytrade_trend_allowed,
    is_daytrade_inverse_setup_type,
    select_daytrade_candidates,
    get_daytrade_week_key, resolve_daytrade_weekly_leverage,
    is_daytrade_weekly_profit_guard_active,
    is_daytrade_monthly_risk_blocked,
    resolve_daytrade_intraday_stop_mult, resolve_daytrade_intraday_target_mult,
    resolve_daytrade_buying_power,
    resolve_daytrade_inverse_buying_power,
    cap_daytrade_position_size,
    resolve_daytrade_breadth_exposure_scale,
    DAYTRADE_MAX_DAILY_LOSS_PCT, DAYTRADE_MAX_GAP, DAYTRADE_MAX_RSI2,
    DAYTRADE_MIN_SETUP_SCORE,
    DAYTRADE_MIN_PREV_DAY_RETURN_PCT, DAYTRADE_MAX_PREV_DAY_RETURN_PCT,
    DAYTRADE_MIN_TURNOVER, DAYTRADE_FALLBACK_MIN_SETUP_SCORE,
    DAYTRADE_FALLBACK_MAX_NOTIONAL_PCT, DAYTRADE_MAX_NOTIONAL_PCT,
    DAYTRADE_STRONG_OVERSOLD_MIN_SETUP_SCORE, DAYTRADE_STRONG_OVERSOLD_NOTIONAL_PCT,
    DAYTRADE_STRONG_OVERSOLD_EQUITY_NOTIONAL_PCT, DAYTRADE_STRONG_OVERSOLD_STOP_MULT,
    DAYTRADE_STRONG_OVERSOLD_TARGET_MULT,
    DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT, DAYTRADE_FALLBACK_TREND_BUFFER,
    DAYTRADE_FALLBACK_INTRADAY_STOP_MULT, DAYTRADE_FALLBACK_INTRADAY_TARGET_MULT,
    DAYTRADE_CATCHUP_MIN_TURNOVER, DAYTRADE_CATCHUP_MIN_SETUP_SCORE,
    DAYTRADE_CATCHUP_GAPDOWN_STOP_MULT, DAYTRADE_CATCHUP_GAPDOWN_TARGET_MULT,
    DAYTRADE_CATCHUP_GAPDOWN_NOTIONAL_PCT, DAYTRADE_CATCHUP_GAPDOWN_EQUITY_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_RS_STOP_MULT, DAYTRADE_CATCHUP_RS_TARGET_MULT,
    DAYTRADE_CATCHUP_RS_NOTIONAL_PCT, DAYTRADE_CATCHUP_RS_EQUITY_NOTIONAL_PCT,
    DAYTRADE_INVERSE_CODES, DAYTRADE_INVERSE_MIN_TURNOVER, DAYTRADE_INVERSE_MIN_SETUP_SCORE,
    DAYTRADE_INVERSE_STOP_MULT, DAYTRADE_INVERSE_TARGET_MULT,
    DAYTRADE_INVERSE_PULLBACK_STOP_MULT, DAYTRADE_INVERSE_PULLBACK_TARGET_MULT,
    DAYTRADE_INVERSE_NOTIONAL_PCT, DAYTRADE_INVERSE_EQUITY_NOTIONAL_PCT,
    DAYTRADE_INVERSE_BUYING_POWER_LEVERAGE,
)
from core.config import (
    SMA_SHORT_PERIOD, SMA_MEDIUM_PERIOD, SMA_TREND_PERIOD, SMA_LONG_PERIOD,
    SLIPPAGE, BREADTH_THRESHOLD, TAX_RATE,
    BEAR_GAP_LIMIT, LEVERAGE_RATE, MAX_POSITIONS, STOP_LOSS_ATR, TAKE_PROFIT_ATR,
    MIN_PRICE, MAX_PRICE,
)
from core.monthly_rotation_strategy import (
    MonthlyRotationStrategyConfig,
    build_rotation_entry_plan,
    build_rotation_rebalance_plan,
    compute_rotation_order_size,
    is_rotation_regime_bull,
    select_monthly_rotation_candidates_from_snapshot,
)
from core.jquants_margin_cache import get_eligible_margin_codes_for_date

MIN_SETUP_SCORE = DAYTRADE_MIN_SETUP_SCORE
MAX_DAILY_LOSS_PCT = DAYTRADE_MAX_DAILY_LOSS_PCT


def _floor_lot(shares):
    return max(0, (int(shares) // 100) * 100)


def _apply_profit_tax(realized_pnl, tax_rate=TAX_RATE):
    pnl = float(realized_pnl)
    if pnl <= 0:
        return pnl, 0.0
    tax = pnl * float(tax_rate)
    return pnl - tax, tax


def _apply_margin_interest(cash, positions, close_np, row_idx, annual_interest_rate):
    if not positions or annual_interest_rate <= 0:
        return float(cash), 0.0

    borrowed_notional = sum(
        float(position.get("financing_notional", position["buy_price"] * position["shares"]))
        for position in positions.values()
    )
    if borrowed_notional <= 0:
        return float(cash), 0.0

    daily_interest = borrowed_notional * (float(annual_interest_rate) / 365.0)
    return float(cash) - float(daily_interest), float(daily_interest)


def _cap_shares_by_liquidity(desired_shares, execution_price, turnover_value, liquidity_limit):
    shares = int(desired_shares)
    if shares < 100 or execution_price <= 0 or liquidity_limit <= 0:
        return max(0, (shares // 100) * 100)
    if not np.isfinite(turnover_value) or turnover_value <= 0:
        return 0

    max_notional = float(turnover_value) * float(liquidity_limit)
    max_shares = _floor_lot(max_notional // float(execution_price))
    return min(_floor_lot(shares), max_shares)


def _resolve_intraday_exit(entry_price, open_price, high_price, low_price, close_price, stop_price, target_price):
    """
    Resolve a same-day OHLC exit with conservative assumptions.
    If both stop and target are touched intraday, prefer the stop so results are not luck-dependent.
    """
    values = [entry_price, open_price, high_price, low_price, close_price, stop_price, target_price]
    if np.any(np.isnan(values)):
        return close_price, "missing_ohlc_fallback"

    if open_price <= stop_price:
        return open_price, "open_stop"
    if open_price >= target_price:
        return open_price, "open_target"

    stop_hit = low_price <= stop_price
    target_hit = high_price >= target_price

    if stop_hit and target_hit:
        return stop_price, "intraday_stop_priority"
    if stop_hit:
        return stop_price, "intraday_stop"
    if target_hit:
        return target_price, "intraday_target"
    return close_price, "close_exit"


def _resolve_execution_slippage(rate, override):
    if override is None:
        return float(rate)
    return float(override)


def run_backtest_v17_swing(univ_indices, bundle_np, timeline, breadth_ratio,
                           initial_cash=1000000, max_pos=3,
                           sl_mult=3.0, tp_mult=20.0, leverage_rate=1.0, breadth_threshold=0.50,
                           slippage=SLIPPAGE, use_sma_exit=True,
                           exit_buffer=0.975, max_hold_days=20,
                           liquidity_limit=0.025, bull_gap_limit=0.13, bear_gap_limit=0.02,
                           atr_trail_mult=3.0, rsi_threshold=70.0,
                           verbose=False):
    """
    Multi-day swing backtest:
    - Buys strong trend leaders near breakouts.
    - Holds positions across sessions with ATR-based risk control.
    - Exits on trend breaks, stops, targets, overextension, or time stop.
    """
    T = len(timeline)
    cash = float(initial_cash)
    portfolio = []
    trade_count = 0
    monthly_assets = {}
    trade_results = []

    close_np = bundle_np["Close"]
    open_np = bundle_np["Open"]
    high_np = bundle_np["High"]
    low_np = bundle_np["Low"]
    atr_np = bundle_np["ATR"]
    rsi2_np = bundle_np["RSI2"]
    rs_alpha_np = bundle_np.get("RS_Alpha", np.zeros_like(close_np))
    sma_short_np = bundle_np.get(f"SMA{SMA_SHORT_PERIOD}", np.zeros_like(close_np))
    sma_med_np = bundle_np.get(f"SMA{SMA_MEDIUM_PERIOD}", np.zeros_like(close_np))
    sma_long_np = bundle_np.get(f"SMA{SMA_LONG_PERIOD}", np.zeros_like(close_np))
    sma_trend_np = bundle_np.get(f"SMA{SMA_TREND_PERIOD}", np.zeros_like(close_np))
    turnover_np = bundle_np.get("Turnover", np.ones_like(close_np) * 1e12)
    high20_np = bundle_np.get("High20")

    if high20_np is None:
        rolling_high20 = []
        for idx in range(close_np.shape[1]):
            series = high_np[:, idx]
            values = np.full(T, np.nan)
            for i in range(20, T):
                values[i] = np.nanmax(series[i - 20:i])
            rolling_high20.append(values)
        high20_np = np.column_stack(rolling_high20)

    idx_1321 = -1
    for idx_t, ticker in enumerate(bundle_np["tickers"]):
        if ticker == "1321.T":
            idx_1321 = idx_t
            break

    current_month = ""
    month_start_equity = initial_cash
    month_done = False
    cooling_days = 0

    for i in range(20, T):
        curr_time = timeline[i]

        if cooling_days > 0:
            cooling_days -= 1

        if curr_time.strftime("%Y-%m") != current_month:
            current_month = curr_time.strftime("%Y-%m")
            month_start_equity = cash + sum(np.nan_to_num(close_np[i, p["s_idx"]]) * p["shares"] for p in portfolio)
            month_done = False

        total_equity = cash + sum(np.nan_to_num(close_np[i, p["s_idx"]]) * p["shares"] for p in portfolio)
        month_drawdown = (total_equity / month_start_equity) - 1.0 if month_start_equity > 0 else 0.0
        if month_drawdown <= -0.10:
            month_done = True

        regime_is_bull = breadth_ratio[i] >= breadth_threshold
        if idx_1321 != -1:
            index_close = close_np[i, idx_1321]
            index_trend = sma_trend_np[i, idx_1321]
            index_short = sma_short_np[i, idx_1321]
            regime_is_bull = regime_is_bull and np.isfinite(index_trend) and index_close > index_trend and index_close > index_short

        new_portfolio = []
        for position in portfolio:
            s_idx = position["s_idx"]
            t_open = open_np[i, s_idx]
            t_high = high_np[i, s_idx]
            t_low = low_np[i, s_idx]
            t_close = close_np[i, s_idx]
            t_sma_med = sma_med_np[i, s_idx]
            t_atr = atr_np[i, s_idx]
            t_rsi2 = rsi2_np[i, s_idx]

            if np.any(np.isnan([t_open, t_high, t_low, t_close, t_sma_med, t_atr])):
                new_portfolio.append(position)
                continue

            position["max_price"] = max(position.get("max_price", position["buy_price"]), t_high)
            stop_price, target_price = calculate_position_stops(
                position["buy_price"], position["buy_atr"], position["max_price"], t_close, sl_mult, tp_mult
            )
            trail_price = position["max_price"] - (position["buy_atr"] * atr_trail_mult)
            stop_price = max(stop_price, trail_price)

            exit_price = None
            if use_sma_exit and t_close < (t_sma_med * exit_buffer):
                exit_price = t_close
            elif t_open <= stop_price:
                exit_price = t_open
            elif t_low <= stop_price:
                exit_price = stop_price
            elif t_open >= target_price:
                exit_price = t_open
            elif t_high >= target_price:
                exit_price = target_price
            elif np.isfinite(t_rsi2) and t_rsi2 >= rsi_threshold:
                exit_price = t_close
            elif position["held_days"] >= max_hold_days:
                exit_price = t_close
            elif month_done or not regime_is_bull:
                exit_price = t_close

            if exit_price is not None:
                real_exit = exit_price * (1.0 - slippage)
                pnl = (real_exit - position["buy_price"]) * position["shares"]
                cash += real_exit * position["shares"]
                trade_results.append(pnl)
                cooling_days = max(cooling_days, 1)
            else:
                position["held_days"] += 1
                new_portfolio.append(position)

        portfolio = new_portfolio
        total_equity = cash + sum(np.nan_to_num(close_np[i, p["s_idx"]]) * p["shares"] for p in portfolio)
        monthly_assets[current_month] = float(total_equity)

        if i + 1 >= T or month_done or cooling_days > 0 or not regime_is_bull:
            continue

        dynamic_lev = calculate_dynamic_leverage(breadth_ratio[i], config_leverage=leverage_rate)
        if dynamic_lev <= 0:
            continue

        current_exposure = sum(np.nan_to_num(close_np[i, p["s_idx"]]) * p["shares"] for p in portfolio)
        buying_power = max(0.0, (total_equity * dynamic_lev) - current_exposure)
        if buying_power <= 0:
            continue

        candidates = []
        for s_idx in univ_indices:
            if any(p["s_idx"] == s_idx for p in portfolio):
                continue

            values = [
                close_np[i, s_idx], open_np[i + 1, s_idx], high_np[i, s_idx], low_np[i, s_idx], atr_np[i, s_idx],
                sma_short_np[i, s_idx], sma_med_np[i, s_idx], sma_long_np[i, s_idx], sma_trend_np[i, s_idx],
                rs_alpha_np[i, s_idx], turnover_np[i, s_idx], high20_np[i, s_idx]
            ]
            if np.any(np.isnan(values)):
                continue

            t_close = close_np[i, s_idx]
            next_open = open_np[i + 1, s_idx]
            t_atr = atr_np[i, s_idx]
            t_rs = rs_alpha_np[i, s_idx]
            t_turnover = turnover_np[i, s_idx]
            breakout_level = high20_np[i, s_idx]
            prev_close = close_np[i - 1, s_idx]
            gap_pct = (next_open / t_close) - 1.0 if t_close > 0 else np.nan

            if t_close <= 0 or next_open <= 0 or t_atr <= 0 or t_turnover <= 0:
                continue
            if liquidity_limit > 0 and (next_open * 100.0) > (t_turnover * liquidity_limit):
                continue
            if gap_pct > bull_gap_limit or gap_pct < -bear_gap_limit:
                continue
            if t_rs < 15.0:
                continue
            if t_close < sma_short_np[i, s_idx] or t_close < sma_med_np[i, s_idx] or t_close < sma_long_np[i, s_idx]:
                continue
            if sma_long_np[i, s_idx] < sma_long_np[i - 5, s_idx]:
                continue
            if sma_trend_np[i, s_idx] > 0 and t_close < sma_trend_np[i, s_idx]:
                continue
            if breakout_level > 0 and t_close < breakout_level * 0.985:
                continue
            if prev_close > 0 and t_close < prev_close:
                continue

            distance_to_breakout = abs(t_close - breakout_level) / t_atr if breakout_level > 0 else 0.0
            momentum_bonus = max(0.0, (t_close / prev_close) - 1.0) if prev_close > 0 else 0.0
            score = (t_rs / 10.0) + (momentum_bonus * 200.0) - distance_to_breakout
            candidates.append((score, s_idx, next_open, t_atr, t_turnover))

        candidates.sort(reverse=True)
        open_slots = max(0, max_pos - len(portfolio))
        for score, s_idx, entry_open, entry_atr, entry_turnover in candidates[:open_slots]:
            real_buy = entry_open * (1.0 + slippage)
            shares = calculate_lot_size(
                current_equity=total_equity,
                atr=entry_atr,
                sl_mult=sl_mult,
                price=real_buy,
                dynamic_leverage=dynamic_lev,
                max_positions=max_pos,
                buying_power=buying_power,
                turnover=entry_turnover
            )
            if shares < 100:
                continue

            trade_notional = real_buy * shares
            if trade_notional > buying_power:
                continue

            portfolio.append({
                "s_idx": s_idx,
                "buy_price": real_buy,
                "shares": shares,
                "held_days": 0,
                "max_price": real_buy,
                "buy_atr": entry_atr,
            })
            cash -= trade_notional
            buying_power -= trade_notional
            trade_count += 1
            if len(portfolio) >= max_pos:
                break

    final = cash + sum(np.nan_to_num(close_np[-1, p["s_idx"]]) * p["shares"] for p in portfolio)
    return float(final), trade_count, monthly_assets, trade_results


def run_backtest_v18_pullback(univ_indices, bundle_np, timeline, breadth_ratio,
                              initial_cash=1000000, max_pos=1,
                              sl_mult=1.5, tp_mult=4.0, leverage_rate=1.0, breadth_threshold=0.65,
                              slippage=SLIPPAGE, use_sma_exit=True,
                              exit_buffer=0.98, max_hold_days=8,
                              liquidity_limit=0.025, bull_gap_limit=0.13, bear_gap_limit=0.02,
                              atr_trail_mult=1.5, rsi_threshold=60.0,
                              verbose=False):
    """
    Trend pullback swing backtest:
    - Only trades strong uptrends in liquid names.
    - Enters on end-of-day pullbacks near SMA20 after short-term exhaustion.
    - Exits with tight ATR stop, trailing stop, and fast mean-reversion profit taking.
    """
    T = len(timeline)
    cash = float(initial_cash)
    portfolio = []
    trade_count = 0
    monthly_assets = {}
    trade_results = []

    close_np = bundle_np["Close"]
    high_np = bundle_np["High"]
    low_np = bundle_np["Low"]
    atr_np = bundle_np["ATR"]
    rsi2_np = bundle_np["RSI2"]
    rs_alpha_np = bundle_np.get("RS_Alpha", np.zeros_like(close_np))
    sma_short_np = bundle_np.get(f"SMA{SMA_SHORT_PERIOD}", np.zeros_like(close_np))
    sma_med_np = bundle_np.get(f"SMA{SMA_MEDIUM_PERIOD}", np.zeros_like(close_np))
    sma_long_np = bundle_np.get(f"SMA{SMA_LONG_PERIOD}", np.zeros_like(close_np))
    sma_trend_np = bundle_np.get(f"SMA{SMA_TREND_PERIOD}", np.zeros_like(close_np))
    turnover_np = bundle_np.get("Turnover", np.ones_like(close_np) * 1e12)

    idx_1321 = -1
    for idx_t, ticker in enumerate(bundle_np["tickers"]):
        if ticker == "1321.T":
            idx_1321 = idx_t
            break

    current_month = ""
    month_start_equity = initial_cash
    month_done = False

    for i in range(max(220, SMA_TREND_PERIOD), T):
        curr_time = timeline[i]
        if curr_time.strftime("%Y-%m") != current_month:
            current_month = curr_time.strftime("%Y-%m")
            month_start_equity = cash + sum(np.nan_to_num(close_np[i, p["s_idx"]]) * p["shares"] for p in portfolio)
            month_done = False

        total_equity = cash + sum(np.nan_to_num(close_np[i, p["s_idx"]]) * p["shares"] for p in portfolio)
        month_drawdown = (total_equity / month_start_equity) - 1.0 if month_start_equity > 0 else 0.0
        if month_drawdown <= -0.10:
            month_done = True

        regime_is_bull = breadth_ratio[i] >= breadth_threshold
        if idx_1321 != -1:
            idx_close = close_np[i, idx_1321]
            idx_sma_trend = sma_trend_np[i, idx_1321]
            regime_is_bull = regime_is_bull and np.isfinite(idx_sma_trend) and idx_close > idx_sma_trend

        new_portfolio = []
        for position in portfolio:
            s_idx = position["s_idx"]
            t_close = close_np[i, s_idx]
            t_high = high_np[i, s_idx]
            t_low = low_np[i, s_idx]
            t_sma_short = sma_short_np[i, s_idx]
            t_sma_med = sma_med_np[i, s_idx]
            t_rsi2 = rsi2_np[i, s_idx]

            if np.any(np.isnan([t_close, t_high, t_low, t_sma_short, t_sma_med, t_rsi2])):
                new_portfolio.append(position)
                continue

            position["max_price"] = max(position["max_price"], t_high)
            stop_price = max(
                position["buy_price"] - (position["buy_atr"] * sl_mult),
                position["max_price"] - (position["buy_atr"] * atr_trail_mult),
            )
            target_price = position["buy_price"] + (position["buy_atr"] * tp_mult)

            exit_price = None
            if t_low <= stop_price:
                exit_price = stop_price
            elif t_high >= target_price:
                exit_price = target_price
            elif use_sma_exit and t_close < (t_sma_med * exit_buffer):
                exit_price = t_close
            elif t_close > t_sma_short and t_rsi2 >= rsi_threshold:
                exit_price = t_close
            elif position["held_days"] >= max_hold_days:
                exit_price = t_close
            elif month_done or not regime_is_bull:
                exit_price = t_close

            if exit_price is not None:
                real_exit = exit_price * (1.0 - slippage)
                pnl = (real_exit - position["buy_price"]) * position["shares"]
                cash += real_exit * position["shares"]
                trade_results.append(pnl)
            else:
                position["held_days"] += 1
                new_portfolio.append(position)

        portfolio = new_portfolio
        total_equity = cash + sum(np.nan_to_num(close_np[i, p["s_idx"]]) * p["shares"] for p in portfolio)
        monthly_assets[current_month] = float(total_equity)

        if month_done or not regime_is_bull:
            continue

        open_slots = max_pos - len(portfolio)
        if open_slots <= 0:
            continue

        current_exposure = sum(np.nan_to_num(close_np[i, p["s_idx"]]) * p["shares"] for p in portfolio)
        buying_power = max(0.0, (total_equity * leverage_rate) - current_exposure)
        if buying_power <= 0:
            continue

        candidates = []
        for s_idx in univ_indices:
            if any(p["s_idx"] == s_idx for p in portfolio):
                continue

            values = [
                close_np[i, s_idx], close_np[i - 1, s_idx], atr_np[i, s_idx], rsi2_np[i, s_idx], rs_alpha_np[i, s_idx],
                sma_med_np[i, s_idx], sma_long_np[i, s_idx], sma_trend_np[i, s_idx], turnover_np[i, s_idx]
            ]
            if np.any(np.isnan(values)):
                continue

            t_close = close_np[i, s_idx]
            prev_close = close_np[i - 1, s_idx]
            t_atr = atr_np[i, s_idx]
            t_rsi2 = rsi2_np[i, s_idx]
            t_rs = rs_alpha_np[i, s_idx]
            t_sma_med = sma_med_np[i, s_idx]
            t_sma_long = sma_long_np[i, s_idx]
            t_sma_trend = sma_trend_np[i, s_idx]
            t_turnover = turnover_np[i, s_idx]

            if t_close <= 0 or t_atr <= 0 or t_turnover <= 0:
                continue
            if liquidity_limit > 0 and (t_close * 100.0) > (t_turnover * liquidity_limit):
                continue
            if t_rs < 30.0:
                continue
            if t_close < t_sma_long or t_close < t_sma_trend:
                continue
            if t_sma_long < sma_long_np[i - 5, s_idx]:
                continue

            pullback_ratio = t_close / t_sma_med if t_sma_med > 0 else np.nan
            one_day_change = (t_close / prev_close) - 1.0 if prev_close > 0 else np.nan
            if not np.isfinite(pullback_ratio) or not np.isfinite(one_day_change):
                continue
            if pullback_ratio > 1.0 or pullback_ratio < 0.96:
                continue
            if t_rsi2 > 8.0:
                continue
            if one_day_change > 0.01:
                continue

            distance_score = max(0.0, (1.0 - pullback_ratio) * 100.0)
            score = t_rs + distance_score - (t_rsi2 * 0.5)
            candidates.append((score, s_idx, t_close, t_atr))

        candidates.sort(reverse=True)
        for score, s_idx, entry_close, entry_atr in candidates[:open_slots]:
            real_buy = entry_close * (1.0 + slippage)
            alloc = min(buying_power, total_equity * 0.9)
            shares = _floor_lot(alloc // real_buy)
            if shares < 100:
                continue

            trade_notional = real_buy * shares
            if trade_notional > buying_power:
                continue

            cash -= trade_notional
            buying_power -= trade_notional
            portfolio.append({
                "s_idx": s_idx,
                "buy_price": real_buy,
                "shares": shares,
                "buy_atr": entry_atr,
                "held_days": 0,
                "max_price": real_buy,
            })
            trade_count += 1
            if len(portfolio) >= max_pos:
                break

    final = cash + sum(np.nan_to_num(close_np[-1, p["s_idx"]]) * p["shares"] for p in portfolio)
    return float(final), trade_count, monthly_assets, trade_results


def run_backtest_v19_monthly_rotation(univ_indices, bundle_np, timeline, breadth_ratio,
                                      initial_cash=1000000, max_pos=3,
                                      sl_mult=3.0, tp_mult=20.0, leverage_rate=1.0, breadth_threshold=0.45,
                                      slippage=SLIPPAGE, use_sma_exit=True,
                                      exit_buffer=0.975, max_hold_days=30,
                                      liquidity_limit=0.025, bull_gap_limit=0.13, bear_gap_limit=0.02,
                                      atr_trail_mult=3.0, rsi_threshold=30.0,
                                      verbose=False,
                                      min_turnover=1_000_000_000.0,
                                      rs_min=0.0,
                                      atr_ratio_max=1.0,
                                      rank_mode="rs",
                                      hold_score_bonus=0.0,
                                      hold_rank_tolerance=0.0,
                                      score_weight_power=0.0,
                                      rebalance_existing=False,
                                      mom20_score_weight=0.0,
                                      mom60_score_weight=0.0,
                                      atr_penalty_weight=0.0,
                                      trend_gap_score_weight=0.0,
                                      mom20_min=-10.0,
                                      mom60_min=-10.0,
                                      mom20_cap=10.0,
                                      mom60_cap=10.0,
                                      dynamic_topn=False,
                                      require_stock_sma20=False,
                                      use_index_sma20=False,
                                      index_mom1_min=None,
                                      breadth_delta_min=None,
                                      tax_rate=TAX_RATE,
                                      annual_margin_interest_rate=0.0279,
                                      eligible_codes_by_date=None):
    """
    Monthly rotation backtest:
    - Rebalances only at month-end.
    - Holds the strongest liquid Prime stocks while market breadth is healthy.
    - Goes to cash when the broad market loses its long-term trend.
    """
    strategy_config = MonthlyRotationStrategyConfig(
        max_pos=max_pos,
        leverage_rate=leverage_rate,
        breadth_threshold=breadth_threshold,
        min_turnover=min_turnover,
        rs_min=rs_min,
        atr_ratio_max=atr_ratio_max,
        rank_mode=rank_mode,
        hold_score_bonus=hold_score_bonus,
        hold_rank_tolerance=hold_rank_tolerance,
        score_weight_power=score_weight_power,
        rebalance_existing=rebalance_existing,
        mom20_score_weight=mom20_score_weight,
        mom60_score_weight=mom60_score_weight,
        atr_penalty_weight=atr_penalty_weight,
        trend_gap_score_weight=trend_gap_score_weight,
        mom20_min=mom20_min,
        mom60_min=mom60_min,
        mom20_cap=mom20_cap,
        mom60_cap=mom60_cap,
        dynamic_topn=dynamic_topn,
        require_stock_sma20=require_stock_sma20,
        use_index_sma20=use_index_sma20,
        index_mom1_min=index_mom1_min,
        breadth_delta_min=breadth_delta_min,
        use_sma_exit=use_sma_exit,
        exit_buffer=exit_buffer,
    )
    T = len(timeline)
    cash = float(initial_cash)
    positions = {}
    trade_results = []
    trade_count = 0
    monthly_assets = {}

    close_np = bundle_np["Close"]
    open_np = bundle_np.get("Open", close_np)
    rs_alpha_np = bundle_np.get("RS_Alpha", np.zeros_like(close_np))
    turnover_np = bundle_np.get("Turnover", np.zeros_like(close_np))
    atr_np = bundle_np.get("ATR", np.zeros_like(close_np))
    sma_long_np = bundle_np.get(f"SMA{SMA_LONG_PERIOD}", np.zeros_like(close_np))
    sma_med_np = bundle_np.get(f"SMA{SMA_MEDIUM_PERIOD}", np.zeros_like(close_np))
    sma_trend_np = bundle_np.get(f"SMA{SMA_TREND_PERIOD}", np.zeros_like(close_np))
    close_shift_20 = np.roll(close_np, 20, axis=0)
    close_shift_20[:20, :] = np.nan
    close_shift_60 = np.roll(close_np, 60, axis=0)
    close_shift_60[:60, :] = np.nan

    idx_1321 = -1
    for idx_t, ticker in enumerate(bundle_np["tickers"]):
        if ticker == "1321.T":
            idx_1321 = idx_t
            break

    start_idx = max(60, SMA_TREND_PERIOD)
    for i in range(start_idx, T):
        curr_time = timeline[i]
        month_key = curr_time.strftime("%Y-%m")

        cash, _ = _apply_margin_interest(
            cash=cash,
            positions=positions,
            close_np=close_np,
            row_idx=i,
            annual_interest_rate=annual_margin_interest_rate,
        )
        current_equity = cash + sum(position["shares"] * close_np[i, s_idx] for s_idx, position in positions.items())

        is_month_end = (i == T - 1) or (timeline[i + 1].strftime("%Y-%m") != month_key)
        if not is_month_end:
            continue

        # Record the actual month-end snapshot before any next-session rebalance executes.
        monthly_assets[month_key] = float(current_equity)
        if i >= T - 1:
            continue

        all_tickers = bundle_np["tickers"]
        eligible_codes = None
        if eligible_codes_by_date:
            eligible_codes = get_eligible_margin_codes_for_date(eligible_codes_by_date, curr_time)
        universe_tickers = [
            all_tickers[s_idx]
            for s_idx in univ_indices
            if eligible_codes is None or all_tickers[s_idx].replace(".T", "") in eligible_codes
        ]
        idx_close = close_np[i, idx_1321] if idx_1321 != -1 else None
        idx_sma_trend = sma_trend_np[i, idx_1321] if idx_1321 != -1 else None
        idx_sma20 = sma_med_np[i, idx_1321] if idx_1321 != -1 else None
        idx_mom1 = None
        if idx_1321 != -1 and i >= 20 and close_np[i - 20, idx_1321] > 0:
            idx_mom1 = (close_np[i, idx_1321] / close_np[i - 20, idx_1321]) - 1.0
        prior_breadth = breadth_ratio[i - 21] if breadth_delta_min is not None and i >= 21 else None
        regime_is_bull = is_rotation_regime_bull(
            breadth_latest=breadth_ratio[i],
            idx_close=idx_close,
            idx_sma_trend=idx_sma_trend,
            idx_sma20=idx_sma20,
            idx_mom1=idx_mom1,
            prior_breadth=prior_breadth,
            config=strategy_config,
        )

        effective_max_pos = max_pos
        if dynamic_topn:
            if breadth_ratio[i] >= 0.75:
                effective_max_pos = max(max_pos, 6)
            elif breadth_ratio[i] >= 0.65:
                effective_max_pos = max(max_pos, 5)
            elif breadth_ratio[i] < 0.58:
                effective_max_pos = min(max_pos, 2)
            elif breadth_ratio[i] < 0.62:
                effective_max_pos = min(max_pos, 3)

        selected = []
        all_candidates = []
        if regime_is_bull and i < T - 1:
            snapshot = {
                "all_tickers": universe_tickers + (["1321.T"] if idx_1321 != -1 and "1321.T" not in universe_tickers else []),
                "prime_ref": set(universe_tickers + (["1321.T"] if idx_1321 != -1 else [])),
                "index_ticker": "1321.T",
                "close_map": {ticker: float(close_np[i, idx]) for idx, ticker in enumerate(all_tickers) if ticker in set(universe_tickers) or ticker == "1321.T"},
                "sma20_map": {ticker: float(sma_med_np[i, idx]) for idx, ticker in enumerate(all_tickers) if ticker in set(universe_tickers) or ticker == "1321.T"},
                "sma_long_map": {ticker: float(sma_long_np[i, idx]) for idx, ticker in enumerate(all_tickers) if ticker in set(universe_tickers) or ticker == "1321.T"},
                "sma_trend_map": {ticker: float(sma_trend_np[i, idx]) for idx, ticker in enumerate(all_tickers) if ticker in set(universe_tickers) or ticker == "1321.T"},
                "atr_map": {ticker: float(atr_np[i, idx]) for idx, ticker in enumerate(all_tickers) if ticker in set(universe_tickers) or ticker == "1321.T"},
                "rs_map": {ticker: float(rs_alpha_np[i, idx]) for idx, ticker in enumerate(all_tickers) if ticker in set(universe_tickers) or ticker == "1321.T"},
                "turnover_map": {ticker: float(turnover_np[i, idx]) for idx, ticker in enumerate(all_tickers) if ticker in set(universe_tickers) or ticker == "1321.T"},
                "prev20_map": {ticker: float(close_shift_20[i, idx]) for idx, ticker in enumerate(all_tickers) if ticker in set(universe_tickers) or ticker == "1321.T"},
                "prev60_map": {ticker: float(close_shift_60[i, idx]) for idx, ticker in enumerate(all_tickers) if ticker in set(universe_tickers) or ticker == "1321.T"},
                "prior_breadth": prior_breadth,
            }
            all_candidates, _, _ = select_monthly_rotation_candidates_from_snapshot(
                snapshot=snapshot,
                held_codes={all_tickers[s_idx].replace(".T", "") for s_idx in positions},
                config=MonthlyRotationStrategyConfig(**{**strategy_config.__dict__, "max_pos": effective_max_pos}),
                limit=max(len(univ_indices), effective_max_pos),
            )
            selected = all_candidates[:effective_max_pos]

        ticker_to_idx = {ticker: idx for idx, ticker in enumerate(all_tickers)}
        target_codes = {str(item["code"]) for item in selected}
        if hold_rank_tolerance > 0 and regime_is_bull and i < T - 1 and all_candidates:
            threshold_idx = min(len(all_candidates), effective_max_pos) - 1
            selected_threshold = all_candidates[threshold_idx]["score"]
            tolerance_floor = selected_threshold - hold_rank_tolerance
            for item in all_candidates:
                if item["score"] < tolerance_floor:
                    break
                ticker = f'{item["code"]}.T'
                s_idx = ticker_to_idx.get(ticker)
                if s_idx in positions:
                    target_codes.add(str(item["code"]))

        # Exit holdings that lost regime support or dropped out of the selected basket.
        if positions:
            rebalance_portfolio = [
                {
                    "code": all_tickers[s_idx].replace(".T", ""),
                    "buy_price": position["buy_price"],
                    "current_price": float(close_np[i, s_idx]),
                    "shares": position["shares"],
                }
                for s_idx, position in positions.items()
            ]
            rebalance_plan = build_rotation_rebalance_plan(
                portfolio=rebalance_portfolio,
                snapshot={
                    "is_bull": regime_is_bull and i < T - 1,
                    "target_codes": target_codes,
                    "sma20_map": {all_tickers[s_idx].replace(".T", ""): float(sma_med_np[i, s_idx]) for s_idx in positions},
                },
                config=strategy_config,
            )
            keep_codes = {str(position["code"]) for position in rebalance_plan["keep_positions"]}
            for s_idx, position in list(positions.items()):
                keep_position = all_tickers[s_idx].replace(".T", "") in keep_codes
                if keep_position:
                    continue

                next_open = float(open_np[i + 1, s_idx])
                if not np.isfinite(next_open) or next_open <= 0:
                    continue
                exit_price = next_open * (1.0 - slippage)
                executable_shares = _cap_shares_by_liquidity(
                    desired_shares=position["shares"],
                    execution_price=exit_price,
                    turnover_value=turnover_np[i + 1, s_idx] if (i + 1) < T else np.nan,
                    liquidity_limit=liquidity_limit,
                )
                if executable_shares < 100:
                    continue
                gross_pnl = (exit_price - position["buy_price"]) * executable_shares
                net_pnl, tax = _apply_profit_tax(gross_pnl, tax_rate=tax_rate)
                cash += (exit_price * executable_shares) - tax
                trade_results.append(net_pnl)
                trade_count += 1
                remaining_shares = position["shares"] - executable_shares
                if remaining_shares >= 100:
                    positions[s_idx]["shares"] = remaining_shares
                    financing_per_share = float(position.get("financing_notional", position["buy_price"] * position["shares"])) / float(position["shares"])
                    positions[s_idx]["financing_notional"] = financing_per_share * remaining_shares
                else:
                    del positions[s_idx]

        if selected:
            portfolio_records = [
                {
                    "code": all_tickers[s_idx].replace(".T", ""),
                    "buy_price": position["buy_price"],
                    "current_price": float(close_np[i, s_idx]),
                    "shares": position["shares"],
                }
                for s_idx, position in positions.items()
            ]
            entry_plan = build_rotation_entry_plan(
                candidates=selected,
                portfolio=portfolio_records,
                account_cash=cash,
                dynamic_leverage=leverage_rate,
                config=MonthlyRotationStrategyConfig(**{**strategy_config.__dict__, "max_pos": effective_max_pos}),
            )
            for item in entry_plan["planned_entries"]:
                ticker = f'{item["code"]}.T'
                s_idx = ticker_to_idx.get(ticker)
                if s_idx is None:
                    continue
                next_open = float(open_np[i + 1, s_idx])
                if not np.isfinite(next_open) or next_open <= 0:
                    continue
                buy_price = next_open * (1.0 + slippage)
                shares = compute_rotation_order_size(
                    target_allocation=entry_plan["target_allocations"].get(str(item["code"]), 0.0),
                    buy_price=buy_price,
                    account_cash=cash,
                )
                shares = _cap_shares_by_liquidity(
                    desired_shares=shares,
                    execution_price=buy_price,
                    turnover_value=turnover_np[i + 1, s_idx] if (i + 1) < T else np.nan,
                    liquidity_limit=liquidity_limit,
                )
                if shares < 100:
                    continue
                trade_notional = buy_price * shares
                if trade_notional > cash:
                    continue
                cash -= trade_notional
                positions[s_idx] = {
                    "buy_price": buy_price,
                    "shares": shares,
                    "financing_notional": trade_notional,
                }

    if positions:
        for s_idx, position in list(positions.items()):
            exit_price = float(close_np[-1, s_idx]) * (1.0 - slippage)
            executable_shares = _cap_shares_by_liquidity(
                desired_shares=position["shares"],
                execution_price=exit_price,
                turnover_value=turnover_np[-1, s_idx],
                liquidity_limit=liquidity_limit,
            )
            if executable_shares < 100:
                continue
            gross_pnl = (exit_price - position["buy_price"]) * executable_shares
            net_pnl, tax = _apply_profit_tax(gross_pnl, tax_rate=tax_rate)
            cash += (exit_price * executable_shares) - tax
            trade_results.append(net_pnl)
            trade_count += 1
            del positions[s_idx]

    final = cash
    return float(final), trade_count, monthly_assets, trade_results

def run_backtest_v16_production(univ_indices, bundle_np, timeline, breadth_ratio,
                               initial_cash=1000000, max_pos=MAX_POSITIONS,
                               sl_mult=STOP_LOSS_ATR, tp_mult=TAKE_PROFIT_ATR,
                               leverage_rate=LEVERAGE_RATE, breadth_threshold=BREADTH_THRESHOLD,
                               slippage=SLIPPAGE, use_sma_exit=True,
                               exit_buffer=0.975, max_hold_days=1,
                               liquidity_limit=0.025, bull_gap_limit=DAYTRADE_MAX_GAP,
                                bear_gap_limit=BEAR_GAP_LIMIT,
                                atr_trail_mult=3.0, rsi_threshold=DAYTRADE_MAX_RSI2,
                                entry_slippage=None, exit_slippage=None,
                                explicit_trade_cost=0.0, profit_tax_rate=0.0,
                                return_daily_stats=False,
                                verbose=False):
    """
    Day-trade production backtest:
    - Signal is evaluated from prior-day weakness and today's gap-up rebound.
    - Entry and exit execution slippage are modeled separately from explicit fees.
    - Explicit fees default to zero so general day-trade margin assumptions can
      match brokers that waive same-day financing / borrow costs.
    - No overnight positions are carried.
    """
    T = len(timeline)
    cash = float(initial_cash)
    trade_count = 0
    monthly_assets = {}
    trade_results = []
    daily_stats = {}
    
    close_np = bundle_np['Close']
    open_np = bundle_np['Open']
    high_np = bundle_np['High']
    low_np = bundle_np['Low']
    rsi2_np = bundle_np['RSI2']
    atr_np = bundle_np['ATR']
    rs_alpha_np = bundle_np.get('RS_Alpha', np.zeros_like(close_np))
    sma_med_np = bundle_np.get(f'SMA{SMA_MEDIUM_PERIOD}', np.zeros_like(close_np))
    turnover_np = bundle_np.get('Turnover', np.ones_like(close_np) * 1e12)
    sma_trend_np = bundle_np.get(f'SMA{SMA_TREND_PERIOD}', np.zeros_like(close_np))
    buy_slippage = _resolve_execution_slippage(slippage, entry_slippage)
    sell_slippage = _resolve_execution_slippage(slippage, exit_slippage)
    market_idx = -1
    for idx_t, ticker in enumerate(bundle_np.get("tickers", [])):
        if ticker == "1321.T":
            market_idx = idx_t
            break
    
    current_month = ""
    month_start_equity = initial_cash
    month_done = False
    current_week = ""
    week_start_equity = initial_cash

    for i in range(2, T):
        curr_time = timeline[i]
        
        if curr_time.strftime('%Y-%m') != current_month:
            current_month = curr_time.strftime('%Y-%m')
            month_start_equity = cash
            month_done = False 

        week_key = get_daytrade_week_key(curr_time)
        if week_key != current_week:
            current_week = week_key
            week_start_equity = float(cash)

        day_key = curr_time.strftime('%Y-%m-%d')
        day_start_equity = float(cash)
        day_trade_count = 0

        total_equity = cash
        if is_daytrade_monthly_risk_blocked(month_start_equity, total_equity):
            month_done = True

        if i + 1 >= T or month_done:
            daily_stats[day_key] = {
                "equity": float(cash),
                "day_pnl": 0.0,
                "trade_count": 0,
            }
            monthly_assets[current_month] = float(cash)
            continue

        market_open = open_np[i, market_idx] if market_idx >= 0 else np.nan
        prev_market_close = close_np[i - 1, market_idx] if market_idx >= 0 else np.nan
        prev_market_sma_trend = sma_trend_np[i - 1, market_idx] if market_idx >= 0 else np.nan
        primary_market_allowed = is_daytrade_market_allowed(
            breadth_ratio[i],
            market_open=market_open,
            prev_market_sma_trend=prev_market_sma_trend,
        )
        fallback_market_allowed = is_daytrade_fallback_market_allowed(
            breadth_ratio[i],
            market_open=market_open,
            prev_market_sma_trend=prev_market_sma_trend,
        )
        strong_oversold_market_allowed = is_daytrade_strong_oversold_market_allowed(
            breadth_ratio[i],
            market_open=market_open,
            prev_market_sma_trend=prev_market_sma_trend,
        )
        catchup_market_allowed = is_daytrade_catchup_market_allowed(
            breadth_ratio[i],
            market_open=market_open,
            prev_market_sma_trend=prev_market_sma_trend,
        )
        inverse_market_allowed = is_daytrade_inverse_market_allowed(
            breadth_ratio[i],
            market_open=market_open,
            prev_market_sma_trend=prev_market_sma_trend,
            prev_market_close=prev_market_close,
        )
        inverse_pullback_market_allowed = is_daytrade_inverse_pullback_market_allowed(
            breadth_ratio[i],
            market_open=market_open,
            prev_market_sma_trend=prev_market_sma_trend,
            prev_market_close=prev_market_close,
        )
        if not (
            primary_market_allowed
            or strong_oversold_market_allowed
            or fallback_market_allowed
            or catchup_market_allowed
            or inverse_market_allowed
            or inverse_pullback_market_allowed
        ):
            daily_stats[day_key] = {
                "equity": float(cash),
                "day_pnl": 0.0,
                "trade_count": 0,
            }
            monthly_assets[current_month] = float(cash)
            continue

        dynamic_lev = calculate_dynamic_leverage(breadth_ratio[i], config_leverage=leverage_rate)
        dynamic_lev = resolve_daytrade_weekly_leverage(
            base_leverage=dynamic_lev,
            week_start_equity=week_start_equity,
            current_equity=cash,
            current_time=curr_time,
        )
        dynamic_lev *= resolve_daytrade_breadth_exposure_scale(breadth_ratio[i])
        if is_daytrade_weekly_profit_guard_active(
            week_start_equity=week_start_equity,
            current_equity=cash,
            current_time=curr_time,
        ):
            daily_stats[day_key] = {
                "equity": float(cash),
                "day_pnl": 0.0,
                "trade_count": 0,
            }
            monthly_assets[current_month] = float(cash)
            continue

        candidates = []
        strong_oversold_candidates = []
        fallback_candidates = []
        catchup_candidates = []
        inverse_candidates = []
        inverse_code_set = {ticker if str(ticker).endswith(".T") else f"{ticker}.T" for ticker in DAYTRADE_INVERSE_CODES}
        for s_idx in univ_indices:
            ticker = bundle_np["tickers"][s_idx]
            t_close = close_np[i, s_idx]
            t_open = open_np[i, s_idx]
            t_sma_med = sma_med_np[i - 1, s_idx]
            prev_close = close_np[i - 1, s_idx]
            prev_prev_close = close_np[i - 2, s_idx]
            prev_open = open_np[i - 1, s_idx]
            prev_low = low_np[i - 1, s_idx]
            prev_atr = atr_np[i - 1, s_idx]
            t_turnover = turnover_np[i - 1, s_idx]
            prev_rsi2 = rsi2_np[i - 1, s_idx]
            t_rs = rs_alpha_np[i - 1, s_idx]
            prev_sma_trend = sma_trend_np[i - 1, s_idx]

            raw_values = [
                t_close, t_open, prev_close, prev_prev_close, prev_open,
                prev_low, prev_atr, t_turnover, t_sma_med, prev_rsi2,
                prev_sma_trend
            ]
            if np.any(np.isnan(raw_values)):
                continue
            if prev_atr <= 0 or t_open <= 0 or t_close <= 0 or prev_close <= 0:
                continue
            if t_open < MIN_PRICE or t_open > MAX_PRICE:
                continue
            if t_turnover <= 0:
                continue
            if t_turnover < min(DAYTRADE_MIN_TURNOVER, DAYTRADE_CATCHUP_MIN_TURNOVER):
                continue
            if liquidity_limit > 0 and (t_open * 100.0) > (t_turnover * liquidity_limit):
                continue
            prev_day_return = (prev_close / prev_prev_close) - 1.0
            primary_trend_allowed = is_daytrade_trend_allowed(prev_close, prev_sma_trend)
            fallback_trend_allowed = is_daytrade_trend_allowed(
                prev_close,
                prev_sma_trend,
                trend_buffer=DAYTRADE_FALLBACK_TREND_BUFFER,
            )

            if primary_market_allowed and primary_trend_allowed and t_turnover >= DAYTRADE_MIN_TURNOVER:
                if (
                    prev_day_return >= DAYTRADE_MIN_PREV_DAY_RETURN_PCT
                    and prev_day_return <= DAYTRADE_MAX_PREV_DAY_RETURN_PCT
                ):
                    metrics = evaluate_daytrade_open_setup(
                        t_open, prev_close, t_sma_med, breadth_ratio[i],
                        prev_open=prev_open, prev_atr=prev_atr, prev_low=prev_low,
                        prev_rsi2=prev_rsi2, rs_alpha=t_rs, prev_prev_close=prev_prev_close,
                        trade_weekday=curr_time.weekday(),
                    )
                    if metrics is not None and prev_rsi2 <= rsi_threshold and metrics["gap_pct"] <= bull_gap_limit:
                        score = score_daytrade_open_setup(
                            metrics,
                            rs_alpha=t_rs,
                            prev_close=prev_close,
                            prev_prev_close=prev_prev_close,
                            prev_atr=prev_atr,
                            prev_rsi2=prev_rsi2
                        )
                        if np.isfinite(score) and score >= MIN_SETUP_SCORE:
                            candidates.append({
                                "code": ticker,
                                "s_idx": s_idx,
                                "score": score,
                                "open": t_open,
                                "close": t_close,
                                "high": high_np[i, s_idx],
                                "low": low_np[i, s_idx],
                                "atr": prev_atr,
                                "turnover": t_turnover,
                                "setup_type": "primary",
                                "notional_pct": DAYTRADE_MAX_NOTIONAL_PCT,
                                "equity_notional_pct": DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
                            })
                            continue

            if strong_oversold_market_allowed and t_turnover >= DAYTRADE_MIN_TURNOVER:
                strong_oversold_metrics = evaluate_daytrade_strong_oversold_open_setup(
                    t_open,
                    prev_close,
                    breadth_ratio[i],
                    prev_atr=prev_atr,
                    prev_rsi2=prev_rsi2,
                    rs_alpha=t_rs,
                    prev_prev_close=prev_prev_close,
                    prev_sma_trend=prev_sma_trend,
                )
                if strong_oversold_metrics is not None:
                    score = score_daytrade_strong_oversold_open_setup(
                        strong_oversold_metrics,
                        rs_alpha=t_rs,
                    )
                    if np.isfinite(score) and score >= DAYTRADE_STRONG_OVERSOLD_MIN_SETUP_SCORE:
                        strong_oversold_candidates.append({
                            "code": ticker,
                            "s_idx": s_idx,
                            "score": score,
                            "open": t_open,
                            "close": t_close,
                            "high": high_np[i, s_idx],
                            "low": low_np[i, s_idx],
                            "atr": prev_atr,
                            "turnover": t_turnover,
                            "setup_type": "strong_oversold",
                            "notional_pct": DAYTRADE_STRONG_OVERSOLD_NOTIONAL_PCT,
                            "equity_notional_pct": DAYTRADE_STRONG_OVERSOLD_EQUITY_NOTIONAL_PCT,
                            "stop_mult": DAYTRADE_STRONG_OVERSOLD_STOP_MULT,
                            "target_mult": DAYTRADE_STRONG_OVERSOLD_TARGET_MULT,
                        })

            if fallback_market_allowed and fallback_trend_allowed and t_turnover >= DAYTRADE_MIN_TURNOVER:
                fallback_metrics = evaluate_daytrade_fallback_open_setup(
                    t_open, prev_close, t_sma_med, breadth_ratio[i],
                    prev_atr=prev_atr, prev_low=prev_low,
                    prev_rsi2=prev_rsi2, rs_alpha=t_rs,
                    prev_prev_close=prev_prev_close
                )
                if fallback_metrics is not None:
                    score = score_daytrade_fallback_open_setup(
                        fallback_metrics,
                        rs_alpha=t_rs,
                        prev_close=prev_close,
                        prev_prev_close=prev_prev_close,
                        prev_atr=prev_atr,
                        prev_rsi2=prev_rsi2
                    )
                    if np.isfinite(score) and score >= DAYTRADE_FALLBACK_MIN_SETUP_SCORE:
                        fallback_candidates.append({
                            "code": ticker,
                            "s_idx": s_idx,
                            "score": score,
                            "open": t_open,
                            "close": t_close,
                            "high": high_np[i, s_idx],
                            "low": low_np[i, s_idx],
                            "atr": prev_atr,
                            "turnover": t_turnover,
                            "setup_type": "fallback",
                            "notional_pct": DAYTRADE_FALLBACK_MAX_NOTIONAL_PCT,
                            "stop_mult": DAYTRADE_FALLBACK_INTRADAY_STOP_MULT,
                            "target_mult": DAYTRADE_FALLBACK_INTRADAY_TARGET_MULT,
                        })

            if catchup_market_allowed and t_turnover >= DAYTRADE_CATCHUP_MIN_TURNOVER:
                catchup_metrics_list = evaluate_daytrade_catchup_open_setups(
                    t_open, prev_close, t_sma_med, breadth_ratio[i],
                    prev_atr=prev_atr, prev_low=prev_low,
                    prev_rsi2=prev_rsi2, rs_alpha=t_rs,
                    prev_prev_close=prev_prev_close,
                    prev_sma_trend=prev_sma_trend,
                )
                for catchup_metrics in catchup_metrics_list:
                    score = score_daytrade_catchup_open_setup(catchup_metrics)
                    if not np.isfinite(score) or score < DAYTRADE_CATCHUP_MIN_SETUP_SCORE:
                        continue
                    if catchup_metrics["setup_type"] == "catchup_gapdown":
                        stop_mult = DAYTRADE_CATCHUP_GAPDOWN_STOP_MULT
                        target_mult = DAYTRADE_CATCHUP_GAPDOWN_TARGET_MULT
                        notional_pct = DAYTRADE_CATCHUP_GAPDOWN_NOTIONAL_PCT
                        equity_notional_pct = DAYTRADE_CATCHUP_GAPDOWN_EQUITY_NOTIONAL_PCT
                    else:
                        stop_mult = DAYTRADE_CATCHUP_RS_STOP_MULT
                        target_mult = DAYTRADE_CATCHUP_RS_TARGET_MULT
                        notional_pct = DAYTRADE_CATCHUP_RS_NOTIONAL_PCT
                        equity_notional_pct = DAYTRADE_CATCHUP_RS_EQUITY_NOTIONAL_PCT
                    catchup_candidates.append({
                        "code": ticker,
                        "s_idx": s_idx,
                        "score": score,
                        "open": t_open,
                        "close": t_close,
                        "high": high_np[i, s_idx],
                        "low": low_np[i, s_idx],
                        "atr": prev_atr,
                        "turnover": t_turnover,
                        "setup_type": catchup_metrics["setup_type"],
                        "notional_pct": notional_pct,
                        "equity_notional_pct": equity_notional_pct,
                        "stop_mult": stop_mult,
                        "target_mult": target_mult,
                    })

            if (
                (inverse_market_allowed or inverse_pullback_market_allowed)
                and ticker in inverse_code_set
                and t_turnover >= DAYTRADE_INVERSE_MIN_TURNOVER
            ):
                inverse_metrics = evaluate_daytrade_inverse_open_setup(
                    t_open,
                    prev_close,
                    breadth_ratio[i],
                    prev_atr=prev_atr,
                    prev_prev_close=prev_prev_close,
                    market_open=market_open,
                    prev_market_close=prev_market_close,
                    prev_market_sma_trend=prev_market_sma_trend,
                )
                if inverse_metrics is not None:
                    score = score_daytrade_inverse_open_setup(
                        inverse_metrics,
                        rs_alpha=t_rs,
                    )
                    if np.isfinite(score) and score >= DAYTRADE_INVERSE_MIN_SETUP_SCORE:
                        setup_type = inverse_metrics.get("setup_type", "inverse")
                        if setup_type == "inverse_pullback":
                            stop_mult = DAYTRADE_INVERSE_PULLBACK_STOP_MULT
                            target_mult = DAYTRADE_INVERSE_PULLBACK_TARGET_MULT
                        else:
                            stop_mult = DAYTRADE_INVERSE_STOP_MULT
                            target_mult = DAYTRADE_INVERSE_TARGET_MULT
                        inverse_candidates.append({
                            "code": ticker,
                            "s_idx": s_idx,
                            "score": score,
                            "open": t_open,
                            "close": t_close,
                            "high": high_np[i, s_idx],
                            "low": low_np[i, s_idx],
                            "atr": prev_atr,
                            "turnover": t_turnover,
                            "setup_type": setup_type,
                            "notional_pct": DAYTRADE_INVERSE_NOTIONAL_PCT,
                            "equity_notional_pct": DAYTRADE_INVERSE_EQUITY_NOTIONAL_PCT,
                            "stop_mult": stop_mult,
                            "target_mult": target_mult,
                        })

        if candidates or strong_oversold_candidates or fallback_candidates or catchup_candidates or inverse_candidates:
            selected = select_daytrade_candidates(
                candidates,
                strong_oversold_candidates,
                fallback_candidates,
                catchup_candidates,
                inverse_candidates,
                breadth_val=breadth_ratio[i],
                trade_weekday=curr_time.weekday(),
            )
            inverse_only = bool(selected) and all(
                is_daytrade_inverse_setup_type(item.get("setup_type")) for item in selected
            )
            if dynamic_lev <= 0 and not inverse_only:
                daily_stats[day_key] = {
                    "equity": float(cash),
                    "day_pnl": 0.0,
                    "trade_count": 0,
                }
                monthly_assets[current_month] = float(cash)
                continue
            day_buying_power = resolve_daytrade_buying_power(
                current_equity=day_start_equity,
                account_cash=cash,
                dynamic_leverage=dynamic_lev,
            )
            inverse_buying_power = 0.0
            if inverse_only:
                inverse_buying_power = resolve_daytrade_inverse_buying_power(
                    current_equity=day_start_equity,
                    account_cash=cash,
                )
            committed_capital = 0.0
            day_pnl = 0.0
            day_loss_limit = day_start_equity * MAX_DAILY_LOSS_PCT
            for candidate in selected:
                if day_trade_count >= max_pos:
                    break
                if -day_pnl >= day_loss_limit:
                    break

                real_buy = candidate["open"] * (1.0 + buy_slippage)
                candidate_buying_power = day_buying_power
                candidate_dynamic_lev = dynamic_lev
                if is_daytrade_inverse_setup_type(candidate.get("setup_type")):
                    candidate_buying_power = inverse_buying_power
                    candidate_dynamic_lev = DAYTRADE_INVERSE_BUYING_POWER_LEVERAGE
                remaining_buying_power = max(0.0, candidate_buying_power - committed_capital)
                if remaining_buying_power <= 0:
                    break

                effective_sl_mult = candidate.get("stop_mult")
                if effective_sl_mult is None:
                    effective_sl_mult = resolve_daytrade_intraday_stop_mult(sl_mult)
                effective_tp_mult = candidate.get("target_mult")
                if effective_tp_mult is None:
                    effective_tp_mult = resolve_daytrade_intraday_target_mult(tp_mult)
                stop_price = max(0.01, real_buy - (candidate["atr"] * effective_sl_mult))
                target_price = real_buy + (candidate["atr"] * effective_tp_mult)

                shares = calculate_lot_size(
                    current_equity=day_start_equity,
                    atr=candidate["atr"],
                    sl_mult=sl_mult,
                    price=real_buy,
                    dynamic_leverage=candidate_dynamic_lev,
                    max_positions=max_pos,
                    buying_power=remaining_buying_power,
                    turnover=candidate["turnover"]
                )
                if shares < 100:
                    continue

                shares = cap_daytrade_position_size(
                    raw_shares=shares,
                    current_equity=day_start_equity,
                    buying_power=remaining_buying_power,
                    entry_price=real_buy,
                    stop_price=stop_price,
                    notional_pct=candidate.get("notional_pct"),
                    equity_notional_pct=candidate.get("equity_notional_pct"),
                )
                if shares < 100:
                    continue

                trade_notional = real_buy * shares
                if trade_notional > remaining_buying_power:
                    continue

                raw_exit, _exit_reason = _resolve_intraday_exit(
                    entry_price=real_buy,
                    open_price=candidate["open"],
                    high_price=candidate["high"],
                    low_price=candidate["low"],
                    close_price=candidate["close"],
                    stop_price=stop_price,
                    target_price=target_price,
                )
                real_sell = raw_exit * (1.0 - sell_slippage)
                gross_pnl = (real_sell - real_buy) * shares
                explicit_cost = float(explicit_trade_cost)
                net_pnl, tax = _apply_profit_tax(
                    gross_pnl - explicit_cost,
                    tax_rate=profit_tax_rate,
                )
                committed_capital += trade_notional
                day_pnl += net_pnl
                trade_results.append(net_pnl)
                trade_count += 1
                day_trade_count += 1

            cash += day_pnl

        daily_stats[day_key] = {
            "equity": float(cash),
            "day_pnl": float(cash - day_start_equity),
            "trade_count": int(day_trade_count),
        }

        monthly_assets[current_month] = float(cash)

    final = float(cash)
    if return_daily_stats:
        return final, trade_count, monthly_assets, trade_results, daily_stats
    return final, trade_count, monthly_assets, trade_results
