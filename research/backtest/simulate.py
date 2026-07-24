"""Block 5b: walk-forward day-loop orchestrator (DESIGN.md's Backtester).

The sole sanctioned Python loop-over-dates in this codebase (coding
conventions doc's "no Python loops over stocks or dates -- the
backtester's day loop will be the sole sanctioned exception") --
everywhere else this house bans looping over stocks/dates in favor of
column expressions.

Threads ``w_prev`` forward across rebalance dates by calling
``build_target_portfolio`` (block 4d) once per date. A date where the
optimizer can't be built (insufficient history) is skipped -- ``w_prev``
carries over unchanged, matching what a real system would do: a failed
rebalance leaves the book as-is, it doesn't liquidate it.

Portfolio return over a holding period is the simplified
sum(w_i * period_return_i) -- ignores intra-period compounding/
rebalancing drift (documented approximation, chosen 2026-07-23, same
posture as this project's other documented simplifications e.g.
research/risk/model.py's reference-sector gap). Names missing data
mid-period (delisted, no bars) are dropped from the weighted sum --
consistent with the yfinance backfill's already-documented
survivorship-bias gap (handoff.md limitation 5), not a new one.
"""

from __future__ import annotations

import dataclasses
import datetime as dt

import numpy as np
import polars as pl

from research.backtest.costs import trade_cost
from research.data import PITStore
from research.portfolio.model import build_target_portfolio
from research.risk.model import BARS_DATASET, UNIVERSE_DATASET

HOLDING_RETURN_SCHEMA = {"security_id": pl.String, "period_return": pl.Float64}


def _empty_holding_returns() -> pl.DataFrame:
    return pl.DataFrame(schema=HOLDING_RETURN_SCHEMA)


def _holding_period_return(
    bars: pl.LazyFrame, start_date: dt.date, end_date: dt.date, security_ids: list[str]
) -> pl.DataFrame:
    """Cumulative return per security over ``(start_date, end_date]``.

    Excludes ``start_date``'s own return (you enter at that day's close,
    so you don't earn that day's move) and includes ``end_date``'s
    (earned while holding). ``[security_id, period_return]``, only for
    securities with a complete run of bars across the window.
    """
    window = bars.filter(
        pl.col("security_id").is_in(security_ids)
        & (pl.col("effective_date") > start_date)
        & (pl.col("effective_date") <= end_date)
        & pl.col("ret").is_not_null()
    )
    result = (
        window.group_by("security_id")
        .agg(((pl.col("ret") + 1.0).product() - 1.0).alias("period_return"))
        .collect()
    )
    return result if not result.is_empty() else _empty_holding_returns()


@dataclasses.dataclass
class BacktestStep:
    rebuild_date: dt.date
    security_ids: list[str]
    weights: np.ndarray
    status: str
    trade_cost: np.ndarray  # $ per security, this rebalance's trade
    period_return: float | None  # portfolio return over (this date, next date]; None on the final step


def run_backtest(
    store: PITStore,
    start_date: dt.date,
    end_date: dt.date,
    *,
    lookback_years: int = 3,
    shrink: float = 0.5,
    cap: float = 3.0,
    risk_aversion: float = 5.0,
    cost_penalty: float = 10.0,
    book_notional: float = 10_000_000.0,
    knowledge_ts: dt.datetime | None = None,
    cost_kwargs: dict | None = None,
    **constraint_kwargs,
) -> list[BacktestStep]:
    """Walk-forward backtest over ``[start_date, end_date]``.

    ``cost_kwargs`` forwarded to :func:`research.backtest.costs.trade_cost`;
    ``constraint_kwargs`` forwarded through :func:`build_target_portfolio`
    to :func:`research.portfolio.constraints.build_constraints`.
    """
    if knowledge_ts is None:
        knowledge_ts = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    cost_kwargs = cost_kwargs or {}

    universe = store.asof(UNIVERSE_DATASET, knowledge_ts, keys=["security_id"])
    rebuild_dates = sorted(
        d
        for d in universe.select(pl.col("effective_date").unique()).collect()["effective_date"]
        if start_date <= d <= end_date
    )
    bars = store.asof(BARS_DATASET, knowledge_ts, keys=["security_id"])

    steps: list[BacktestStep] = []
    w_prev: pl.DataFrame | None = None
    for i, date in enumerate(rebuild_dates):
        target = build_target_portfolio(
            store,
            date,
            w_prev,
            lookback_years=lookback_years,
            shrink=shrink,
            cap=cap,
            risk_aversion=risk_aversion,
            cost_penalty=cost_penalty,
            book_notional=book_notional,
            knowledge_ts=knowledge_ts,
            **constraint_kwargs,
        )
        if target is None:
            continue

        cost = trade_cost(target.weights - target.w_prev, target.adv, book_notional, **cost_kwargs)

        period_return = None
        next_date = rebuild_dates[i + 1] if i + 1 < len(rebuild_dates) else None
        if next_date is not None:
            holding = _holding_period_return(bars, date, next_date, target.security_ids)
            aligned = pl.DataFrame(
                {"security_id": target.security_ids, "weight": target.weights}
            ).join(holding, on="security_id", how="inner")
            if not aligned.is_empty():
                period_return = float(
                    (aligned["weight"] * aligned["period_return"]).sum()
                )

        steps.append(
            BacktestStep(
                rebuild_date=date,
                security_ids=target.security_ids,
                weights=target.weights,
                status=target.status,
                trade_cost=cost,
                period_return=period_return,
            )
        )
        w_prev = pl.DataFrame({"security_id": target.security_ids, "weight": target.weights})

    return steps
