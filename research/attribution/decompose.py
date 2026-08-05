"""Attribution (DESIGN.md Block 6): decompose realized backtest returns into
factor-bet contribution vs specific (stock-picking) contribution.

Reuses the SAME per-date exposures/factor-returns/specific-returns
build_risk_model already computes internally (via
research.risk.model.build_factor_return_history, widened 2026-08-05 to also
expose the exposure history it discarded before) -- not a second,
independent regression. Fully vectorized: no Python loop over dates here:
build_factor_return_history already contains the sole per-date loop this
computation needs, everything downstream is Polars joins/group-bys.

Runs on backtest output first (DESIGN.md: "same metric code runs on
backtest output and live data" -- backtest is what exists right now, no
live loop running yet).
"""

from __future__ import annotations

import dataclasses
import datetime as dt

import numpy as np
import polars as pl

from research.backtest import BacktestStep
from research.data import PITStore
from research.risk.model import build_factor_return_history


@dataclasses.dataclass
class AttributionResult:
    dates: list[dt.date]
    factor_contribution: np.ndarray  # per date: portfolio factor exposure dot factor returns
    specific_contribution: np.ndarray  # per date: sum(weight * specific_return)
    total: np.ndarray  # factor_contribution + specific_contribution


def _empty_result() -> AttributionResult:
    empty = np.array([])
    return AttributionResult(
        dates=[], factor_contribution=empty, specific_contribution=empty, total=empty
    )


def decompose_backtest(
    steps: list[BacktestStep],
    store: PITStore,
    *,
    knowledge_ts: dt.datetime | None = None,
) -> AttributionResult:
    """Per rebalance date: how much of that date's target weights came from
    factor bets vs specific (idiosyncratic) return.

    Steps with ``status != "optimal"`` are excluded -- their weights aren't
    real trades, same convention as ``build_target_portfolio``'s own
    "don't trust weights unless status is optimal". A date with no
    matching factor/specific-return data (e.g. outside the covariance
    history's usable range) contributes 0.0 for both, not a gap in the
    output -- every step's date is represented.
    """
    if not steps:
        return _empty_result()

    weights_rows = [
        {"effective_date": step.rebuild_date, "security_id": security_id, "weight": float(weight)}
        for step in steps
        if step.status == "optimal"
        for security_id, weight in zip(step.security_ids, step.weights)
    ]
    weights_long = (
        pl.DataFrame(weights_rows)
        if weights_rows
        else pl.DataFrame(
            schema={"effective_date": pl.Date, "security_id": pl.String, "weight": pl.Float64}
        )
    )

    all_dates = sorted({step.rebuild_date for step in steps})
    factor_history, specific_history, exposure_history = build_factor_return_history(
        store, all_dates[0].year, all_dates[-1].year, knowledge_ts=knowledge_ts
    )
    factor_cols = [c for c in factor_history.columns if c != "effective_date"]

    specific_contribution = (
        weights_long.join(specific_history, on=["effective_date", "security_id"], how="inner")
        .with_columns((pl.col("weight") * pl.col("specific_return")).alias("contrib"))
        .group_by("effective_date")
        .agg(pl.col("contrib").sum().alias("specific_contribution"))
    )

    exposure_long = (
        exposure_history.unpivot(
            on=factor_cols,
            index=["effective_date", "security_id"],
            variable_name="factor",
            value_name="exposure",
        )
        .drop_nulls("exposure")
    )
    portfolio_exposure = (
        weights_long.join(exposure_long, on=["effective_date", "security_id"], how="inner")
        .with_columns((pl.col("weight") * pl.col("exposure")).alias("weighted_exposure"))
        .group_by(["effective_date", "factor"])
        .agg(pl.col("weighted_exposure").sum())
    )

    factor_returns_long = (
        factor_history.unpivot(
            on=factor_cols, index="effective_date", variable_name="factor",
            value_name="factor_return",
        )
        .drop_nulls("factor_return")
    )
    factor_contribution = (
        portfolio_exposure.join(factor_returns_long, on=["effective_date", "factor"], how="inner")
        .with_columns((pl.col("weighted_exposure") * pl.col("factor_return")).alias("contrib"))
        .group_by("effective_date")
        .agg(pl.col("contrib").sum().alias("factor_contribution"))
    )

    result = (
        pl.DataFrame({"effective_date": all_dates})
        .join(factor_contribution, on="effective_date", how="left")
        .join(specific_contribution, on="effective_date", how="left")
        .fill_null(0.0)
        .sort("effective_date")
    )

    return AttributionResult(
        dates=result["effective_date"].to_list(),
        factor_contribution=result["factor_contribution"].to_numpy(),
        specific_contribution=result["specific_contribution"].to_numpy(),
        total=(result["factor_contribution"] + result["specific_contribution"]).to_numpy(),
    )
