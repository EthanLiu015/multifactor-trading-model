import datetime as dt
import json

import numpy as np

from research.portfolio.export_target import export_target_portfolio
from research.portfolio.model import TargetPortfolio


def _target(status: str = "optimal") -> TargetPortfolio:
    return TargetPortfolio(
        rebuild_date=dt.date(2026, 8, 4),
        security_ids=["AAPL", "MSFT", "GOOG"],
        weights=np.array([0.5, -0.3, 0.0]),
        w_prev=np.zeros(3),
        adv=np.array([1e9, 1e9, 1e9]),
        objective_value=1.23,
        status=status,
    )


def test_export_writes_notional_per_symbol_skips_zero_weight(tmp_path):
    path = tmp_path / "target_portfolio.json"

    export_target_portfolio(_target(), book_notional=10_000_000.0, path=path)

    payload = json.loads(path.read_text())
    assert payload["rebuild_date"] == "2026-08-04"
    assert payload["status"] == "optimal"
    positions = {p["symbol"]: p["target_notional"] for p in payload["positions"]}
    assert positions == {"AAPL": 5_000_000.0, "MSFT": -3_000_000.0}
    assert "GOOG" not in positions  # zero weight, skipped


def test_export_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "dir" / "target_portfolio.json"

    export_target_portfolio(_target(), path=path)

    assert path.exists()


def test_export_passes_through_non_optimal_status(tmp_path):
    path = tmp_path / "target_portfolio.json"

    export_target_portfolio(_target(status="infeasible"), path=path)

    payload = json.loads(path.read_text())
    assert payload["status"] == "infeasible"
