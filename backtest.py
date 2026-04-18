import pandas as pd
import numpy as np
from core.logic import (
    calculate_dynamic_leverage, check_entry_signal,
    calculate_position_stops, calculate_lot_size, detect_market_regime
)
from core.config import (
    SMA_SHORT_PERIOD, SMA_MEDIUM_PERIOD, SMA_TREND_PERIOD,
    MIN_ALLOCATION_AMOUNT, MAX_ALLOCATION_AMOUNT,
    SLIPPAGE, MAX_HOLD_DAYS, COOLING_DAYS, EXIT_ON_SMA20_BREACH, SMA20_EXIT_BUFFER,
    RS_THRESHOLD
)

def run_backtest_v16_production(univ_indices, bundle_np, timeline, breadth_ratio,
                               initial_cash=1000000, max_pos=3,
                               sl_mult=3.0, tp_mult=20.0, leverage_rate=2.0, breadth_threshold=0.50,
                               slippage=SLIPPAGE, use_sma_exit=EXIT_ON_SMA20_BREACH,
                               exit_buffer=SMA20_EXIT_BUFFER, max_hold_days=MAX_HOLD_DAYS,
                               liquidity_limit=0.025, bull_gap_limit=0.13, bear_gap_limit=0.02,
                                atr_trail_mult=3.0, rsi_threshold=30.0,
                                verbose=False):
    """
    V17.0 Imperial Apex (Golden Logic Sync)
    - Replicates live logic: Pure Trend Following
    - Fixed ATR TP/SL & SMA20 Exit
    - Gap Filter: Synced with BULL_GAP_LIMIT
    - Liquidity Filter: Synced with LIQUIDITY_LIMIT_RATE
    """
    T = len(timeline)
    cash = float(initial_cash)
    portfolio = []
    trade_count = 0
    monthly_assets = {}
    trade_results = []
    
    close_np = bundle_np['Close']
    open_np = bundle_np['Open']
    high_np = bundle_np['High']
    low_np = bundle_np['Low']
    rsi2_np = bundle_np['RSI2']
    atr_np = bundle_np['ATR']
    rs_alpha_np = bundle_np.get('RS_Alpha', np.zeros_like(close_np))
    sma_med_np = bundle_np.get(f'SMA{SMA_MEDIUM_PERIOD}', np.zeros_like(close_np))
    high20_np = bundle_np.get('High20', np.zeros_like(close_np))
    
    cooling_days = 0
    current_month = ""
    month_start_equity = initial_cash
    month_done = False
    
    # Identify 1321.T for regime detection
    idx_1321 = -1
    for idx_t, t_ticker in enumerate(bundle_np['tickers']):
        if t_ticker == '1321.T': 
            idx_1321 = idx_t
            break

    for i in range(1, T):
        curr_time = timeline[i]
        
        # 0. Monthly Tracking
        if cooling_days > 0: cooling_days -= 1
        
        if curr_time.strftime('%Y-%m') != current_month:
            current_month = curr_time.strftime('%Y-%m')
            # Calculate equity at start of month
            month_start_equity = cash + sum(np.nan_to_num(close_np[i, p['s_idx']]) * p['shares'] for p in portfolio)
            month_done = False 

        total_equity = cash + sum(np.nan_to_num(close_np[i, p['s_idx']]) * p['shares'] for p in portfolio)
        month_drawdown = (total_equity / month_start_equity) - 1.0 if month_start_equity > 0 else 0
        
        # --- Shared Regime Parity ---
        p_1321 = close_np[i, idx_1321] if idx_1321 != -1 else 0
        s_trend_1321 = bundle_np[f'SMA{SMA_TREND_PERIOD}'][i, idx_1321] if idx_1321 != -1 else 0
        s_trend_prev = bundle_np[f'SMA{SMA_TREND_PERIOD}'][i-10, idx_1321] if i > 10 and idx_1321 != -1 else s_trend_1321
        slope = (s_trend_1321 / s_trend_prev - 1.0) * 100 if s_trend_prev != 0 else 0
        
        regime = "NEUTRAL"
        if p_1321 < s_trend_1321:
            regime = "BEAR"
        elif slope > 0.01:
            regime = "BULL"
            
        s_short_1321 = bundle_np[f'SMA{SMA_SHORT_PERIOD}'][i, idx_1321] if idx_1321 != -1 else 0
        is_trend_snapped = p_1321 < s_short_1321 if idx_1321 != -1 else False

        # --- Imperial Sovereign Protocol (V17.0 Golden) ---
        if month_drawdown <= -0.15: month_done = True 

        # 1. Management
        new_portfolio = []
        for p in portfolio:
            tidx = p['s_idx']
            t_open = open_np[i, tidx]
            t_high = high_np[i, tidx]
            t_low = low_np[i, tidx]
            t_close = close_np[i, tidx]
            t_atr = atr_np[i, tidx]
            
            if np.isnan(t_close):
                new_portfolio.append(p)
                continue
            
            # 最高値の更新
            p['max_price'] = max(p.get('max_price', t_high), t_high)
            exit_p = None
            
            # --- Exit Conditions (V17.0 Golden) ---
            tsl_price, target_price = calculate_position_stops(
                p['buy_price'], p['buy_atr'], p['max_price'], t_close,
                sl_mult, tp_mult
            )

            # Trend Breach (Synced buffer)
            is_trend_broken = t_close < sma_med_np[i, tidx] * exit_buffer

            if is_trend_broken:
                exit_p = t_close
            from core.config import SLIPPAGE_RATE
            
            if t_open <= tsl_price:
                # Gap down: Exit at Open (worse price)
                exit_p = t_open
            elif t_low <= tsl_price:
                # Intraday hit: Exit at Stop price
                exit_p = tsl_price
            elif t_open >= target_price:
                # Gap up: Exit at Open (better price)
                exit_p = t_open
            elif t_high >= target_price:
                # Intraday hit: Exit at Target price
                exit_p = target_price
            elif p.get('held_days', 0) >= max_hold_days:
                exit_p = t_close
            elif month_done:
                exit_p = t_close
            
            if exit_p is not None:
                final_exit = exit_p * (1.0 - SLIPPAGE_RATE)
                trade_results.append((final_exit - p['buy_price']) * p['shares'])
                cash += final_exit * p['shares']
                cooling_days = COOLING_DAYS
            else:
                p['held_days'] = p.get('held_days', 0) + 1
                new_portfolio.append(p)
        portfolio = new_portfolio
        
        # Stats Update
        total_equity = cash + sum(np.nan_to_num(close_np[i, pos['s_idx']]) * pos['shares'] for pos in portfolio)
        monthly_assets[current_month] = float(total_equity)

        # 2. Entry (V17.0 Golden)
        if i + 1 >= T or month_done or cooling_days > 0 or regime != "BULL": continue 
        
        dynamic_lev = calculate_dynamic_leverage(breadth_ratio[i], config_leverage=leverage_rate)
        if dynamic_lev <= 0: continue
        
        # Selection: Pure RS_Alpha Top Leaders
        rs_alphas = rs_alpha_np[i, :]
        rsis = rsi2_np[i, :]
        sma_trends = bundle_np[f'SMA{SMA_TREND_PERIOD}'][i, :]
        turnover_vals = bundle_np.get('Turnover', np.ones_like(close_np) * 1e12) 

        valid_indices = [idx for idx in univ_indices if not np.isnan(rs_alphas[idx])]
        # Scoring: Top RS leaders
        sorted_candidates = sorted(valid_indices, key=lambda x: rs_alphas[x], reverse=True)
        
        for s_idx in sorted_candidates:
            if len(portfolio) >= max_pos: break 
            if any(p['s_idx'] == s_idx for p in portfolio): continue
            
            rs = rs_alphas[s_idx]
            r2 = rsis[s_idx]
            t_close = close_np[i, s_idx]
            t_open = open_np[i, s_idx]
            t_sma_med = sma_med_np[i, s_idx]
            t_sma_trend = sma_trends[s_idx]
            t_turnover = turnover_vals[i, s_idx]
            
            # [V150.2 Reality Sync] Gap Filter Parity
            prev_close = close_np[i-1, s_idx]
            gap_pct = (t_open / prev_close - 1.0) if prev_close > 0 else 0
            if (regime == "BULL" and gap_pct < -0.02) or (abs(gap_pct) > bull_gap_limit):
                continue

            if rs < RS_THRESHOLD: continue

            # Entry Signal (V17.0 Reversion Sync)
            entry_signal = check_entry_signal(regime, r2, t_close, t_open, t_sma_med)
                    
            if entry_signal:
                from core.config import SLIPPAGE_RATE
                real_buy = t_close * (1.0 + SLIPPAGE_RATE)
                
                # --- V155 Reality Sync: Sizing & Capital Control ---
                current_exposure = total_equity - cash
                buying_power = (total_equity * dynamic_lev) - current_exposure
                
                shares = calculate_lot_size(
                    current_equity=total_equity,
                    atr=atr_np[i, s_idx],
                    sl_mult=sl_mult,
                    price=real_buy,
                    dynamic_leverage=dynamic_lev,
                    max_positions=max_pos,
                    buying_power=buying_power,
                    turnover=t_turnover
                )
                
                if shares >= 100:
                    portfolio.append({
                        's_idx': s_idx, 'buy_price': real_buy,
                        'shares': shares, 'held_days': 0, 'max_price': real_buy,
                        'buy_atr': atr_np[i, s_idx]
                    })
                    cash -= real_buy * shares
                    trade_count += 1

    final = cash + sum(np.nan_to_num(close_np[-1, p['s_idx']]) * p['shares'] for p in portfolio)
    return float(final), trade_count, monthly_assets, trade_results
