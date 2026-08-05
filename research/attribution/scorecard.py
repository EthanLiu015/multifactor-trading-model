"""Book-level scorecard (DESIGN.md's analytics suite: Sharpe, IR, gross/net
exposure, max drawdown, hit rate, factor exposures vs limits).

v1 scope: Sharpe ratio, max drawdown, hit rate (all from BacktestResult's
net_returns/equity_curve, already built), plus gross/net exposure per date
(from BacktestStep's weights, already built). Deliberately NOT built here,
documented gaps not silent ones: per-factor paper-portfolio metrics (needs
a hypothetical single-factor-only portfolio, not just decompose_backtest's
aggregate factor contribution), realized transfer coefficient (meaningless
until the backtester models a real target-vs-held execution gap -- the
current single-shot fill assumption makes held == target trivially),
realized beta (needs research/portfolio/beta.py wired in).
"""

from __future__ import annotations

import dataclasses

import numpy as np

from research.backtest import BacktestResult, BacktestStep

TRADING_DAYS_PER_YEAR = 252


@dataclasses.dataclass
class BookScorecard:
    sharpe_ratio: float | None  # None if net_returns has <2 points or zero std
    max_drawdown: float  # most negative peak-to-trough drop, e.g. -0.15 = -15%
    hit_rate: float  # fraction of periods with net_return > 0
    gross_exposure: np.ndarray  # per usable step, sum(|w_i|)
    net_exposure: np.ndarray  # per usable step, sum(w_i)


def _sharpe_ratio(net_returns: np.ndarray) -> float | None:
    if len(net_returns) < 2:
        return None
    std = net_returns.std(ddof=1)
    if std == 0.0:
        return None
    return float(net_returns.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR))


def _max_drawdown(equity_curve: np.ndarray) -> float:
    if len(equity_curve) == 0:
        return 0.0
    running_max = np.maximum.accumulate(equity_curve)
    drawdowns = (equity_curve - running_max) / running_max
    return float(drawdowns.min())


def _hit_rate(net_returns: np.ndarray) -> float:
    if len(net_returns) == 0:
        return 0.0
    return float((net_returns > 0).sum() / len(net_returns))


def score_backtest(result: BacktestResult, steps: list[BacktestStep]) -> BookScorecard:
    """Book-level metrics from a completed backtest.

    ``steps`` is the same list passed to ``summarize_backtest`` to build
    ``result`` -- gross/net exposure need each step's per-security weight
    vector, which ``BacktestResult`` itself doesn't carry (it's a pure
    aggregation over scalars: gross_returns/costs/turnover, not weights).
    Filters to ``period_return is not None`` exactly like
    ``summarize_backtest`` does, so the exposure arrays stay aligned with
    ``result``'s own arrays -- a step this filter drops would otherwise
    silently misalign gross/net exposure against dates/net_returns.
    """
    usable = [step for step in steps if step.period_return is not None]
    gross_exposure = np.array([np.abs(step.weights).sum() for step in usable])
    net_exposure = np.array([step.weights.sum() for step in usable])

    return BookScorecard(
        sharpe_ratio=_sharpe_ratio(result.net_returns),
        max_drawdown=_max_drawdown(result.equity_curve),
        hit_rate=_hit_rate(result.net_returns),
        gross_exposure=gross_exposure,
        net_exposure=net_exposure,
    )
