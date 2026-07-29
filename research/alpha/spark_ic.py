"""Spark benchmark for the historical alpha run (Block 6d).

Re-executes the SAME per-date IC computation as
:func:`research.alpha.ic.build_ic_series` — via
:func:`research.alpha.ic._ic_for_date`, unchanged — but distributes it
across Spark executors via ``groupBy(rebalance_date).applyInPandas(...)``
instead of a local Python loop, to compare wall time against the 824.2s
local baseline (docs/METRICS.md).

No ``sc.broadcast()``: Spark Connect (what ``DatabricksSession`` uses) has
no ``sparkContext`` / RDD-broadcast API at all — confirmed by inspecting
``pyspark.sql.connect.session.SparkSession`` directly, not assumed (see
docs/STATE.md Block 6d-iii).

A first version closed the per-date function over the full driver-collected
bars/universe frames directly (relying on ordinary PySpark UDF closure
mechanics instead of an explicit broadcast call). That hit a real, hard
wall: ``applyInPandas``'s function is cloudpickled as ONE blob and sent as
a single gRPC message when the query plan is registered — no chunking,
unlike ``spark.createDataFrame()`` (which streams/batches large local data
fine, see block 6c). The pickled closure came out to 462MB against Spark
Connect's 128MB hard cap.

Fixed with a real Spark-side broadcast RANGE-JOIN instead: ``dates_sdf``
(185 tiny rows: rebalance_date + a generous trailing/forward window) is
broadcast (``F.broadcast``, matching DESIGN.md's own security-master-join
pattern — small side broadcast, big side untouched) and joined against
``bars_sdf`` on ``effective_date BETWEEN window_start AND window_end``, so
each date's ``applyInPandas`` group already contains exactly the bars rows
it needs — no client-shipped blob. Universe membership stays a plain
closure dict (``members_by_date``): at ~185 dates x ~1,000 tickers it's a
few MB, nowhere near the 128MB ceiling, so there's no reason to route it
through Spark too.

Window sizing: the largest lookback any signal needs is momentum's
``lookback_days=252 + skip_days=21`` = 273 trading days; low_vol needs 252;
reversal needs 21. 273 trading days ~= 382-397 calendar days after
weekends/holidays, so 430 calendar days back is a deliberate margin, not a
tight fit. Forward side needs ``horizon_days`` (default 21) trading days;
35 calendar days covers that comfortably. A signal's shift-then-difference
math (e.g. momentum's cum_sum().shift(lookback).shift(skip)) is invariant
to where the cumulative sum starts counting from, provided the window
contains enough trailing rows — so narrowing bars to this window changes
nothing about the computed value, only how much data gets shipped.
"""

from __future__ import annotations

import argparse
import datetime as dt
import time
from typing import TYPE_CHECKING, Callable

import polars as pl

from research.alpha.ic import BARS_DATASET, UNIVERSE_DATASET, _ic_for_date
from research.signals import SIGNAL_REGISTRY

if TYPE_CHECKING:
    # Deferred: DeltaPITStore imports databricks.connect at module level,
    # not installed in the main .venv (see delta_store.py's docstring).
    from research.data.delta_store import DeltaPITStore

RESULT_SCHEMA = "rebalance_date date, signal string, ic double"


def build_ic_series_spark(
    delta_store: "DeltaPITStore",
    signal_fns: dict[str, Callable[..., pl.DataFrame]],
    start_year: int,
    end_year: int,
    *,
    horizon_days: int = 21,
    knowledge_ts: dt.datetime | None = None,
) -> pl.DataFrame:
    """Same result as build_ic_series (long format: rebalance_date/signal/ic
    rows instead of one frame per signal), computed via Spark instead of a
    local Python loop over rebalance dates.
    """
    from pyspark.sql import functions as F

    if knowledge_ts is None:
        knowledge_ts = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

    bars_sdf = delta_store.asof(BARS_DATASET, knowledge_ts, keys=["security_id"]).select(
        "security_id", "effective_date", "ret"
    )
    universe_pl = pl.from_pandas(
        delta_store.asof(UNIVERSE_DATASET, knowledge_ts, keys=["security_id"]).toPandas()
    ).with_columns(pl.col("effective_date").cast(pl.Date))

    rebuild_dates = sorted(
        d
        for d in universe_pl.select(pl.col("effective_date").unique())["effective_date"]
        if start_year <= d.year <= end_year
    )

    # Small (185 dates x ~1000 tickers, a few MB) — safe as a closure, no
    # need to route it through the Spark-side join like bars.
    members_by_date = {
        d: universe_pl.filter(pl.col("effective_date") == d)["security_id"].to_list()
        for d in rebuild_dates
    }

    trailing_buffer_days = 430  # margin over momentum's ~397-calendar-day need
    forward_buffer_days = 35  # margin over horizon_days=21 trading days
    dates_sdf = delta_store.spark.createDataFrame(
        [
            {
                "rebalance_date": d,
                "window_start": d - dt.timedelta(days=trailing_buffer_days),
                "window_end": d + dt.timedelta(days=forward_buffer_days),
            }
            for d in rebuild_dates
        ]
    )

    joined_sdf = bars_sdf.join(
        F.broadcast(dates_sdf),
        (bars_sdf["effective_date"] >= dates_sdf["window_start"])
        & (bars_sdf["effective_date"] <= dates_sdf["window_end"]),
    ).select(
        dates_sdf["rebalance_date"],
        bars_sdf["security_id"],
        bars_sdf["effective_date"],
        bars_sdf["ret"],
    )

    def _per_date(pdf):
        import pandas as pd

        d = pdf["rebalance_date"].iloc[0]
        window_bars = (
            pl.from_pandas(pdf.drop(columns=["rebalance_date"]))
            .with_columns(pl.col("effective_date").cast(pl.Date))
            .lazy()
        )
        members = members_by_date.get(d, [])
        ic_by_signal = _ic_for_date(window_bars, members, d, signal_fns, horizon_days)
        return pd.DataFrame(
            [
                {"rebalance_date": d, "signal": name, "ic": ic}
                for name, ic in ic_by_signal.items()
            ]
        )

    result_sdf = joined_sdf.groupBy("rebalance_date").applyInPandas(
        _per_date, schema=RESULT_SCHEMA
    )
    return pl.from_pandas(result_sdf.toPandas())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute IC per signal via Spark — Block 6d benchmark"
    )
    parser.add_argument("--start", type=int, default=2011)
    parser.add_argument("--end", type=int, default=dt.date.today().year)
    parser.add_argument("--catalog", default="mfts")
    parser.add_argument("--schema", default="research")
    parser.add_argument("--horizon", type=int, default=21)
    args = parser.parse_args(argv)

    from databricks.connect import DatabricksSession  # deferred: only the live run needs it
    from research.data.delta_store import DeltaPITStore  # deferred: same reason

    spark = DatabricksSession.builder.serverless(True).getOrCreate()
    delta_store = DeltaPITStore(spark, args.catalog, args.schema)

    t0 = time.perf_counter()
    result = build_ic_series_spark(
        delta_store, SIGNAL_REGISTRY, args.start, args.end, horizon_days=args.horizon
    )
    elapsed = time.perf_counter() - t0

    for name in SIGNAL_REGISTRY:
        series = result.filter(pl.col("signal") == name).drop_nulls("ic")
        n = series.height
        mean_ic = series["ic"].mean() if n else None
        print(f"{name}: n={n} mean_ic={mean_ic}")
    print(f"all signals computed via Spark in {elapsed:.1f}s — record in docs/METRICS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
