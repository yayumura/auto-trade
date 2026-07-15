from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import math
from typing import Any

import numpy as np

from core.config import (
    LIQUIDITY_LIMIT_RATE,
    SMA_LONG_PERIOD,
    SMA_MEDIUM_PERIOD,
    SMA_TREND_PERIOD,
)
from core.daytrade_candidate_engine import (
    DaytradeOpenArrayView,
    generate_daytrade_candidate_groups,
)
from core.logic import (
    DAYTRADE_BULL_ETF_CODES,
    DAYTRADE_INVERSE_CODES,
    DAYTRADE_MAX_GAP,
    DAYTRADE_MAX_RSI2,
    build_daytrade_open_market_context,
    resolve_daytrade_scan_min_turnover,
)

DAYTRADE_DISCOVERY_OPEN_SCENARIOS = (-0.02, 0.0, 0.02)
DAYTRADE_DISCOVERY_BATCH_SIZE = 49
DAYTRADE_DISCOVERY_BATCH_COUNT = 4
DAYTRADE_DISCOVERY_MAX_SYMBOLS = DAYTRADE_DISCOVERY_BATCH_SIZE * DAYTRADE_DISCOVERY_BATCH_COUNT


def normalize_daytrade_observation_code(value: Any) -> str:
    code = str(value or "").strip().upper()
    return code[:-2] if code.endswith(".T") else code


def select_daytrade_production_observation_codes(
    observations: Sequence[Mapping[str, Any]],
    *,
    breadth: float,
    max_symbols: int = 49,
    excluded_codes: Sequence[Any] = (),
    reserved_codes: Sequence[Any] | None = None,
    liquidity_limit: float = LIQUIDITY_LIMIT_RATE,
    min_turnover_resolver: Callable[[str, float], float] | None = None,
) -> list[str]:
    """Rank the live observation universe using prior-day information only."""
    if int(max_symbols) <= 0 or not math.isfinite(float(breadth)):
        return []
    resolver = min_turnover_resolver or resolve_daytrade_scan_min_turnover
    excluded = {
        normalize_daytrade_observation_code(code)
        for code in excluded_codes or ()
    }
    reserved_source = (
        (*DAYTRADE_BULL_ETF_CODES, *DAYTRADE_INVERSE_CODES)
        if reserved_codes is None
        else reserved_codes
    )
    reserved = {
        normalize_daytrade_observation_code(code)
        for code in reserved_source
    }
    reserved.discard("1321")

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for observation in observations:
        code = normalize_daytrade_observation_code(
            observation.get("code", observation.get("ticker"))
        )
        if not code or code == "1321" or code in excluded or code in seen:
            continue
        ticker = str(observation.get("ticker") or code).strip().upper()
        is_reserved = code in reserved
        if not bool(observation.get("is_prime")) and not is_reserved:
            continue
        try:
            prev_close = float(observation.get("close"))
            prev_atr = float(observation.get("atr"))
            prev_turnover = float(observation.get("turnover"))
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(value) and value > 0 for value in (prev_close, prev_atr, prev_turnover)):
            continue
        if prev_turnover < float(resolver(ticker, float(breadth))):
            continue
        headroom = prev_turnover * float(liquidity_limit) / (prev_close * 100.0)
        if not math.isfinite(headroom) or headroom < 1.0:
            continue
        seen.add(code)
        rows.append(
            {
                "code": code,
                "reserved": is_reserved,
                "headroom": headroom,
                "turnover": prev_turnover,
            }
        )

    rows.sort(
        key=lambda item: (
            not item["reserved"],
            item["code"] if item["reserved"] else "",
            -item["headroom"],
            -item["turnover"],
            item["code"],
        )
    )
    return [str(item["code"]) for item in rows[: int(max_symbols)]]


