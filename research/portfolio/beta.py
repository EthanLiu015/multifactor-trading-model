"""Per-stock market beta (Block 4b input): rolling single-factor beta.

Needed for the optimizer's beta-neutral constraint (β·w = 0, DESIGN.md
Block 4) — the risk model's own "market" exposure (research/risk/
exposures.py) is a Barra-style constant (=1.0 for every stock), not a
per-stock CAPM beta; β·w = 0 against a constant collapses to dollar-
neutral and buys no real market-neutrality. This module fills that gap.

Market proxy = equal-weighted average daily return across the SAME
security set the optimizer is already using (its risk-model-surviving
cross-section), not a separate market index — no market-cap data exists
yet (deferred to CRSP) so cap-weighting isn't possible, and there's no
free market-index series wired into the lake. Documented approximation,
not the "real" market portfolio.
"""

from __future__ import annotations

import datetime as dt

import polars as pl

BETA_SCHEMA = {"security_id": pl.String, "beta": pl.Float64}


def _empty_beta() -> pl.DataFrame:
    return pl.DataFrame(schema=BETA_SCHEMA)


def compute_market_beta(
    bars: pl.LazyFrame,
    rebuild_date: dt.date,
    security_ids: list[str],
    *,
    window_days: int = 252,
    min_obs: int | None = None,
) -> pl.DataFrame:
    """Trailing single-factor beta per security, as of ``rebuild_date``.

    ``security_ids`` both defines the market proxy (equal-weighted mean
    return across this set, per date) and the securities beta is computed
    for. ``min_obs`` (default: 2/3 of ``window_days``, matching
    research/signals/low_vol.py's own default) is the minimum
    overlapping-observation count required — securities below it are
    simply absent from the result, never a forced/noisy partial beta.
    """
    if min_obs is None:
        min_obs = max(2, (2 * window_days) // 3)

    window_dates = (
        bars.select(pl.col("effective_date").unique())
        .filter(pl.col("effective_date") <= rebuild_date)
        .sort("effective_date", descending=True)
        .head(window_days)
        .collect()["effective_date"]
    )
    if len(window_dates) < min_obs:
        return _empty_beta()

    window = bars.filter(
        pl.col("effective_date").is_between(window_dates.min(), rebuild_date)
        & pl.col("security_id").is_in(security_ids)
    ).collect()

    mkt = window.group_by("effective_date").agg(pl.col("ret").mean().alias("mkt_ret"))
    joined = window.join(mkt, on="effective_date", how="inner")

    result = (
        joined.group_by("security_id")
        .agg(
            pl.len().alias("n_obs"),
            (pl.cov(pl.col("ret"), pl.col("mkt_ret")) / pl.col("mkt_ret").var()).alias(
                "beta"
            ),
        )
        .filter((pl.col("n_obs") >= min_obs) & pl.col("beta").is_not_null())
        .select("security_id", "beta")
    )
    return result if result.height else _empty_beta()
