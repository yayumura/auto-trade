from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from core.config import SMA_LONG_PERIOD, SMA_TREND_PERIOD
from core.logic import calculate_all_technicals_v12, get_prime_tickers


@dataclass(frozen=True)
class MonthlyRotationStrategyConfig:
    version_label: str = "V19.9 Monthly Rotation Profit Tune"
    max_pos: int = 3
    leverage_rate: float = 1.0
    breadth_threshold: float = 0.41
    min_turnover: float = 1_000_000_000.0
    rs_min: float = 0.0
    atr_ratio_max: float = 0.06
    rank_mode: str = "rs"
    hold_score_bonus: float = 20.0
    hold_rank_tolerance: float = 0.0
    score_weight_power: float = 2.2
    rebalance_existing: bool = False
    mom20_score_weight: float = 10.0
    mom60_score_weight: float = -10.0
    atr_penalty_weight: float = 100.0
    trend_gap_score_weight: float = 0.0
    mom20_min: float = -10.0
    mom60_min: float = -10.0
    mom20_cap: float = 0.575
    mom60_cap: float = 1.25
    dynamic_topn: bool = False
    require_stock_sma20: bool = False
    use_index_sma20: bool = False
    index_mom1_min: float | None = None
    breadth_delta_min: float | None = None
    use_sma_exit: bool = True
    exit_buffer: float = 0.975


PROD_MONTHLY_ROTATION_CONFIG = MonthlyRotationStrategyConfig()


def get_prod_monthly_rotation_backtest_params() -> dict:
    params = asdict(PROD_MONTHLY_ROTATION_CONFIG)
    params.pop("version_label", None)
    return params


def is_rotation_regime_bull(
    breadth_latest: float,
    idx_close: float | None,
    idx_sma_trend: float | None,
    idx_sma20: float | None = None,
    idx_mom1: float | None = None,
    prior_breadth: float | None = None,
    config: MonthlyRotationStrategyConfig = PROD_MONTHLY_ROTATION_CONFIG,
) -> bool:
    regime_is_bull = float(breadth_latest) >= float(config.breadth_threshold)
    if idx_close is not None and idx_sma_trend is not None:
        regime_is_bull = regime_is_bull and np.isfinite(idx_sma_trend) and float(idx_close) > float(idx_sma_trend)
    if config.use_index_sma20:
        regime_is_bull = regime_is_bull and idx_sma20 is not None and np.isfinite(idx_sma20) and float(idx_close) > float(idx_sma20)
    if config.index_mom1_min is not None:
        regime_is_bull = regime_is_bull and idx_mom1 is not None and float(idx_mom1) >= float(config.index_mom1_min)
    if config.breadth_delta_min is not None:
        regime_is_bull = regime_is_bull and prior_breadth is not None and ((float(breadth_latest) - float(prior_breadth)) >= float(config.breadth_delta_min))
    return bool(regime_is_bull)


