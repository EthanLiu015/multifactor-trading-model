"""IC measurement — the alpha research engine's edge-validation step (Block 2).

Two things live here that intentionally do NOT live in research/signals/:

1. ``compute_forward_returns`` looks FORWARD from a rebalance date. Every
   signal in research/signals/ only looks backward from ``rebuild_date`` —
   that asymmetry is the actual point-in-time boundary this project is built
   around (see research/data/store.py's module docstring). Forward returns
   are a research/backtest LABEL (what actually happened next), never a
   live trading input, which is why the forward-looking read lives in its
   own module instead of being a flag on a signal function.
2. ``compute_ic`` / ``build_ic_series`` / ``IcSummary``: per DESIGN.md Block
   2, IC = rank correlation of a signal's value against the forward return
   it's trying to predict, measured per rebalance date and then summarized
   (mean IC, IC t-stat) to judge whether a signal's edge is real or noise.

Every rebalance date here comes from ``lake/universe_monthly`` — a security
only counts on dates it was actually a member (point-in-time), matching the
same discipline research/universe.py already enforces for membership.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import time
from typing import Callable

import polars as pl

from research.data import PITStore
from research.signals import SIGNAL_REGISTRY

BARS_DATASET = "yfinance_daily"
UNIVERSE_DATASET = "universe_monthly"

IC_SCHEMA = {"effective_date": pl.Date, "ic": pl.Float64}
FORWARD_RETURNS_SCHEMA = {
    "effective_date": pl.Date,
    "security_id": pl.String,
    "forward_return": pl.Float64,
}


def _empty_forward_returns() -> pl.DataFrame:
    return pl.DataFrame(schema=FORWARD_RETURNS_SCHEMA)


@dataclasses.dataclass
class IcSummary:
    n: int
    mean_ic: float | None
    ic_std: float | None
    ic_tstat: float | None


def compute_forward_returns(
    bars: pl.LazyFrame,
    rebuild_date: dt.date,
    *,
    horizon_days: int = 21,
) -> pl.DataFrame:
    """Forward ``horizon_days``-trading-day return per security, from ``rebuild_date``.

    ``bars`` here is not filtered to <= rebuild_date like every signal in
    research/signals/ — this function deliberately reads ahead in time.
    Never call this from point-in-time signal or decision code; it exists
    to LABEL a rebalance date with what happened next, for research
    validation only. Bounded to a ``horizon_days``-wide forward date window
    (same date-window technique as research/signals/low_vol.py, just
    forward instead of backward) rather than scanning full history —
    computing this over 15 years of history per call measured at ~3.3s vs
    ~0.1-0.3s bounded (2026-07-16, see docs/METRICS.md).
    """
    window_dates = (
        bars.select(pl.col("effective_date").unique())
        .filter(pl.col("effective_date") >= rebuild_date)
        .sort("effective_date")
        .head(horizon_days + 1)
        .collect()["effective_date"]
    )
    if len(window_dates) < horizon_days + 1:
        return _empty_forward_returns()

    window = bars.filter(
        pl.col("effective_date").is_between(rebuild_date, window_dates.max())
    )
    full = (
        window.sort(["security_id", "effective_date"])
        .with_columns(pl.col("ret").log1p().alias("log_ret"))
        .with_columns(
            pl.col("log_ret").cum_sum().over("security_id").alias("cum_log_ret")
        )
        .with_columns(
            pl.col("cum_log_ret")
            .shift(-horizon_days)
            .over("security_id")
            .alias("cum_log_ret_fwd")
        )
    )
    result = (
        full.filter(pl.col("effective_date") == rebuild_date)
        .filter(pl.col("cum_log_ret_fwd").is_not_null())
        .select(
            pl.lit(rebuild_date, dtype=pl.Date).alias("effective_date"),
            pl.col("security_id"),
            ((pl.col("cum_log_ret_fwd") - pl.col("cum_log_ret")).exp() - 1.0).alias(
                "forward_return"
            ),
        )
        .collect()
    )
    return result


def compute_ic(signal_df: pl.DataFrame, forward_returns_df: pl.DataFrame) -> float | None:
    """Spearman rank correlation between signal value and forward return.

    ``None`` if fewer than 2 securities have both a signal value and a
    forward return on this date — correlation is undefined, not zero.
    """
    joined = signal_df.join(
        forward_returns_df, on=["effective_date", "security_id"], how="inner"
    )
    if joined.height < 2:
        return None
    value = joined.select(
        pl.corr(pl.col("signal_value"), pl.col("forward_return"), method="spearman")
    ).item()
    return value


def _ic_for_date(
    bars: pl.LazyFrame,
    members: list[str],
    d: dt.date,
    signal_fns: dict[str, Callable[..., pl.DataFrame]],
    horizon_days: int,
) -> dict[str, float | None]:
    """One IC value per signal, for a single rebalance date.

    Extracted from build_ic_series's loop body (Block 6d, 2026-07-27) so the
    same per-date unit of work can be distributed across Spark executors
    (research/alpha/spark_ic.py) without duplicating this logic — the local
    loop and the Spark path both call this one function.
    """
    forward = compute_forward_returns(bars, d, horizon_days=horizon_days).filter(
        pl.col("security_id").is_in(members)
    )
    result: dict[str, float | None] = {}
    for name, fn in signal_fns.items():
        signal = fn(bars, d).filter(pl.col("security_id").is_in(members))
        result[name] = compute_ic(signal, forward)
    return result


def build_ic_series(
    store: PITStore,
    signal_fns: dict[str, Callable[..., pl.DataFrame]],
    start_year: int,
    end_year: int,
    *,
    horizon_days: int = 21,
    knowledge_ts: dt.datetime | None = None,
) -> dict[str, pl.DataFrame]:
    """One IC value per rebalance date in ``[start_year, end_year]``, per signal.

    Rebalance dates and membership come from ``lake/universe_monthly``
    (point-in-time) — a security's signal/forward-return only counts on
    dates it was actually a universe member. Forward returns are computed
    ONCE per date and reused across every signal in ``signal_fns`` — they
    don't depend on the signal, and computing them per-signal was measured
    at 3x the cost for no benefit (2026-07-16, docs/METRICS.md).
    """
    if knowledge_ts is None:
        knowledge_ts = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

    bars = store.asof(BARS_DATASET, knowledge_ts, keys=["security_id"])
    universe = store.asof(UNIVERSE_DATASET, knowledge_ts, keys=["security_id"])

    rebuild_dates = sorted(
        d
        for d in universe.select(pl.col("effective_date").unique()).collect()[
            "effective_date"
        ]
        if start_year <= d.year <= end_year
    )

    rows: dict[str, list[dict]] = {name: [] for name in signal_fns}
    for d in rebuild_dates:
        members = (
            universe.filter(pl.col("effective_date") == d)
            .select("security_id")
            .collect()["security_id"]
            .to_list()
        )
        ic_by_signal = _ic_for_date(bars, members, d, signal_fns, horizon_days)
        for name, ic in ic_by_signal.items():
            rows[name].append({"effective_date": d, "ic": ic})

    return {
        name: pl.DataFrame(r, schema=IC_SCHEMA) if r else pl.DataFrame(schema=IC_SCHEMA)
        for name, r in rows.items()
    }


def ic_summary(ic_series: pl.DataFrame) -> IcSummary:
    """Mean IC, IC std, IC t-stat — is this signal's edge real or noise."""
    values = ic_series.drop_nulls("ic")["ic"]
    n = len(values)
    if n == 0:
        return IcSummary(n=0, mean_ic=None, ic_std=None, ic_tstat=None)
    mean_ic = values.mean()
    ic_std = values.std() if n > 1 else None
    ic_tstat = mean_ic / (ic_std / (n**0.5)) if ic_std else None
    return IcSummary(n=n, mean_ic=mean_ic, ic_std=ic_std, ic_tstat=ic_tstat)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute IC per signal in SIGNAL_REGISTRY over universe_monthly rebalance dates"
    )
    parser.add_argument("--start", type=int, default=2011)
    parser.add_argument("--end", type=int, default=dt.date.today().year)
    parser.add_argument("--lake", default="lake")
    parser.add_argument("--horizon", type=int, default=21, help="forward-return trading days")
    args = parser.parse_args(argv)

    store = PITStore(args.lake)
    knowledge_ts = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

    t0 = time.perf_counter()
    series_by_signal = build_ic_series(
        store,
        SIGNAL_REGISTRY,
        args.start,
        args.end,
        horizon_days=args.horizon,
        knowledge_ts=knowledge_ts,
    )
    elapsed = time.perf_counter() - t0

    for name, series in series_by_signal.items():
        summary = ic_summary(series)
        print(
            f"{name}: n={summary.n} mean_ic={summary.mean_ic} "
            f"ic_std={summary.ic_std} ic_tstat={summary.ic_tstat}"
        )
    print(f"all signals computed in {elapsed:.1f}s — record in docs/METRICS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
