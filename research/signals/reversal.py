"""Short-term reversal signal (Phase 2 signals + IC measurement).

Trailing ``window_days``-trading-day cumulative return, stored RAW — not
sign-flipped. Reversal theory predicts past losers outperform (negative
IC); rather than bake that assumed sign into the signal itself, this module
reports the plain empirical trailing return and lets IC measurement
(research/alpha/ic.py) reveal whether the correlation is actually negative.
Same convention used by research/signals/low_vol.py.
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


def compute_reversal(
    bars: pl.LazyFrame,
    rebuild_date: dt.date,
    *,
    window_days: int = 21,
) -> pl.DataFrame:
    """Trailing ``window_days`` cumulative return per security, as of ``rebuild_date``.

    ``bars`` must already be revision-deduped (i.e. from
    :meth:`PITStore.asof`); this only looks backward in ``effective_date``
    from ``rebuild_date``. A security needs at least ``window_days + 1``
    trailing trading-day rows to get a value.
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
            pl.col("cum_log_ret").sort_by("effective_date").last().alias("cum_end"),
            pl.col("cum_log_ret")
            .sort_by("effective_date")
            .shift(window_days)
            .last()
            .alias("cum_start"),
        )
        .filter(
            (pl.col("n_obs") >= window_days + 1)
            & pl.col("cum_end").is_not_null()
            & pl.col("cum_start").is_not_null()
        )
        .select(
            pl.lit(rebuild_date, dtype=pl.Date).alias("effective_date"),
            pl.col("security_id"),
            ((pl.col("cum_end") - pl.col("cum_start")).exp() - 1.0).alias(
                "signal_value"
            ),
        )
        .collect()
    )
    return result if result.height else _empty_signal()
