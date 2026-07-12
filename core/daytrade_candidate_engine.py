from dataclasses import dataclass
from typing import NotRequired, Sequence, TypedDict

import numpy as np

from core.config import MIN_PRICE
from core.logic import (
    DaytradeOpenMarketContext,
    DAYTRADE_BULL_ETF_CODES,
    DAYTRADE_BULL_ETF_LOW_BREADTH_REBOUND_EQUITY_NOTIONAL_PCT,
    DAYTRADE_BULL_ETF_LOW_BREADTH_REBOUND_MIN_SETUP_SCORE,
    DAYTRADE_BULL_ETF_LOW_BREADTH_REBOUND_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_GAPDOWN_EQUITY_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_GAPDOWN_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_GAPDOWN_STOP_MULT,
    DAYTRADE_CATCHUP_GAPDOWN_TARGET_MULT,
    DAYTRADE_CATCHUP_MIN_SETUP_SCORE,
    DAYTRADE_CATCHUP_MIN_TURNOVER,
    DAYTRADE_CATCHUP_RS_EQUITY_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_RS_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_RS_STOP_MULT,
    DAYTRADE_CATCHUP_RS_STRONG_CONTINUATION_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_RS_STRONG_CONTINUATION_RISK_BUDGET_PCT,
    DAYTRADE_CATCHUP_RS_TARGET_MULT,
    DAYTRADE_FALLBACK_INTRADAY_STOP_MULT,
    DAYTRADE_FALLBACK_INTRADAY_TARGET_MULT,
    DAYTRADE_FALLBACK_MAX_NOTIONAL_PCT,
    DAYTRADE_FALLBACK_MIN_SETUP_SCORE,
    DAYTRADE_FALLBACK_TREND_BUFFER,
    DAYTRADE_INVERSE_CODES,
    DAYTRADE_INVERSE_EQUITY_NOTIONAL_PCT,
    DAYTRADE_INVERSE_MIN_SETUP_SCORE,
    DAYTRADE_INVERSE_NOTIONAL_PCT,
    DAYTRADE_INVERSE_PULLBACK_STOP_MULT,
    DAYTRADE_INVERSE_PULLBACK_TARGET_MULT,
    DAYTRADE_INVERSE_REBREAK_STOP_MULT,
    DAYTRADE_INVERSE_REBREAK_TARGET_MULT,
    DAYTRADE_INVERSE_STOP_MULT,
    DAYTRADE_INVERSE_TARGET_MULT,
    DAYTRADE_MAX_PREV_DAY_RETURN_PCT,
    DAYTRADE_MIN_PREV_DAY_RETURN_PCT,
    DAYTRADE_MIN_SETUP_SCORE,
    DAYTRADE_MIN_TURNOVER,
    DAYTRADE_STRONG_OVERSOLD_MIN_SETUP_SCORE,
    DAYTRADE_STRONG_OVERSOLD_STOP_MULT,
    DAYTRADE_STRONG_OVERSOLD_TARGET_MULT,
    evaluate_daytrade_bull_etf_open_setup,
    evaluate_daytrade_catchup_open_setups,
    evaluate_daytrade_fallback_open_setup,
    evaluate_daytrade_inverse_open_setup,
    evaluate_daytrade_open_setup,
    evaluate_daytrade_strong_oversold_open_setup,
    is_daytrade_bull_etf_price_allowed,
    is_daytrade_strong_oversold_tuesday_stretched_open_filtered,
    is_daytrade_trend_allowed,
    resolve_daytrade_catchup_equity_notional_pct,
    resolve_daytrade_catchup_notional_pct,
    resolve_daytrade_catchup_size_multiplier,
    resolve_daytrade_fallback_equity_notional_pct,
    resolve_daytrade_fallback_notional_pct,
    resolve_daytrade_inverse_min_turnover,
    resolve_daytrade_primary_equity_notional_pct,
    resolve_daytrade_primary_notional_pct,
    resolve_daytrade_primary_risk_budget_pct,
    resolve_daytrade_primary_size_multiplier,
    resolve_daytrade_scan_min_turnover,
    resolve_daytrade_strong_oversold_equity_notional_pct,
    resolve_daytrade_strong_oversold_notional_pct,
    resolve_daytrade_strong_oversold_risk_budget_pct,
    resolve_daytrade_strong_oversold_size_multiplier,
    score_daytrade_bull_etf_open_setup,
    score_daytrade_catchup_open_setup,
    score_daytrade_fallback_open_setup,
    score_daytrade_inverse_open_setup,
    score_daytrade_open_setup,
    score_daytrade_strong_oversold_open_setup,
)


