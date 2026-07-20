"""Specific (idiosyncratic) variance D (Block 3 risk model).

Diagonal of Σ = B·F·Bᵀ + D — one EWMA variance per security, from that
security's specific-return time series (the residuals research/risk/
regression.py produces, stacked across rebalance dates). Same half-life
convention as factor_covariance.py, but uses Polars' native ``ewm_var``
directly (no need for the numpy reweighting trick factor_covariance.py
needed — that was specifically to feed sklearn's LedoitWolf, which has no
sample-weight support; plain per-security EWMA variance doesn't need it).
"""

from __future__ import annotations

import polars as pl

SPECIFIC_VARIANCE_SCHEMA = {"security_id": pl.String, "specific_variance": pl.Float64}


def build_specific_variance(
    specific_return_history: pl.DataFrame,
    halflife_days: float = 63.0,
) -> pl.DataFrame:
    """EWMA specific variance per security.

    ``specific_return_history``: [effective_date, security_id,
    specific_return], typically many rebalance dates' worth of regression
    residuals stacked. A security needs at least 2 observations to get a
    variance; securities with fewer are absent from the result — no
    fabricated placeholder.
    """
    if specific_return_history.is_empty():
        return pl.DataFrame(schema=SPECIFIC_VARIANCE_SCHEMA)

    return (
        specific_return_history.group_by("security_id")
        .agg(
            pl.col("specific_return")
            .sort_by("effective_date")
            .ewm_var(half_life=halflife_days)
            .last()
            .alias("specific_variance"),
            pl.len().alias("n_obs"),
        )
        .filter(pl.col("n_obs") >= 2)
        .select("security_id", "specific_variance")
    )