def build_daytrade_production_observation_indices_by_day(
    *,
    bundle_np: Mapping[str, Any],
    timeline: Sequence[Any],
    prime_tickers: Sequence[str],
    max_symbols: int = 49,
    excluded_codes: Sequence[Any] = (),
    liquidity_limit: float = LIQUIDITY_LIMIT_RATE,
) -> dict[str, tuple[int, ...]]:
    """Replay the live prior-day 49-symbol registry policy for every trade date."""
    tickers = [str(item) for item in bundle_np.get("tickers", ())]
    close_np = np.asarray(bundle_np["Close"])
    atr_np = np.asarray(bundle_np["ATR"])
    turnover_np = np.asarray(bundle_np["Turnover"])
    sma_long_np = np.asarray(bundle_np[f"SMA{SMA_LONG_PERIOD}"])
    if any(array.ndim != 2 for array in (close_np, atr_np, turnover_np, sma_long_np)):
        raise ValueError("production observation arrays must be two-dimensional")
    if any(array.shape != close_np.shape for array in (atr_np, turnover_np, sma_long_np)):
        raise ValueError("production observation arrays must have identical shapes")
    if close_np.shape[0] != len(timeline) or close_np.shape[1] != len(tickers):
        raise ValueError("production observation arrays must align with timeline and tickers")

    prime = {str(ticker) for ticker in prime_tickers}
    reserved = {
        normalize_daytrade_observation_code(code)
        for code in (*DAYTRADE_BULL_ETF_CODES, *DAYTRADE_INVERSE_CODES)
    }
    prime_indices = np.asarray(
        [index for index, ticker in enumerate(tickers) if ticker in prime],
        dtype=int,
    )
    eligible_indices = [
        index
        for index, ticker in enumerate(tickers)
        if ticker in prime or normalize_daytrade_observation_code(ticker) in reserved
    ]
    code_to_index = {
        normalize_daytrade_observation_code(ticker): index
        for index, ticker in enumerate(tickers)
    }

    result: dict[str, tuple[int, ...]] = {}
    for day_index in range(2, len(timeline)):
        feature_index = day_index - 1
        prime_close = close_np[feature_index, prime_indices]
        prime_sma = sma_long_np[feature_index, prime_indices]
        valid = np.isfinite(prime_close) & np.isfinite(prime_sma)
        breadth = float(np.mean(prime_close[valid] > prime_sma[valid])) if np.any(valid) else 0.0
        observations = [
            {
                "ticker": tickers[index],
                "code": normalize_daytrade_observation_code(tickers[index]),
                "is_prime": tickers[index] in prime,
                "close": close_np[feature_index, index],
                "atr": atr_np[feature_index, index],
                "turnover": turnover_np[feature_index, index],
            }
            for index in eligible_indices
        ]
        selected_codes = select_daytrade_production_observation_codes(
            observations,
            breadth=breadth,
            max_symbols=max_symbols,
            excluded_codes=excluded_codes,
            reserved_codes=tuple(reserved),
            liquidity_limit=liquidity_limit,
        )
        result[str(np.datetime64(timeline[day_index], "D"))] = tuple(
            code_to_index[code]
            for code in selected_codes
            if code in code_to_index
        )
    return result