class DaytradeCandidate(TypedDict):
    code: str
    s_idx: int
    score: float
    open: float
    atr: float
    turnover: float
    setup_type: str
    notional_pct: float | None
    equity_notional_pct: float | None
    risk_budget_pct: NotRequired[float | None]
    size_multiplier: NotRequired[float]
    stop_mult: NotRequired[float]
    target_mult: NotRequired[float]
    gap_pct: NotRequired[float | None]
    prev_return: NotRequired[float | None]
    prev_rsi2: NotRequired[float | None]
    open_from_prev_low_atr: NotRequired[float | None]
    open_vs_sma_atr: NotRequired[float | None]
    rs_alpha: NotRequired[float | None]
    symbol_trend_ratio: NotRequired[float | None]
    market_ratio: NotRequired[float | None]


@dataclass(frozen=True, slots=True)
class DaytradeOpenArrayView:
    tickers: Sequence[str]
    universe_indices: Sequence[int]
    open_today: np.ndarray
    close_prev: np.ndarray
    close_prev2: np.ndarray
    open_prev: np.ndarray
    low_prev: np.ndarray
    atr_prev: np.ndarray
    turnover_prev: np.ndarray
    rsi2_prev: np.ndarray
    rs_alpha_prev: np.ndarray
    sma_med_prev: np.ndarray
    sma_trend_prev: np.ndarray

    def __post_init__(self):
        ticker_count = len(self.tickers)
        arrays = (
            self.open_today,
            self.close_prev,
            self.close_prev2,
            self.open_prev,
            self.low_prev,
            self.atr_prev,
            self.turnover_prev,
            self.rsi2_prev,
            self.rs_alpha_prev,
            self.sma_med_prev,
            self.sma_trend_prev,
        )
        if any(array.ndim != 1 for array in arrays):
            raise ValueError("daytrade open array view requires one-dimensional arrays")
        if any(len(array) != ticker_count for array in arrays):
            raise ValueError("daytrade open array view arrays must align with tickers")


class DaytradeScanStats(TypedDict):
    universe: int
    raw_nan: int
    invalid_price_atr: int
    price_blocked: int
    turnover_nonpositive: int
    turnover_blocked: int
    liquidity_blocked: int
    passed_scan: int


class DaytradeSetupStats(TypedDict):
    no_setup_candidate_after_scan: int


@dataclass(slots=True)
class DaytradeCandidateGroups:
    primary: list[DaytradeCandidate]
    strong_oversold: list[DaytradeCandidate]
    fallback: list[DaytradeCandidate]
    catchup: list[DaytradeCandidate]
    inverse: list[DaytradeCandidate]
    bull_etf: list[DaytradeCandidate]
    scan_stats: DaytradeScanStats
    setup_stats: DaytradeSetupStats


