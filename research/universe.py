"""Point-in-time monthly universe builder (part 3).

Derives the tradeable universe from daily bars in the lake: on the last
trading day of each month, rank securities by trailing ``adv_window``-day
median dollar volume, apply price and coverage filters, keep the top
``top_n``. Each snapshot is stored under dataset ``universe_monthly`` with
the rebuild date as ``effective_date``, so backtests read membership via
:meth:`PITStore.asof` and can never see a universe built from future data.

Market-cap filter (DESIGN.md: > $2B) is deferred until CRSP provides
shares outstanding — yfinance bars carry none (decision 2026-07-13).

The trailing window reaches only backward from each rebuild date, so
market-time look-ahead is impossible by construction. The ``knowledge_ts``
cutoff additionally pins which *revisions* of the bars are visible; for
the initial single-batch yfinance backfill it is inert, but it makes
universe rebuilds reproducible once restatements or CRSP reloads land.
"""

from __future__ import annotations

import argparse
import datetime as dt
import time

import polars as pl

from research.data import PITStore

BARS_DATASET = "yfinance_daily"
UNIVERSE_DATASET = "universe_monthly"

SNAPSHOT_SCHEMA = {
    "effective_date": pl.Date,
    "security_id": pl.String,
    "rank": pl.UInt32,
    "median_dollar_volume": pl.Float64,
    "last_close": pl.Float64,
    "days_traded": pl.UInt32,
}


def month_end_trading_days(bars: pl.LazyFrame) -> list[dt.date]:
    """Last observed trading date of each calendar month in ``bars``."""
    out = (
        bars.select(pl.col("effective_date").unique())
        .group_by(
            pl.col("effective_date").dt.year().alias("y"),
            pl.col("effective_date").dt.month().alias("m"),
        )
        .agg(pl.col("effective_date").max().alias("month_end"))
        .sort("month_end")
        .collect()
    )
    return out["month_end"].to_list()


def _empty_snapshot() -> pl.DataFrame:
    return pl.DataFrame(schema=SNAPSHOT_SCHEMA)


def build_snapshot(
    bars: pl.LazyFrame,
    rebuild_date: dt.date,
    *,
    top_n: int,
    adv_window: int,
    min_price: float,
    min_days: int,
) -> pl.DataFrame:
    """Universe membership decided on ``rebuild_date``.

    ``bars`` must already be revision-deduped (i.e. come from
    :meth:`PITStore.asof`); this function only looks backward in
    ``effective_date`` from ``rebuild_date``.
    """
    window_dates = (
        bars.select(pl.col("effective_date").unique())
        .filter(pl.col("effective_date") <= rebuild_date)
        .sort("effective_date", descending=True)
        .head(adv_window)
        .collect()["effective_date"]
    )
    # Too little trailing history (start of the lake): no universe rather
    # than a universe ranked on noise.
    if len(window_dates) < min_days:
        return _empty_snapshot()

    window = bars.filter(
        pl.col("effective_date").is_between(window_dates.min(), rebuild_date)
    )
    ranked = (
        window.group_by("security_id")
        .agg(
            pl.col("dollar_volume").median().alias("median_dollar_volume"),
            # Most recent *unadjusted* close: the price filter means the
            # actual ticket price, and adj_close rewrites history per split.
            pl.col("close").sort_by("effective_date").last().alias("last_close"),
            pl.len().alias("days_traded"),
        )
        .filter(
            (pl.col("days_traded") >= min_days)
            & (pl.col("last_close") > min_price)
            & pl.col("median_dollar_volume").is_not_null()
        )
        .sort("median_dollar_volume", descending=True)
        .head(top_n)
        .collect()
        .with_row_index("rank", offset=1)
    )
    return ranked.select(
        pl.lit(rebuild_date, dtype=pl.Date).alias("effective_date"),
        pl.col("security_id"),
        pl.col("rank"),
        pl.col("median_dollar_volume"),
        pl.col("last_close"),
        pl.col("days_traded").cast(pl.UInt32),
    )


def build_universe(
    store: PITStore,
    start_year: int,
    end_year: int,
    *,
    top_n: int = 1000,
    adv_window: int = 60,
    min_price: float = 5.0,
    min_days: int | None = None,
    knowledge_ts: dt.datetime | None = None,
) -> pl.DataFrame:
    """All monthly snapshots for rebuild dates in [start_year, end_year]."""
    if min_days is None:
        min_days = max(1, (2 * adv_window) // 3)
    if knowledge_ts is None:
        knowledge_ts = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    bars = store.asof(BARS_DATASET, knowledge_ts, keys=["security_id"])
    rebuilds = [
        d
        for d in month_end_trading_days(bars)
        if start_year <= d.year <= end_year
    ]
    snapshots = [
        build_snapshot(
            bars,
            d,
            top_n=top_n,
            adv_window=adv_window,
            min_price=min_price,
            min_days=min_days,
        )
        for d in rebuilds
    ]
    if not snapshots:
        return _empty_snapshot()
    return pl.concat(snapshots)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build monthly PIT universe snapshots from the lake"
    )
    parser.add_argument("--start", type=int, default=2011)
    parser.add_argument("--end", type=int, default=dt.date.today().year)
    parser.add_argument("--lake", default="lake")
    parser.add_argument("--top", type=int, default=1000)
    parser.add_argument("--window", type=int, default=60, help="trailing trading days")
    parser.add_argument("--min-price", type=float, default=5.0)
    parser.add_argument(
        "--min-days",
        type=int,
        default=None,
        help="min days traded in window (default: 2/3 of --window)",
    )
    args = parser.parse_args(argv)

    store = PITStore(args.lake)
    knowledge_ts = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    t0 = time.perf_counter()
    universe = build_universe(
        store,
        args.start,
        args.end,
        top_n=args.top,
        adv_window=args.window,
        min_price=args.min_price,
        min_days=args.min_days,
        knowledge_ts=knowledge_ts,
    )
    if universe.is_empty():
        print("no snapshots built — lake empty or window never satisfied")
        return 1
    for (year,), year_df in sorted(
        universe.group_by(pl.col("effective_date").dt.year()), key=lambda kv: kv[0]
    ):
        store.append(
            UNIVERSE_DATASET, year_df, knowledge_ts=knowledge_ts, part=str(year)
        )
        n_snaps = year_df["effective_date"].n_unique()
        print(f"{year}: {n_snaps} snapshots, {year_df.height} member-rows")
    elapsed = time.perf_counter() - t0
    n_total = universe["effective_date"].n_unique()
    print(
        f"done: {n_total} snapshots, {universe.height} rows in {elapsed:.1f}s "
        f"— record in docs/METRICS.md"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
