"""Classic 12-1 month price momentum (Phase 2 signals + IC measurement).

Jegadeesh-Titman formulation: cumulative return over the trailing
``lookback_days`` trading days, EXCLUDING the most recent ``skip_days`` —
the skip-month avoids contaminating momentum with the separate short-term
reversal signal (research/signals/reversal.py), which is exactly the return
this window would otherwise double-count.

Computed from cumulative log-returns (sum, not repeated products) so the
skip/lookback window is a plain difference of two lagged values rather than
a fresh windowed product per row.
"""

from __future__ import annotations

import datetime as dt

import polars as pl

SIGNAL_SCHEMA = {
    "effective_date": pl.Date,
    "security_id": pl.String,
    "signal_value": pl.Float64,
}


def _empty_signal() -> pl.DataFrame:
    return pl.DataFrame(schema=SIGNAL_SCHEMA)


def compute_momentum(
    bars: pl.LazyFrame,
    rebuild_date: dt.date,
    *,
    lookback_days: int = 252,
    skip_days: int = 21,
) -> pl.DataFrame:
    """Momentum value per security as of ``rebuild_date``.

    ``bars`` must already be revision-deduped (i.e. from
    :meth:`PITStore.asof`); this only looks backward in ``effective_date``
    from ``rebuild_date``. A security needs at least ``lookback_days + 1``
    trailing trading-day rows to get a value — shorter histories are simply
    absent from the result, never a forced/noisy partial-window momentum.
    """
    window = (
        bars.filter(pl.col("effective_date") <= rebuild_date)
        .sort(["security_id", "effective_date"])
        .with_columns(pl.col("ret").log1p().alias("log_ret"))
        .with_columns(
            pl.col("log_ret").cum_sum().over("security_id").alias("cum_log_ret")
        )
    )

    result = (
        window.group_by("security_id")
        .agg(
            pl.len().alias("n_obs"),
            pl.col("cum_log_ret")
            .sort_by("effective_date")
            .shift(skip_days)
            .last()
            .alias("cum_skip"),
            pl.col("cum_log_ret")
            .sort_by("effective_date")
            .shift(lookback_days)
            .last()
            .alias("cum_lookback"),
        )
        .filter(
            (pl.col("n_obs") >= lookback_days + 1)
            & pl.col("cum_skip").is_not_null()
            & pl.col("cum_lookback").is_not_null()
        )
        .select(
            pl.lit(rebuild_date, dtype=pl.Date).alias("effective_date"),
            pl.col("security_id"),
            ((pl.col("cum_skip") - pl.col("cum_lookback")).exp() - 1.0).alias(
                "signal_value"
            ),
        )
        .collect()
    )
    return result if result.height else _empty_signal()