def select_monthly_rotation_candidates_from_snapshot(
    snapshot: dict,
    held_codes: list[str] | set[str] | None = None,
    config: MonthlyRotationStrategyConfig = PROD_MONTHLY_ROTATION_CONFIG,
    limit: int | None = None,
) -> tuple[list[dict], float, bool]:
    held_codes = set(str(code) for code in (held_codes or []))
    prime_ref = set(snapshot.get("prime_ref") or get_prime_tickers())
    all_tickers = [str(ticker) for ticker in snapshot.get("all_tickers", [])]
    idx_ticker = str(snapshot.get("index_ticker", "1321.T"))
    elite_cols = [ticker for ticker in all_tickers if ticker in prime_ref]
    if not elite_cols:
        return [], 0.0, False

    close_map = snapshot["close_map"]
    sma_long_map = snapshot["sma_long_map"]
    breadth_latest = float(np.mean([
        float(close_map[ticker]) > float(sma_long_map[ticker])
        for ticker in elite_cols
        if ticker in close_map and ticker in sma_long_map
    ]))

    idx_close = close_map.get(idx_ticker)
    idx_sma_trend = snapshot["sma_trend_map"].get(idx_ticker)
    idx_sma20 = snapshot["sma20_map"].get(idx_ticker)
    idx_mom1 = None
    idx_prev20 = snapshot["prev20_map"].get(idx_ticker)
    if idx_close is not None and idx_prev20 is not None and np.isfinite(idx_prev20) and float(idx_prev20) > 0:
        idx_mom1 = (float(idx_close) / float(idx_prev20)) - 1.0

    prior_breadth = snapshot.get("prior_breadth")
    regime_is_bull = is_rotation_regime_bull(
        breadth_latest=breadth_latest,
        idx_close=idx_close,
        idx_sma_trend=idx_sma_trend,
        idx_sma20=idx_sma20,
        idx_mom1=idx_mom1,
        prior_breadth=prior_breadth,
        config=config,
    )
    if not regime_is_bull:
        return [], breadth_latest, False

    sma20_map = snapshot["sma20_map"]
    sma_trend_map = snapshot["sma_trend_map"]
    atr_map = snapshot["atr_map"]
    rs_map = snapshot["rs_map"]
    turnover_map = snapshot["turnover_map"]
    prev20_map = snapshot["prev20_map"]
    prev60_map = snapshot["prev60_map"]
    code_to_name = snapshot.get("code_to_name", {})

    candidates = []
    for ticker in all_tickers:
        code = str(ticker).replace(".T", "")
        if ticker not in prime_ref or ticker == idx_ticker:
            continue

        t_close = float(close_map.get(ticker, np.nan))
        t_sma20 = float(sma20_map.get(ticker, np.nan))
        t_sma_trend = float(sma_trend_map.get(ticker, np.nan))
        t_atr = float(atr_map.get(ticker, np.nan))
        t_rs = float(rs_map.get(ticker, np.nan))
        t_turnover = float(turnover_map.get(ticker, np.nan))
        t_prev20 = float(prev20_map.get(ticker, np.nan))
        t_prev60 = float(prev60_map.get(ticker, np.nan))

        if not np.isfinite([t_close, t_sma_trend, t_atr, t_rs, t_turnover]).all():
            continue
        if t_close <= 0 or t_turnover < config.min_turnover or t_rs < config.rs_min:
            continue
        if t_close <= t_sma_trend:
            continue
        if config.require_stock_sma20 and (not np.isfinite(t_sma20) or t_close <= t_sma20):
            continue
        if t_atr <= 0:
            continue
        atr_ratio = t_atr / t_close
        if atr_ratio > config.atr_ratio_max:
            continue

        mom20 = (t_close / t_prev20) - 1.0 if np.isfinite(t_prev20) and t_prev20 > 0 else np.nan
        mom60 = (t_close / t_prev60) - 1.0 if np.isfinite(t_prev60) and t_prev60 > 0 else np.nan
        if not np.isfinite([mom20, mom60]).all():
            continue
        if mom20 < config.mom20_min or mom60 < config.mom60_min:
            continue
        if mom20 > config.mom20_cap or mom60 > config.mom60_cap:
            continue

        if config.rank_mode == "blend":
            score = t_rs - (atr_ratio * 1000.0)
        elif config.rank_mode == "risk_adj":
            score = t_rs / max(atr_ratio, 1e-6)
        else:
            score = t_rs

        trend_gap = (t_close / t_sma_trend) - 1.0 if t_sma_trend > 0 else 0.0
        score += (
            (mom20 * config.mom20_score_weight)
            + (mom60 * config.mom60_score_weight)
            - (atr_ratio * config.atr_penalty_weight)
            + (trend_gap * config.trend_gap_score_weight)
        )
        if code in held_codes:
            score += config.hold_score_bonus

        candidates.append({
            "code": code,
            "name": code_to_name.get(code, code),
            "price": t_close,
            "atr": t_atr,
            "rs": t_rs,
            "adv_yen": t_turnover,
            "score": float(score),
            "mom20": float(mom20),
            "mom60": float(mom60),
        })

    candidates.sort(key=lambda item: item["score"], reverse=True)
    candidate_limit = config.max_pos if limit is None else limit
    return candidates[: candidate_limit], breadth_latest, True


