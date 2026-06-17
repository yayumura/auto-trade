from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from core.portfolio_state import (
    load_portfolio_state,
    load_portfolio_positions,
    write_portfolio_state,
)


def test_write_portfolio_state_creates_schema_versioned_json(tmp_path: Path):
    path = tmp_path / "portfolio.json"

    write_portfolio_state(
        str(path),
        [
            {
                "code": "1000",
                "shares": 100,
                "execution_id": "EX-1",
                "entry_order_id": "ORDER-1",
                "buy_time": "2026-04-21 09:00:00",
                "entry_order_unresolved": False,
            }
        ],
        metadata={
            "source": "unit-test",
            "broker_environment": "live",
            "broker_account_type": 4,
            "broker_product": "margin",
        },
    )

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["schema_version"] == 2
    assert raw["format"] == "schema_versioned_json"
    assert raw["metadata"]["source"] == "unit-test"
    assert raw["positions"][0]["code"] == "1000"
    assert raw["positions"][0]["broker_environment"] == "live"
    assert raw["positions"][0]["position_lot_key_source"] == "execution_id"
    assert raw["positions"][0]["position_lot_key_needs_review"] is False

    lot_identity = json.loads(raw["positions"][0]["position_lot_key"])
    assert lot_identity["broker_environment"] == "live"
    assert lot_identity["broker_account_type"] == "4"
    assert lot_identity["broker_product"] == "margin"
    assert lot_identity["symbol"] == "1000"
    assert lot_identity["execution_id"] == "EX-1"
    assert lot_identity["entry_order_id"] == "ORDER-1"

    state = load_portfolio_state(str(path))
    assert state is not None
    assert state.schema_version == 2
    assert state.source_format == "schema_versioned_json"
    assert state.positions[0]["shares"] == 100


def test_load_portfolio_positions_migrates_legacy_csv_and_backs_it_up(tmp_path: Path):
    path = tmp_path / "portfolio.json"
    legacy = pd.DataFrame([
        {
            "code": "1000",
            "shares": 100,
            "buy_time": "2026-04-21 09:00:00",
            "highest_price": 105.0,
        }
    ])
    legacy.to_csv(path, index=False, encoding="utf-8-sig")

    state = load_portfolio_state(str(path))
    assert state is not None
    assert state.source_format == "legacy_csv"
    assert state.needs_migration is True
    assert state.positions[0]["code"] == "1000"

    positions = load_portfolio_positions(str(path))
    assert positions[0]["code"] == "1000"
    assert positions[0]["position_lot_key_source"] == "buy_time"
    assert positions[0]["position_lot_key_needs_review"] is True

    write_portfolio_state(str(path), positions, metadata={"source": "unit-test"})

    archive_dir = tmp_path / "archive"
    archive_files = list(archive_dir.glob("portfolio_legacy_*.json"))
    assert archive_files

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["schema_version"] == 2
    assert raw["positions"][0]["code"] == "1000"
