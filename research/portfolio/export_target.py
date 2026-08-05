"""Writes a TargetPortfolio to common/target_portfolio.json -- the file
contract between the Python research side and the C++ execution scheduler
(DESIGN.md line 212: "target portfolio file/IPC format").

Writes target DOLLAR NOTIONAL per symbol, not shares or weights -- the
execution scheduler converts notional to shares using its own live price,
since research-side prices (yfinance/CRSP, as of the rebalance date) can
differ from the live intraday price by execution time.

``security_ids`` on TargetPortfolio are already ticker symbols (yfinance's
native security_id, confirmed by reading research/risk/exposures.py's
membership join -- not security_master's internal_id, which is a separate,
not-yet-integrated identifier system). No security_master resolution
needed here.

Non-optimal ``status`` (e.g. "infeasible") is written through as-is, not
gated here -- the execution scheduler is the one that decides whether to
trade off the file, matching TargetPortfolio's own "callers must check
status" convention.
"""

from __future__ import annotations

import json
from pathlib import Path

from research.portfolio.model import TargetPortfolio

DEFAULT_PATH = Path("common/target_portfolio.json")


def export_target_portfolio(
    target: TargetPortfolio,
    book_notional: float = 10_000_000.0,
    path: Path = DEFAULT_PATH,
) -> Path:
    """Writes ``target.weights * book_notional`` per symbol to ``path`` as JSON.

    Zero-weight positions are skipped -- nothing for the execution
    scheduler to do there, and it keeps the file focused on names that
    actually need a trade.
    """
    positions = [
        {"symbol": symbol, "target_notional": float(weight) * book_notional}
        for symbol, weight in zip(target.security_ids, target.weights)
        if weight != 0.0
    ]
    payload = {
        "rebuild_date": target.rebuild_date.isoformat(),
        "status": target.status,
        "positions": positions,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return path