def normalize_jquants_cache_frame(data_df: pd.DataFrame) -> pd.DataFrame:
    normalized = data_df.copy()
    if not isinstance(normalized.columns, pd.MultiIndex):
        return normalized

    new_cols = []
    for col in normalized.columns:
        ticker, field = col[0], col[1]
        if isinstance(field, tuple):
            field = field[0]
        new_cols.append((ticker, field))
    normalized.columns = pd.MultiIndex.from_tuples(new_cols)
    return normalized


def build_rotation_backtest_inputs_from_cache(
    data_df: pd.DataFrame,
    config: MonthlyRotationStrategyConfig = PROD_MONTHLY_ROTATION_CONFIG,
) -> dict:
    normalized = normalize_jquants_cache_frame(data_df)
    bundle = {
        "Open": normalized.xs("Open", axis=1, level=1),
        "High": normalized.xs("High", axis=1, level=1),
        "Low": normalized.xs("Low", axis=1, level=1),
        "Close": normalized.xs("Close", axis=1, level=1),
        "Volume": normalized.xs("Volume", axis=1, level=1),
    }

    indicator_bundle = calculate_all_technicals_v12(normalized)
    all_tickers = list(bundle["Close"].columns)
    prime_ref = set(get_prime_tickers())
    elite_indices = [i for i, ticker in enumerate(all_tickers) if ticker in prime_ref]
    univ_indices = np.array(
        [i for i, ticker in enumerate(all_tickers) if ticker in prime_ref and ticker != "1321.T"],
        dtype=int,
    )

    breadth_matrix = (
        bundle["Close"].values[:, elite_indices]
        > indicator_bundle[f"SMA{SMA_LONG_PERIOD}"].values[:, elite_indices]
    )
    breadth_series = np.nanmean(breadth_matrix.astype(float), axis=1)

    bundle_np = {key: frame.values for key, frame in bundle.items()}
    bundle_np["tickers"] = all_tickers
    bundle_np.update({key: frame.values for key, frame in indicator_bundle.items()})
    return {
        "normalized_data_df": normalized,
        "bundle": bundle,
        "indicator_bundle": indicator_bundle,
        "bundle_np": bundle_np,
        "timeline": bundle["Close"].index,
        "univ_indices": univ_indices,
        "breadth_series": breadth_series,
        "config": config,
    }


def build_rotation_live_snapshot(
    data_df: pd.DataFrame,
    symbols_df: pd.DataFrame | None = None,
    held_codes: list[str] | None = None,
    config: MonthlyRotationStrategyConfig = PROD_MONTHLY_ROTATION_CONFIG,
) -> dict:
    normalized = normalize_jquants_cache_frame(data_df)
    indicator_bundle = calculate_all_technicals_v12(normalized)
    close = indicator_bundle["Close"]
    all_tickers = list(close.columns)
    code_to_name = {}
    if symbols_df is not None and "コード" in symbols_df.columns and "銘柄名" in symbols_df.columns:
        code_to_name = {
            str(row["コード"]): row["銘柄名"]
            for _, row in symbols_df.iterrows()
        }
    prior_breadth = None
    prime_ref = set(get_prime_tickers())
    elite_cols = [ticker for ticker in all_tickers if ticker in prime_ref]
    if len(close) > 21 and elite_cols:
        prior_breadth = float((close[elite_cols].iloc[-22] > indicator_bundle[f"SMA{SMA_LONG_PERIOD}"][elite_cols].iloc[-22]).mean())
    snapshot = {
        "all_tickers": all_tickers,
        "prime_ref": prime_ref,
        "index_ticker": "1321.T",
        "close_map": close.iloc[-1].to_dict(),
        "sma20_map": indicator_bundle["SMA20"].iloc[-1].to_dict(),
        "sma_long_map": indicator_bundle[f"SMA{SMA_LONG_PERIOD}"].iloc[-1].to_dict(),
        "sma_trend_map": indicator_bundle[f"SMA{SMA_TREND_PERIOD}"].iloc[-1].to_dict(),
        "atr_map": indicator_bundle["ATR"].iloc[-1].to_dict(),
        "rs_map": indicator_bundle["RS_Alpha"].iloc[-1].to_dict(),
        "turnover_map": indicator_bundle.get("Turnover", close * 0).iloc[-1].to_dict(),
        "prev20_map": close.shift(20).iloc[-1].to_dict(),
        "prev60_map": close.shift(60).iloc[-1].to_dict(),
        "prior_breadth": prior_breadth,
        "code_to_name": code_to_name,
    }
    top_candidates, rotation_breadth, rotation_bull = select_monthly_rotation_candidates_from_snapshot(
        snapshot=snapshot,
        held_codes=held_codes,
        config=config,
    )
    latest_close_map = {
        str(col).replace(".T", ""): float(indicator_bundle["Close"][col].iloc[-1])
        for col in indicator_bundle["Close"].columns
    }
    sma20_map = {
        str(col).replace(".T", ""): float(indicator_bundle["SMA20"][col].iloc[-1])
        for col in indicator_bundle["SMA20"].columns
    }
    return {
        "normalized_data_df": normalized,
        "indicator_bundle": indicator_bundle,
        "top_candidates": top_candidates if rotation_bull else [],
        "breadth": rotation_breadth,
        "is_bull": rotation_bull,
        "latest_close_map": latest_close_map,
        "sma20_map": sma20_map,
        "target_codes": {str(item["code"]) for item in top_candidates},
        "selection_snapshot": snapshot,
    }