def generate_daytrade_candidate_groups(
    snapshot: DaytradeOpenArrayView,
    market: DaytradeOpenMarketContext,
    *,
    liquidity_limit: float,
    bull_gap_limit: float,
    rsi_threshold: float,
) -> DaytradeCandidateGroups:
    tickers = snapshot.tickers
    univ_indices = snapshot.universe_indices
    open_today = snapshot.open_today
    close_prev = snapshot.close_prev
    close_prev2 = snapshot.close_prev2
    open_prev = snapshot.open_prev
    low_prev = snapshot.low_prev
    atr_prev = snapshot.atr_prev
    turnover_prev = snapshot.turnover_prev
    rsi2_prev = snapshot.rsi2_prev
    rs_alpha_prev = snapshot.rs_alpha_prev
    sma_med_prev = snapshot.sma_med_prev
    sma_trend_prev = snapshot.sma_trend_prev

    entry_breadth = market.breadth_val
    market_open = market.market_open
    prev_market_close = market.prev_market_close
    prev_market_sma_trend = market.prev_market_sma_trend
    market_ratio = market.market_ratio
    primary_market_allowed = market.primary_market_allowed
    fallback_market_allowed = market.fallback_market_allowed
    strong_oversold_market_allowed = market.strong_oversold_market_allowed
    catchup_market_allowed = market.catchup_market_allowed
    inverse_market_allowed = market.inverse_market_allowed
    inverse_pullback_market_allowed = market.inverse_pullback_market_allowed
    bull_etf_market_allowed = market.bull_etf_market_allowed
    trade_weekday = market.trade_weekday
    curr_time = market.trade_date



    candidates = []
    strong_oversold_candidates = []
    fallback_candidates = []
    catchup_candidates = []
    inverse_candidates = []
    bull_etf_candidates = []
    scan_stats = {
        "universe": 0,
        "raw_nan": 0,
        "invalid_price_atr": 0,
        "price_blocked": 0,
        "turnover_nonpositive": 0,
        "turnover_blocked": 0,
        "liquidity_blocked": 0,
        "passed_scan": 0,
    }
    setup_stats = {"no_setup_candidate_after_scan": 0}
    inverse_code_set = {ticker if str(ticker).endswith(".T") else f"{ticker}.T" for ticker in DAYTRADE_INVERSE_CODES}
    bull_etf_code_set = {ticker if str(ticker).endswith(".T") else f"{ticker}.T" for ticker in DAYTRADE_BULL_ETF_CODES}
    for s_idx in univ_indices:
        scan_stats["universe"] += 1
        ticker = tickers[s_idx]
        t_open = open_today[s_idx]
        t_sma_med = sma_med_prev[s_idx]
        prev_close = close_prev[s_idx]
        prev_prev_close = close_prev2[s_idx]
        prev_open = open_prev[s_idx]
        prev_low = low_prev[s_idx]
        prev_atr = atr_prev[s_idx]
        t_turnover = turnover_prev[s_idx]
        prev_rsi2 = rsi2_prev[s_idx]
        t_rs = rs_alpha_prev[s_idx]
        prev_sma_trend = sma_trend_prev[s_idx]

        raw_values = [
            t_open, prev_close, prev_prev_close, prev_open,
            prev_low, prev_atr, t_turnover, t_sma_med, prev_rsi2,
            prev_sma_trend
        ]
        if np.any(np.isnan(raw_values)):
            scan_stats["raw_nan"] += 1
            continue
        if prev_atr <= 0 or t_open <= 0 or prev_close <= 0:
            scan_stats["invalid_price_atr"] += 1
            continue
        if t_open < MIN_PRICE or not is_daytrade_bull_etf_price_allowed(t_open, ticker, entry_breadth):
            scan_stats["price_blocked"] += 1
            continue
        if t_turnover <= 0:
            scan_stats["turnover_nonpositive"] += 1
            continue
        if t_turnover < resolve_daytrade_scan_min_turnover(ticker, entry_breadth):
            scan_stats["turnover_blocked"] += 1
            continue
        if liquidity_limit > 0 and (t_open * 100.0) > (t_turnover * liquidity_limit):
            scan_stats["liquidity_blocked"] += 1
            continue
        scan_stats["passed_scan"] += 1
        setup_candidate_count_before = (
            len(candidates)
            + len(strong_oversold_candidates)
            + len(fallback_candidates)
            + len(catchup_candidates)
            + len(inverse_candidates)
            + len(bull_etf_candidates)
        )
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
                    t_open, prev_close, t_sma_med, entry_breadth,
                    prev_open=prev_open, prev_atr=prev_atr, prev_low=prev_low,
                    prev_rsi2=prev_rsi2, rs_alpha=t_rs, prev_prev_close=prev_prev_close,
                    trade_weekday=trade_weekday,
                    market_open=market_open, prev_market_close=prev_market_close,
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
                    if np.isfinite(score) and score >= DAYTRADE_MIN_SETUP_SCORE:
                        primary_equity_notional_pct = resolve_daytrade_primary_equity_notional_pct(
                            breadth_val=entry_breadth,
                            gap_pct=metrics.get("gap_pct"),
                            open_vs_sma_atr=metrics.get("open_vs_sma_atr"),
                            open_from_prev_low_atr=metrics.get("open_from_prev_low_atr"),
                            market_ratio=market_ratio,
                            primary_score=score,
                            rs_alpha=t_rs,
                            trade_weekday=trade_weekday,
                            prev_return=metrics.get("prev_return"),
                            prev_rsi2=prev_rsi2,
                        )
                        primary_notional_pct = resolve_daytrade_primary_notional_pct(
                            breadth_val=entry_breadth,
                            gap_pct=metrics.get("gap_pct"),
                            open_vs_sma_atr=metrics.get("open_vs_sma_atr"),
                            open_from_prev_low_atr=metrics.get("open_from_prev_low_atr"),
                            market_ratio=market_ratio,
                            primary_score=score,
                            rs_alpha=t_rs,
                            trade_weekday=trade_weekday,
                            prev_return=metrics.get("prev_return"),
                            prev_rsi2=prev_rsi2,
                        )
                        primary_risk_budget_pct = resolve_daytrade_primary_risk_budget_pct(
                            breadth_val=entry_breadth,
                            gap_pct=metrics.get("gap_pct"),
                            open_vs_sma_atr=metrics.get("open_vs_sma_atr"),
                            open_from_prev_low_atr=metrics.get("open_from_prev_low_atr"),
                            market_ratio=market_ratio,
                            primary_score=score,
                            primary_equity_notional_pct=primary_equity_notional_pct,
                            rs_alpha=t_rs,
                            trade_weekday=trade_weekday,
                            prev_return=metrics.get("prev_return"),
                            prev_rsi2=prev_rsi2,
                        )
                        primary_size_multiplier = resolve_daytrade_primary_size_multiplier(
                            breadth_val=entry_breadth,
                            gap_pct=metrics.get("gap_pct"),
                            open_vs_sma_atr=metrics.get("open_vs_sma_atr"),
                            market_ratio=market_ratio,
                            primary_score=score,
                            trade_weekday=trade_weekday,
                            prev_return=metrics.get("prev_return"),
                            prev_rsi2=prev_rsi2,
                        )
                        candidates.append({
                            "code": ticker,
                            "s_idx": s_idx,
                            "score": score,
                            "open": t_open,
                            "atr": prev_atr,
                            "turnover": t_turnover,
                            "setup_type": "primary",
                            "notional_pct": primary_notional_pct,
                            "equity_notional_pct": primary_equity_notional_pct,
                            "risk_budget_pct": primary_risk_budget_pct,
                            "size_multiplier": primary_size_multiplier,
                            "gap_pct": metrics.get("gap_pct"),
                            "prev_return": metrics.get("prev_return"),
                            "prev_rsi2": prev_rsi2,
                            "open_from_prev_low_atr": metrics.get("open_from_prev_low_atr"),
                            "open_vs_sma_atr": metrics.get("open_vs_sma_atr"),
                            "rs_alpha": float(t_rs) if np.isfinite(t_rs) else np.nan,
                        })
                        continue

        if strong_oversold_market_allowed and t_turnover >= DAYTRADE_MIN_TURNOVER:
            strong_oversold_metrics = evaluate_daytrade_strong_oversold_open_setup(
                t_open,
                prev_close,
                entry_breadth,
                prev_atr=prev_atr,
                prev_rsi2=prev_rsi2,
                rs_alpha=t_rs,
                prev_prev_close=prev_prev_close,
                prev_sma_trend=prev_sma_trend,
            )
            if strong_oversold_metrics is not None:
                if is_daytrade_strong_oversold_tuesday_stretched_open_filtered(
                    strong_oversold_metrics["open_vs_trend_atr"],
                    trade_weekday=trade_weekday,
                ):
                    continue
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
                        "atr": prev_atr,
                    "turnover": t_turnover,
                    "setup_type": "strong_oversold",
                    "notional_pct": resolve_daytrade_strong_oversold_notional_pct(
                        breadth_val=entry_breadth,
                        gap_pct=strong_oversold_metrics.get("gap_pct"),
                        market_ratio=market_ratio,
                        score=score,
                        open_vs_trend_atr=strong_oversold_metrics.get("open_vs_trend_atr"),
                        trade_weekday=trade_weekday,
                    ),
                    "equity_notional_pct": resolve_daytrade_strong_oversold_equity_notional_pct(
                        breadth_val=entry_breadth,
                        gap_pct=strong_oversold_metrics.get("gap_pct"),
                        market_ratio=market_ratio,
                        score=score,
                        open_vs_trend_atr=strong_oversold_metrics.get("open_vs_trend_atr"),
                        trade_weekday=trade_weekday,
                    ),
                    "risk_budget_pct": resolve_daytrade_strong_oversold_risk_budget_pct(
                        breadth_val=entry_breadth,
                        gap_pct=strong_oversold_metrics.get("gap_pct"),
                        market_ratio=market_ratio,
                        score=score,
                        open_vs_trend_atr=strong_oversold_metrics.get("open_vs_trend_atr"),
                        trade_weekday=trade_weekday,
                    ),
                    "size_multiplier": resolve_daytrade_strong_oversold_size_multiplier(
                        breadth_val=entry_breadth,
                        gap_pct=strong_oversold_metrics.get("gap_pct"),
                        market_ratio=market_ratio,
                        score=score,
                        open_vs_trend_atr=strong_oversold_metrics.get("open_vs_trend_atr"),
                        trade_weekday=trade_weekday,
                    ),
                    "stop_mult": DAYTRADE_STRONG_OVERSOLD_STOP_MULT,
                    "target_mult": DAYTRADE_STRONG_OVERSOLD_TARGET_MULT,
                    "gap_pct": strong_oversold_metrics.get("gap_pct"),
                    "prev_return": strong_oversold_metrics.get("prev_return"),
                    "prev_rsi2": strong_oversold_metrics.get("prev_rsi2"),
                    "open_from_prev_low_atr": strong_oversold_metrics.get("open_from_prev_low_atr"),
                    "open_vs_sma_atr": strong_oversold_metrics.get("open_vs_trend_atr"),
                    "rs_alpha": float(t_rs) if np.isfinite(t_rs) else np.nan,
                })

        if fallback_market_allowed and fallback_trend_allowed and t_turnover >= DAYTRADE_MIN_TURNOVER:
            fallback_metrics = evaluate_daytrade_fallback_open_setup(
                t_open, prev_close, t_sma_med, entry_breadth,
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
                        "atr": prev_atr,
                "turnover": t_turnover,
                "setup_type": "fallback",
                "notional_pct": resolve_daytrade_fallback_notional_pct(
                    breadth_val=entry_breadth,
                    score=score,
                    prev_return=fallback_metrics.get("prev_return"),
                    market_ratio=market_ratio,
                    open_vs_sma_atr=fallback_metrics.get("open_vs_sma_atr"),
                    trade_weekday=trade_weekday,
                    default_pct=DAYTRADE_FALLBACK_MAX_NOTIONAL_PCT,
                ),
                "equity_notional_pct": resolve_daytrade_fallback_equity_notional_pct(
                    gap_pct=fallback_metrics["gap_pct"],
                    breadth_val=entry_breadth,
                    market_ratio=market_ratio,
                    prev_return=fallback_metrics["prev_return"],
                    open_vs_sma_atr=fallback_metrics.get("open_vs_sma_atr"),
                    score=score,
                    trade_weekday=trade_weekday,
                ),
                "stop_mult": DAYTRADE_FALLBACK_INTRADAY_STOP_MULT,
                "target_mult": DAYTRADE_FALLBACK_INTRADAY_TARGET_MULT,
                "prev_return": fallback_metrics.get("prev_return"),
                "prev_rsi2": fallback_metrics.get("prev_rsi2"),
                "open_from_prev_low_atr": fallback_metrics.get("open_from_prev_low_atr"),
                "open_vs_sma_atr": fallback_metrics.get("open_vs_sma_atr"),
                "rs_alpha": float(t_rs) if np.isfinite(t_rs) else np.nan,
            })

        if catchup_market_allowed and t_turnover >= DAYTRADE_CATCHUP_MIN_TURNOVER:
            catchup_metrics_list = evaluate_daytrade_catchup_open_setups(
                t_open, prev_close, t_sma_med, entry_breadth,
                prev_atr=prev_atr, prev_low=prev_low,
                prev_rsi2=prev_rsi2, rs_alpha=t_rs,
                prev_prev_close=prev_prev_close,
                prev_sma_trend=prev_sma_trend,
            )
            for catchup_metrics in catchup_metrics_list:
                score = score_daytrade_catchup_open_setup(catchup_metrics)
                if not np.isfinite(score) or score < DAYTRADE_CATCHUP_MIN_SETUP_SCORE:
                    continue
                risk_budget_pct = None
                if catchup_metrics["setup_type"] == "catchup_gapdown":
                    stop_mult = DAYTRADE_CATCHUP_GAPDOWN_STOP_MULT
                    target_mult = DAYTRADE_CATCHUP_GAPDOWN_TARGET_MULT
                    notional_pct = resolve_daytrade_catchup_notional_pct(
                        setup_type=catchup_metrics["setup_type"],
                        breadth_val=entry_breadth,
                        market_ratio=market_ratio,
                        prev_return=catchup_metrics.get("prev_return"),
                        open_vs_sma_atr=catchup_metrics.get("open_vs_sma_atr"),
                        score=score,
                        rs_alpha=catchup_metrics.get("rs_alpha"),
                        default_pct=DAYTRADE_CATCHUP_GAPDOWN_NOTIONAL_PCT,
                    )
                    equity_notional_pct = resolve_daytrade_catchup_equity_notional_pct(
                        setup_type=catchup_metrics["setup_type"],
                        breadth_val=entry_breadth,
                        gap_pct=catchup_metrics["gap_pct"],
                        prev_return=catchup_metrics["prev_return"],
                        open_vs_sma_atr=catchup_metrics.get("open_vs_sma_atr"),
                        score=score,
                        trade_weekday=trade_weekday,
                        default_pct=DAYTRADE_CATCHUP_GAPDOWN_EQUITY_NOTIONAL_PCT,
                    )
                else:
                    stop_mult = DAYTRADE_CATCHUP_RS_STOP_MULT
                    target_mult = DAYTRADE_CATCHUP_RS_TARGET_MULT
                    notional_pct = resolve_daytrade_catchup_notional_pct(
                        setup_type=catchup_metrics["setup_type"],
                        breadth_val=entry_breadth,
                        market_ratio=market_ratio,
                        prev_return=catchup_metrics.get("prev_return"),
                        open_vs_sma_atr=catchup_metrics.get("open_vs_sma_atr"),
                        score=score,
                        rs_alpha=catchup_metrics.get("rs_alpha"),
                        default_pct=DAYTRADE_CATCHUP_RS_NOTIONAL_PCT,
                    )
                    equity_notional_pct = resolve_daytrade_catchup_equity_notional_pct(
                        setup_type=catchup_metrics["setup_type"],
                        breadth_val=entry_breadth,
                        gap_pct=catchup_metrics["gap_pct"],
                        prev_return=catchup_metrics["prev_return"],
                        open_vs_sma_atr=catchup_metrics.get("open_vs_sma_atr"),
                        score=score,
                        trade_weekday=trade_weekday,
                        default_pct=DAYTRADE_CATCHUP_RS_EQUITY_NOTIONAL_PCT,
                    )
                    if (
                        catchup_metrics["setup_type"] == "catchup_rs"
                        and np.isfinite(notional_pct)
                        and float(notional_pct) >= DAYTRADE_CATCHUP_RS_STRONG_CONTINUATION_NOTIONAL_PCT
                    ):
                        risk_budget_pct = DAYTRADE_CATCHUP_RS_STRONG_CONTINUATION_RISK_BUDGET_PCT
                catchup_candidates.append({
                    "code": ticker,
                    "s_idx": s_idx,
                    "score": score,
                    "gap_pct": catchup_metrics["gap_pct"],
                    "open": t_open,
                    "atr": prev_atr,
                    "turnover": t_turnover,
                    "setup_type": catchup_metrics["setup_type"],
                    "notional_pct": notional_pct,
                    "equity_notional_pct": equity_notional_pct,
                    "risk_budget_pct": risk_budget_pct,
                    "size_multiplier": resolve_daytrade_catchup_size_multiplier(
                        setup_type=catchup_metrics["setup_type"],
                        breadth_val=entry_breadth,
                        gap_pct=catchup_metrics["gap_pct"],
                        market_ratio=market_ratio,
                        score=score,
                        rs_alpha=t_rs,
                        open_vs_sma_atr=catchup_metrics.get("open_vs_sma_atr"),
                        trade_weekday=trade_weekday,
                    ),
                    "stop_mult": stop_mult,
                    "target_mult": target_mult,
                    "prev_return": catchup_metrics.get("prev_return"),
                    "prev_rsi2": catchup_metrics.get("prev_rsi2"),
                    "open_from_prev_low_atr": catchup_metrics.get("open_from_prev_low_atr"),
                    "open_vs_sma_atr": catchup_metrics.get("open_vs_sma_atr"),
                    "rs_alpha": catchup_metrics.get("rs_alpha"),
                    "symbol_trend_ratio": catchup_metrics.get("symbol_trend_ratio"),
                })

        if (
            (inverse_market_allowed or inverse_pullback_market_allowed)
            and ticker in inverse_code_set
            and t_turnover >= resolve_daytrade_inverse_min_turnover(entry_breadth)
        ):
            inverse_metrics = evaluate_daytrade_inverse_open_setup(
                t_open,
                prev_close,
                entry_breadth,
                prev_atr=prev_atr,
                prev_prev_close=prev_prev_close,
                market_open=market_open,
                prev_market_close=prev_market_close,
                prev_market_sma_trend=prev_market_sma_trend,
                trade_date=curr_time,
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
                    elif setup_type == "inverse_rebreak":
                        stop_mult = DAYTRADE_INVERSE_REBREAK_STOP_MULT
                        target_mult = DAYTRADE_INVERSE_REBREAK_TARGET_MULT
                    else:
                        stop_mult = DAYTRADE_INVERSE_STOP_MULT
                        target_mult = DAYTRADE_INVERSE_TARGET_MULT
                    inverse_candidates.append({
                        "code": ticker,
                        "s_idx": s_idx,
                        "score": score,
                        "open": t_open,
                        "atr": prev_atr,
                        "turnover": t_turnover,
                        "setup_type": setup_type,
                        "notional_pct": DAYTRADE_INVERSE_NOTIONAL_PCT,
                        "equity_notional_pct": DAYTRADE_INVERSE_EQUITY_NOTIONAL_PCT,
                        "stop_mult": stop_mult,
                        "target_mult": target_mult,
                        "gap_pct": inverse_metrics.get("gap_pct"),
                        "prev_return": inverse_metrics.get("prev_return"),
                        "prev_rsi2": inverse_metrics.get("prev_rsi2"),
                        "open_vs_sma_atr": inverse_metrics.get("open_vs_sma_atr"),
                        "market_ratio": inverse_metrics.get("market_ratio"),
                    })

        if (
            bull_etf_market_allowed
            and ticker in bull_etf_code_set
            and t_turnover >= resolve_daytrade_scan_min_turnover(ticker, entry_breadth)
        ):
            bull_etf_metrics = evaluate_daytrade_bull_etf_open_setup(
                t_open,
                prev_close,
                sma_med_prev[s_idx],
                entry_breadth,
                prev_atr=prev_atr,
                prev_rsi2=prev_rsi2,
                prev_prev_close=prev_prev_close,
            )
            if bull_etf_metrics is not None:
                score = score_daytrade_bull_etf_open_setup(bull_etf_metrics)
                if np.isfinite(score) and score >= DAYTRADE_BULL_ETF_LOW_BREADTH_REBOUND_MIN_SETUP_SCORE:
                    bull_etf_candidates.append({
                        "code": ticker,
                        "s_idx": s_idx,
                        "score": score,
                        "open": t_open,
                        "atr": prev_atr,
                        "turnover": t_turnover,
                        "setup_type": "bull_etf_rebound",
                        "notional_pct": DAYTRADE_BULL_ETF_LOW_BREADTH_REBOUND_NOTIONAL_PCT,
                        "equity_notional_pct": DAYTRADE_BULL_ETF_LOW_BREADTH_REBOUND_EQUITY_NOTIONAL_PCT,
                        "stop_mult": DAYTRADE_FALLBACK_INTRADAY_STOP_MULT,
                        "target_mult": DAYTRADE_FALLBACK_INTRADAY_TARGET_MULT,
                        "gap_pct": bull_etf_metrics.get("gap_pct"),
                        "prev_return": bull_etf_metrics.get("prev_return"),
                        "prev_rsi2": bull_etf_metrics.get("prev_rsi2"),
                        "open_vs_sma_atr": bull_etf_metrics.get("open_vs_sma_atr"),
                    })

        setup_candidate_count_after = (
            len(candidates)
            + len(strong_oversold_candidates)
            + len(fallback_candidates)
            + len(catchup_candidates)
            + len(inverse_candidates)
            + len(bull_etf_candidates)
        )
        if setup_candidate_count_after == setup_candidate_count_before:
            setup_stats["no_setup_candidate_after_scan"] += 1

    return DaytradeCandidateGroups(
        primary=candidates,
        strong_oversold=strong_oversold_candidates,
        fallback=fallback_candidates,
        catchup=catchup_candidates,
        inverse=inverse_candidates,
        bull_etf=bull_etf_candidates,
        scan_stats=scan_stats,
        setup_stats=setup_stats,
    )
