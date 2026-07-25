"""Block 5c: backtest result/equity-curve summary.

Pure aggregation over BacktestStep, mirroring research/alpha/ic.py's
IcSummary pattern for empty-input handling: no data isn't an error
here, it's a degenerate (empty) result, not None. Unlike
build_target_portfolio/build_risk_model, this function never fails to
build -- it just has nothing to summarize when given no steps.
"""

from __future__ import annotations

import dataclasses
import datetime as dt

import numpy as np

from research.backtest.simulate import BacktestStep


@dataclasses.dataclass
class BacktestResult:
    dates: list[dt.date]
    gross_returns: np.ndarray  # period_return per included step
    costs: np.ndarray  # $ total cost per included step
    net_returns: np.ndarray  # gross_return - cost/book_notional
    equity_curve: np.ndarray  # cumulative product of (1+net_returns), starts at 1.0
    turnover: np.ndarray  # L1 |delta_w| per included step


def summarize_backtest(
    steps: list[BacktestStep], book_notional: float = 10_000_000.0
) -> BacktestResult:
    """Equity curve + cost/turnover series over ``steps``.

    Only steps with a ``period_return`` are included -- the final step
    from :func:`research.backtest.simulate.run_backtest` never has one
    (nothing to hold until), so it contributes cost/turnover to no
    return period and is dropped here.
    """
    usable = [s for s in steps if s.period_return is not None]

    dates = [s.rebuild_date for s in usable]
    gross_returns = np.array([s.period_return for s in usable])
    costs = np.array([s.trade_cost.sum() for s in usable])
    turnover = np.array([s.turnover for s in usable])
    net_returns = gross_returns - costs / book_notional
    equity_curve = np.cumprod(1.0 + net_returns)

    return BacktestResult(
        dates=dates,
        gross_returns=gross_returns,
        costs=costs,
        net_returns=net_returns,
        equity_curve=equity_curve,
        turnover=turnover,
    )
