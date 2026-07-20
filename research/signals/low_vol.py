"""Low-volatility signal (Phase 2 signals + IC measurement).

Trailing ``window_days``-trading-day standard deviation of daily returns,
stored RAW (not sign-flipped or negated). The low-volatility anomaly
predicts low-vol names outperform (negative IC expected); same convention
as research/signals/reversal.py — report the plain empirical quantity and
let IC measurement reveal the sign rather than assuming it up front.

Uses the same trailing-window-of-dates technique as research/universe.py's
build_snapshot, rather than momentum/reversal's cumulative-log-return
shift — a plain windowed stdev doesn't need the cumulative-sum trick.
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


def compute_low_vol(
    bars: pl.LazyFrame,
    rebuild_date: dt.date,
    *,
    window_days: int = 252,
    min_obs: int | None = None,
) -> pl.DataFrame:
    """Trailing return-volatility per security, as of ``rebuild_date``.

    ``bars`` must already be revision-deduped (i.e. from
    :meth:`PITStore.asof`); this only looks backward in ``effective_date``
    from ``rebuild_date``. ``min_obs`` (default: 2/3 of ``window_days``,
    matching universe.py's own default) is the minimum non-null ``ret``
    count required — securities below it are simply absent from the result.
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
        return _empty_signal()

    window = bars.filter(
        pl.col("effective_date").is_between(window_dates.min(), rebuild_date)
    )

    result = (
        window.group_by("security_id")
        .agg(
            pl.col("ret").count().alias("n_obs"),
            pl.col("ret").std().alias("vol"),
        )
        .filter((pl.col("n_obs") >= min_obs) & pl.col("vol").is_not_null())
        .select(
            pl.lit(rebuild_date, dtype=pl.Date).alias("effective_date"),
            pl.col("security_id"),
            pl.col("vol").alias("signal_value"),
        )
        .collect()
    )
    return result if result.height else _empty_signal()