def select_monthly_rotation_candidates_from_df(
    data_df: pd.DataFrame,
    symbols_df: pd.DataFrame | None = None,
    held_codes: list[str] | None = None,
    config: MonthlyRotationStrategyConfig = PROD_MONTHLY_ROTATION_CONFIG,
    limit: int | None = None,
) -> tuple[list[dict], float, bool]:
    snapshot = build_rotation_live_snapshot(
        data_df=data_df,
        symbols_df=symbols_df,
        held_codes=held_codes,
        config=config,
    )
    top_candidates, breadth, is_bull = select_monthly_rotation_candidates_from_snapshot(
        snapshot=snapshot["selection_snapshot"],
        held_codes=held_codes,
        config=config,
        limit=limit,
    )
    return top_candidates, breadth, is_bull


def mark_rotation_portfolio(portfolio: list[dict], realtime_buffers=None, latest_close_map: dict | None = None) -> list[dict]:
    latest_close_map = latest_close_map or {}
    updated = []
    for position in portfolio:
        pos = dict(position)
        code = str(pos["code"])
        current_price = pos.get("current_price", pos["buy_price"])
        if realtime_buffers and code in realtime_buffers:
            rt_price = realtime_buffers[code].get_latest_price()
            if rt_price and rt_price > 0:
                current_price = rt_price
        elif code in latest_close_map and latest_close_map[code] > 0:
            current_price = latest_close_map[code]

        pos["current_price"] = round(float(current_price), 1)
        prev_high = float(pos.get("highest_price", pos["current_price"]))
        pos["highest_price"] = round(max(prev_high, float(current_price)), 1)
        updated.append(pos)
    return updated


def should_keep_monthly_rotation_position(
    position: dict,
    target_codes: set[str],
    regime_is_bull: bool,
    sma20_map: dict | None,
    config: MonthlyRotationStrategyConfig = PROD_MONTHLY_ROTATION_CONFIG,
) -> bool:
    code = str(position["code"])
    if not regime_is_bull or code not in target_codes:
        return False
    if config.use_sma_exit:
        sma20 = None if sma20_map is None else sma20_map.get(code)
        current_price = float(position.get("current_price", position["buy_price"]))
        if sma20 is None or not np.isfinite(sma20):
            return False
        return current_price > (float(sma20) * config.exit_buffer)
    return True


