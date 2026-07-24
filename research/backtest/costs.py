"""Block 5a: research-side trading cost model (DESIGN.md Block 5's cost
components, proxied here since Block 5/C++ hasn't built its own yet).

Covers spread + market impact + fees only. Short borrow costs and
financing costs are DEFERRED -- same free-data gap as block 4b's
borrow-availability filter (no free borrow-rate source exists in the
lake). Backtest P&L will therefore overstate short-book profitability
until that data exists; documented, not hidden.
"""

from __future__ import annotations

import numpy as np


def trade_cost(
    delta_w: np.ndarray,
    adv: np.ndarray,
    book_notional: float,
    *,
    half_spread_bps: float = 5.0,
    impact_coef: float = 10.0,
    fee_bps: float = 1.0,
) -> np.ndarray:
    """Per-security $ trading cost for one rebalance's ``delta_w = w - w_prev``.

    ``adv`` row-aligned to ``delta_w`` ($ median daily dollar volume).
    Cost (bps) = ``half_spread_bps + impact_coef * sqrt(notional/adv) +
    fee_bps`` -- square-root impact per DESIGN.md's "square-root impact
    model as starting point." Returns a per-security array (not a
    scalar total) so callers can attribute cost by name, matching
    research/portfolio/inputs.py's "return full arrays, let the caller
    aggregate" convention. All three bps constants are placeholders,
    pending real calibration (no backtester history exists yet to
    calibrate against).
    """
    notional = np.abs(delta_w) * book_notional
    impact_bps = impact_coef * np.sqrt(notional / adv)
    cost_bps = half_spread_bps + impact_bps + fee_bps
    return notional * cost_bps / 1e4
