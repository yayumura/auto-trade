import argparse
import csv
import math
import os

from core.config import (
    DAYTRADE_EXIT_LOG_FILE,
    DAYTRADE_PRODUCTION_SNAPSHOT_FILE,
    RUNTIME_LIVE_ORDER_CONFIG_HASH,
)
from core.daytrade_production_replay import (
    load_daytrade_production_snapshots,
    replay_daytrade_production_snapshot,
)
from core.live_approval_manifest import read_git_commit_sha


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Replay point-in-time daytrade production snapshots with the shared "
            "candidate engine and report actual linked exits."
        )
    )
    parser.add_argument(
        "--snapshots-file",
        default=DAYTRADE_PRODUCTION_SNAPSHOT_FILE,
    )
    parser.add_argument(
        "--exit-log",
        default=DAYTRADE_EXIT_LOG_FILE,
    )
    parser.add_argument(
        "--trade-mode",
        default="KABUCOM_LIVE",
        choices=("KABUCOM_LIVE", "KABUCOM_TEST"),
    )
    parser.add_argument(
        "--min-snapshots",
        type=int,
        default=1,
        help="Operational completeness threshold only; it is not a profitability proof.",
    )
    return parser.parse_args()


def _as_bool(value):
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _load_linked_exits(path, snapshot_ids):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("decision_snapshot_id") not in snapshot_ids:
                continue
            if _as_bool(row.get("is_simulation")):
                continue
            rows.append(row)
    return rows


def _float(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    return result if math.isfinite(result) else 0.0


def run_production_replay(
    *,
    snapshots_file,
    exit_log,
    trade_mode,
    min_snapshots=1,
    expected_code_commit_sha=None,
    expected_runtime_config_hash=None,
):
    snapshots = [
        snapshot
        for snapshot in load_daytrade_production_snapshots(snapshots_file)
        if str(snapshot.get("trade_mode") or "").upper() == trade_mode
        and not bool(snapshot.get("is_simulation"))
    ]
    results = [
        replay_daytrade_production_snapshot(
            snapshot,
            expected_code_commit_sha=expected_code_commit_sha,
            expected_runtime_config_hash=expected_runtime_config_hash,
        )
        for snapshot in snapshots
    ]
    parity_count = sum(result.parity for result in results)
    replayable_count = sum(result.replayable for result in results)
    replayable_ids = {
        result.snapshot_id
        for result in results
        if result.parity and result.replayable
    }
    eligible_ids = {
        result.snapshot_id
        for snapshot, result in zip(snapshots, results)
        if result.parity
        and result.replayable
        and bool(snapshot.get("eligible_for_decision_clean_holdout"))
    }
    # KABUCOM_TEST snapshots can prove schema / selector / order-lifecycle parity,
    # even though they must never be counted as LIVE clean-holdout evidence.
    exits = _load_linked_exits(exit_log, replayable_ids)
    pnl = [_float(row.get("observed_pnl")) for row in exits]
    gross_profit = sum(value for value in pnl if value > 0)
    gross_loss = abs(sum(value for value in pnl if value < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    summary = {
        "trade_mode": trade_mode,
        "snapshots": len(snapshots),
        "replayable": replayable_count,
        "parity": parity_count,
        "eligible_execution_replay": len(replayable_ids),
        "eligible_decision_clean_holdout": len(eligible_ids),
        "selected_decisions": sum(bool(result.selected_codes) for result in results),
        "linked_actual_exits": len(exits),
        "observed_pnl": sum(pnl),
        "observed_gross_pnl": sum(pnl),
        "observed_profit_factor": profit_factor,
    }
    if len(snapshots) < int(min_snapshots):
        return 2, summary
    if parity_count != len(snapshots):
        return 3, summary
    return 0, summary


def main():
    args = parse_args()
    code, summary = run_production_replay(
        snapshots_file=args.snapshots_file,
        exit_log=args.exit_log,
        trade_mode=args.trade_mode,
        min_snapshots=args.min_snapshots,
        expected_code_commit_sha=read_git_commit_sha(),
        expected_runtime_config_hash=RUNTIME_LIVE_ORDER_CONFIG_HASH,
    )
    print("=" * 60)
    print("DAYTRADE PRODUCTION SNAPSHOT REPLAY")
    print("=" * 60)
    for key, value in summary.items():
        if key == "observed_profit_factor" and math.isinf(value):
            value = "inf"
        print(f"{key.upper()}: {value}")
    if code == 2:
        print("STATUS: INSUFFICIENT_SNAPSHOTS")
    elif code == 3:
        print("STATUS: PARITY_FAILED")
    else:
        print("STATUS: PARITY_OK")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
