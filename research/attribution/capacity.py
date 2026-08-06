"""Capacity analysis (DESIGN.md analytics suite): "at what AUM does modeled
impact eat the alpha? Re-run quarterly; the number recruiters ask for."

Re-runs the full backtest pipeline at several book_notional (AUM) levels,
holding everything else fixed. No new modeling needed: run_backtest already
threads book_notional through BOTH the optimizer's ADV-relative position
caps (constraints.py: |w_i| <= adv_days*adv_i/book_notional -- the same
dollar cap becomes a tighter WEIGHT cap as AUM grows) and the cost model
(costs.py: impact cost grows faster than linear in trade $ size). Both
effects any real capacity curve needs are already captured by existing,
already-tested machinery -- this module is a thin sweep over book_notional,
not a new algorithm.

Expensive: re-runs the full per-date risk-model + QP-solve pipeline once
per book_notional level. Not for casual/automated use -- DESIGN.md itself
says "re-run quarterly."
"""

from __future__ import annotations

import dataclasses
import datetime as dt

from research.attribution.scorecard import score_backtest
from research.backtest.result import summarize_backtest
from research.backtest.simulate import run_backtest
from research.data import PITStore


@dataclasses.dataclass
class CapacityPoint:
    book_notional: float
    sharpe_ratio: float | None
    total_net_return: float  # cumulative net return over the run; 0.0 if no usable steps


def capacity_analysis(
    store: PITStore,
    start_date: dt.date,
    end_date: dt.date,
    book_notional_values: list[float],
    **run_backtest_kwargs,
) -> list[CapacityPoint]:
    """Sharpe ratio and cumulative net return at each AUM level -- the
    capacity curve. The AUM where sharpe_ratio crosses zero (or drops below
    whatever bar the caller cares about) is the answer to "how big can this
    book get before costs eat the alpha."

    ``book_notional_values`` should be given smallest-to-largest, but this
    function doesn't require or enforce an order -- the caller reads the
    curve, this just computes each point.
    """
    # score_backtest's own store.asof() call needs the SAME knowledge_ts
    # run_backtest used -- letting it default independently to "now" would
    # still be point-in-time-safe (no future leakage), but would silently
    # diverge from whatever vintage run_backtest_kwargs actually pinned.
    knowledge_ts = run_backtest_kwargs.get("knowledge_ts")

    points = []
    for book_notional in book_notional_values:
        steps = run_backtest(
            store, start_date, end_date, book_notional=book_notional, **run_backtest_kwargs
        )
        result = summarize_backtest(steps, book_notional=book_notional)
        scorecard = score_backtest(result, steps, store, knowledge_ts=knowledge_ts)
        total_net_return = (
            float(result.equity_curve[-1] - 1.0) if len(result.equity_curve) else 0.0
        )
        points.append(CapacityPoint(book_notional, scorecard.sharpe_ratio, total_net_return))
    return points