def select_daytrade_rotating_discovery_codes(
    *,
    tickers: Sequence[str],
    trade_date: Any,
    feature_asof: Any,
    close_prev: Sequence[float],
    close_prev2: Sequence[float],
    open_prev: Sequence[float],
    low_prev: Sequence[float],
    atr_prev: Sequence[float],
    turnover_prev: Sequence[float],
    rsi2_prev: Sequence[float],
    rs_alpha_prev: Sequence[float],
    sma_med_prev: Sequence[float],
    sma_long_prev: Sequence[float],
    sma_trend_prev: Sequence[float],
    prime_tickers: Sequence[str],
    excluded_codes: Sequence[Any] = (),
    liquidity_limit: float = LIQUIDITY_LIMIT_RATE,
    max_symbols: int = DAYTRADE_DISCOVERY_MAX_SYMBOLS,
    open_scenarios: Sequence[float] = DAYTRADE_DISCOVERY_OPEN_SCENARIOS,
) -> list[str]:
    """Select one trade day's rotating universe from prior-day evidence only."""
    if int(max_symbols) != DAYTRADE_DISCOVERY_MAX_SYMBOLS:
        raise ValueError(
            "rotating discovery max_symbols is fixed by four 49-symbol registry batches"
        )
    scenarios = tuple(float(value) for value in open_scenarios)
    if scenarios != DAYTRADE_DISCOVERY_OPEN_SCENARIOS:
        raise ValueError("rotating discovery opening scenarios are fixed")

    try:
        trade_day = np.datetime64(trade_date, "D")
        feature_day = np.datetime64(feature_asof, "D")
    except (TypeError, ValueError):
        return []
    if np.isnat(trade_day) or np.isnat(feature_day) or trade_day <= feature_day:
        return []

    ticker_values = [str(ticker) for ticker in tickers]
    codes = [normalize_daytrade_observation_code(ticker) for ticker in ticker_values]
    if not ticker_values or any(not code for code in codes) or len(set(codes)) != len(codes):
        raise ValueError("rotating discovery tickers must be unique after normalization")

    raw_vectors = {
        "close_prev": close_prev,
        "close_prev2": close_prev2,
        "open_prev": open_prev,
        "low_prev": low_prev,
        "atr_prev": atr_prev,
        "turnover_prev": turnover_prev,
        "rsi2_prev": rsi2_prev,
        "rs_alpha_prev": rs_alpha_prev,
        "sma_med_prev": sma_med_prev,
        "sma_long_prev": sma_long_prev,
        "sma_trend_prev": sma_trend_prev,
    }
    vectors = {
        name: np.asarray(values, dtype=float)
        for name, values in raw_vectors.items()
    }
    expected_shape = (len(ticker_values),)
    if any(vector.shape != expected_shape for vector in vectors.values()):
        raise ValueError("rotating discovery feature vectors must align with tickers")

    prime = {str(ticker) for ticker in prime_tickers}
    excluded = {
        normalize_daytrade_observation_code(code)
        for code in excluded_codes or ()
    }
    reserved = {
        normalize_daytrade_observation_code(code)
        for code in (*DAYTRADE_BULL_ETF_CODES, *DAYTRADE_INVERSE_CODES)
    }
    reserved.discard("1321")
    eligible_indices = [
        index
        for index, ticker in enumerate(ticker_values)
        if (
            ticker in prime
            or codes[index] in reserved
        )
        and codes[index] not in excluded
        and codes[index] != "1321"
    ]
    prime_indices = np.asarray(
        [
            index
            for index, ticker in enumerate(ticker_values)
            if ticker in prime
            and codes[index] not in excluded
            and codes[index] != "1321"
        ],
        dtype=int,
    )
    market_index = next(
        (index for index, code in enumerate(codes) if code == "1321"),
        None,
    )
    if market_index is None or prime_indices.size == 0:
        return []

    prime_close = vectors["close_prev"][prime_indices]
    prime_sma = vectors["sma_long_prev"][prime_indices]
    valid = np.isfinite(prime_close) & np.isfinite(prime_sma)
    if not np.any(valid):
        return []
    breadth = float(np.mean(prime_close[valid] > prime_sma[valid]))
    previous_market_close = vectors["close_prev"][market_index]
    previous_market_sma_trend = vectors["sma_trend_prev"][market_index]
    if not (
        np.isfinite(previous_market_close)
        and previous_market_close > 0
        and np.isfinite(previous_market_sma_trend)
        and previous_market_sma_trend > 0
    ):
        return []

    observations = [
        {
            "ticker": ticker_values[index],
            "code": codes[index],
            "is_prime": ticker_values[index] in prime,
            "close": vectors["close_prev"][index],
            "atr": vectors["atr_prev"][index],
            "turnover": vectors["turnover_prev"][index],
        }
        for index in eligible_indices
    ]
    liquidity_codes = select_daytrade_production_observation_codes(
        observations,
        breadth=breadth,
        max_symbols=len(eligible_indices),
        excluded_codes=excluded,
        reserved_codes=tuple(reserved),
        liquidity_limit=liquidity_limit,
    )
    liquidity_rank = {code: rank for rank, code in enumerate(liquidity_codes)}

    scenario_candidates: dict[str, dict[str, float]] = {}
    for scenario in scenarios:
        hypothetical_open = vectors["close_prev"] * (1.0 + scenario)
        hypothetical_market_open = previous_market_close * (1.0 + scenario)
        market_context = build_daytrade_open_market_context(
            trade_date=trade_date,
            feature_asof=feature_asof,
            open_asof=trade_date,
            breadth_val=breadth,
            market_open=hypothetical_market_open,
            prev_market_close=previous_market_close,
            prev_market_sma_trend=previous_market_sma_trend,
        )
        groups = generate_daytrade_candidate_groups(
            DaytradeOpenArrayView(
                tickers=ticker_values,
                universe_indices=eligible_indices,
                open_today=hypothetical_open,
                close_prev=vectors["close_prev"],
                close_prev2=vectors["close_prev2"],
                open_prev=vectors["open_prev"],
                low_prev=vectors["low_prev"],
                atr_prev=vectors["atr_prev"],
                turnover_prev=vectors["turnover_prev"],
                rsi2_prev=vectors["rsi2_prev"],
                rs_alpha_prev=vectors["rs_alpha_prev"],
                sma_med_prev=vectors["sma_med_prev"],
                sma_trend_prev=vectors["sma_trend_prev"],
            ),
            market_context,
            liquidity_limit=liquidity_limit,
            bull_gap_limit=DAYTRADE_MAX_GAP,
            rsi_threshold=DAYTRADE_MAX_RSI2,
        )
        seen_in_scenario: set[str] = set()
        for group in (
            groups.primary,
            groups.strong_oversold,
            groups.fallback,
            groups.catchup,
            groups.inverse,
            groups.bull_etf,
        ):
            for candidate in group:
                code = normalize_daytrade_observation_code(candidate.get("code"))
                if code not in liquidity_rank:
                    continue
                record = scenario_candidates.setdefault(
                    code,
                    {"scenario_count": 0.0, "max_score": float("-inf")},
                )
                record["max_score"] = max(
                    record["max_score"],
                    float(candidate.get("score", float("-inf"))),
                )
                if code not in seen_in_scenario:
                    record["scenario_count"] += 1.0
                    seen_in_scenario.add(code)

    reserved_codes = [code for code in liquidity_codes if code in reserved]
    candidate_codes = sorted(
        (code for code in scenario_candidates if code not in reserved),
        key=lambda code: (
            -scenario_candidates[code]["scenario_count"],
            -scenario_candidates[code]["max_score"],
            liquidity_rank[code],
            code,
        ),
    )
    ordered_codes = list(dict.fromkeys((*reserved_codes, *candidate_codes, *liquidity_codes)))
    return ordered_codes[:DAYTRADE_DISCOVERY_MAX_SYMBOLS]