def build_rotation_rebalance_plan(
    portfolio: list[dict],
    snapshot: dict,
    config: MonthlyRotationStrategyConfig = PROD_MONTHLY_ROTATION_CONFIG,
) -> dict:
    target_codes = snapshot["target_codes"] if snapshot.get("is_bull") else set()
    sma20_map = snapshot.get("sma20_map")
    keep_positions = []
    exit_positions = []

    for position in portfolio:
        if should_keep_monthly_rotation_position(
            position,
            target_codes=target_codes,
            regime_is_bull=bool(snapshot.get("is_bull")),
            sma20_map=sma20_map,
            config=config,
        ):
            keep_positions.append(position)
        else:
            exit_positions.append(position)

    return {
        "keep_positions": keep_positions,
        "exit_positions": exit_positions,
        "target_codes": target_codes,
    }


def compute_rotation_target_allocations(
    candidates: list[dict],
    total_budget: float,
    config: MonthlyRotationStrategyConfig = PROD_MONTHLY_ROTATION_CONFIG,
) -> dict[str, float]:
    if not candidates or total_budget <= 0:
        return {}

    if config.score_weight_power > 0:
        weights = [max(float(item.get("score", 0.0)), 0.0) ** config.score_weight_power for item in candidates]
        weight_sum = sum(weights)
        if weight_sum <= 0:
            weights = [1.0] * len(candidates)
            weight_sum = float(len(candidates))
    else:
        weights = [1.0] * len(candidates)
        weight_sum = float(len(candidates))

    return {
        str(item["code"]): float(total_budget * (weight / weight_sum))
        for item, weight in zip(candidates, weights)
    }


def build_rotation_entry_plan(
    candidates: list[dict],
    portfolio: list[dict],
    account_cash: float,
    dynamic_leverage: float,
    config: MonthlyRotationStrategyConfig = PROD_MONTHLY_ROTATION_CONFIG,
) -> dict:
    current_exposure = sum(
        float(position.get("current_price", position["buy_price"])) * int(position["shares"])
        for position in portfolio
    )
    total_equity = float(account_cash) + float(current_exposure)
    buying_power = min(float(account_cash), (total_equity * float(dynamic_leverage)) - current_exposure)
    target_allocations = compute_rotation_target_allocations(
        candidates,
        total_budget=max(0.0, float(buying_power)),
        config=config,
    )
    existing_codes = {str(position["code"]) for position in portfolio}
    planned_entries = [
        candidate for candidate in candidates
        if str(candidate["code"]) not in existing_codes and target_allocations.get(str(candidate["code"]), 0.0) > 0
    ]
    return {
        "current_exposure": float(current_exposure),
        "total_equity": float(total_equity),
        "buying_power": float(max(0.0, buying_power)),
        "target_allocations": target_allocations,
        "planned_entries": planned_entries,
    }


def build_rotation_watchlist(
    candidates: list[dict],
    portfolio: list[dict],
    max_pos: int,
    market_index_code: str = "1321",
) -> dict:
    max_watchlist = max(5, int(max_pos) * 4)
    watchlist = [str(candidate["code"]) for candidate in candidates[:max_watchlist]]
    portfolio_codes = [str(position["code"]) for position in portfolio]
    reg_targets = watchlist + list(set(portfolio_codes))
    current_targets = set(watchlist + portfolio_codes + [market_index_code])
    return {
        "watchlist": watchlist,
        "portfolio_codes": portfolio_codes,
        "registration_targets": reg_targets[:50],
        "current_targets": current_targets,
    }


def compute_rotation_order_size(target_allocation: float, buy_price: float, account_cash: float) -> int:
    if target_allocation <= 0 or buy_price <= 0 or account_cash <= 0:
        return 0

    shares = int((float(target_allocation) // float(buy_price)) // 100) * 100
    if shares < 100:
        return 0

    if float(buy_price) * shares > float(account_cash):
        shares = int((float(account_cash) // float(buy_price)) // 100) * 100
    return shares if shares >= 100 else 0


def build_rotation_position_record(
    item: dict,
    executed_price: float,
    shares: int,
    buy_time: str,
) -> dict:
    return {
        "code": item["code"],
        "name": item["name"],
        "buy_time": buy_time,
        "buy_price": round(float(executed_price), 1),
        "highest_price": round(float(executed_price), 1),
        "current_price": round(float(executed_price), 1),
        "shares": int(shares),
        "buy_atr": float(item.get("atr", 0)),
    }