def build_daytrade_rotating_discovery_indices_by_day(
    *,
    bundle_np: Mapping[str, Any],
    timeline: Sequence[Any],
    prime_tickers: Sequence[str],
    excluded_codes: Sequence[Any] = (),
    liquidity_limit: float = LIQUIDITY_LIMIT_RATE,
    max_symbols: int = DAYTRADE_DISCOVERY_MAX_SYMBOLS,
    open_scenarios: Sequence[float] = DAYTRADE_DISCOVERY_OPEN_SCENARIOS,
) -> dict[str, tuple[int, ...]]:
    """Replay the shared one-day rotating selector across a historical timeline."""
    if int(max_symbols) != DAYTRADE_DISCOVERY_MAX_SYMBOLS:
        raise ValueError(
            "rotating discovery max_symbols is fixed by four 49-symbol registry batches"
        )
    scenarios = tuple(float(value) for value in open_scenarios)
    if scenarios != DAYTRADE_DISCOVERY_OPEN_SCENARIOS:
        raise ValueError("rotating discovery opening scenarios are fixed")

    tickers = [str(item) for item in bundle_np.get("tickers", ())]
    required_fields = (
        "Close",
        "Open",
        "Low",
        "ATR",
        "Turnover",
        "RSI2",
        "RS_Alpha",
        f"SMA{SMA_MEDIUM_PERIOD}",
        f"SMA{SMA_LONG_PERIOD}",
        f"SMA{SMA_TREND_PERIOD}",
    )
    arrays = {field: np.asarray(bundle_np[field]) for field in required_fields}
    close_np = arrays["Close"]
    if any(array.ndim != 2 for array in arrays.values()):
        raise ValueError("rotating discovery arrays must be two-dimensional")
    if any(array.shape != close_np.shape for array in arrays.values()):
        raise ValueError("rotating discovery arrays must have identical shapes")
    if close_np.shape != (len(timeline), len(tickers)):
        raise ValueError("rotating discovery arrays must align with timeline and tickers")

    codes = [normalize_daytrade_observation_code(ticker) for ticker in tickers]
    if any(not code for code in codes) or len(set(codes)) != len(codes):
        raise ValueError("rotating discovery tickers must be unique after normalization")
    code_to_index = {code: index for index, code in enumerate(codes)}

    result: dict[str, tuple[int, ...]] = {}
    for day_index in range(2, len(timeline)):
        feature_index = day_index - 1
        selected_codes = select_daytrade_rotating_discovery_codes(
            tickers=tickers,
            trade_date=timeline[day_index],
            feature_asof=timeline[feature_index],
            close_prev=close_np[feature_index],
            close_prev2=close_np[day_index - 2],
            open_prev=arrays["Open"][feature_index],
            low_prev=arrays["Low"][feature_index],
            atr_prev=arrays["ATR"][feature_index],
            turnover_prev=arrays["Turnover"][feature_index],
            rsi2_prev=arrays["RSI2"][feature_index],
            rs_alpha_prev=arrays["RS_Alpha"][feature_index],
            sma_med_prev=arrays[f"SMA{SMA_MEDIUM_PERIOD}"][feature_index],
            sma_long_prev=arrays[f"SMA{SMA_LONG_PERIOD}"][feature_index],
            sma_trend_prev=arrays[f"SMA{SMA_TREND_PERIOD}"][feature_index],
            prime_tickers=prime_tickers,
            excluded_codes=excluded_codes,
            liquidity_limit=liquidity_limit,
            max_symbols=max_symbols,
            open_scenarios=scenarios,
        )
        day_key = str(np.datetime64(timeline[day_index], "D"))
        result[day_key] = tuple(code_to_index[code] for code in selected_codes)
    return result
