"""One-time port of a local PITStore dataset into Delta (Block 6c).

Copies every ``knowledge_ts`` batch from the local lake, not just the
current ``asof`` view — each batch is re-stamped on the Delta side with
its ORIGINAL ``knowledge_ts`` (via :meth:`DeltaPITStore.append`), so the
full bitemporal history (every vendor revision, exactly as it was known)
survives the copy, not just a single current snapshot.

Loaders (CRSPDailyLoader, YFinanceDailyLoader) are untouched by this —
this only moves data already pulled/audited/tested into the local lake.
Re-running vendor pulls against Spark/Databricks directly is a separate,
larger scope not taken on here (see docs/STATE.md Block 6c).
"""

from __future__ import annotations

import argparse
import time
from typing import TYPE_CHECKING

import polars as pl

from research.data.store import PITStore

if TYPE_CHECKING:
    # Deferred: DeltaPITStore itself imports databricks.connect at module
    # level, which isn't installed in the main .venv (see delta_store.py's
    # docstring) — this file must stay importable there regardless.
    from research.data.delta_store import DeltaPITStore


def port_dataset(
    local_store: PITStore,
    delta_store: "DeltaPITStore",
    dataset: str,
    keys: list[str],
) -> int:
    """Copy every batch of ``dataset`` from local_store into delta_store.

    Returns total rows ported (summed across all knowledge_ts batches).
    """
    df = local_store.scan(dataset).collect()
    unsigned_cols = [
        c
        for c, dtype in df.schema.items()
        if dtype in (pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64)
    ]
    total = 0
    for ts in sorted(df["knowledge_ts"].unique().to_list()):
        batch = df.filter(pl.col("knowledge_ts") == ts).drop(
            "knowledge_ts", "load_ts"
        )
        if unsigned_cols:
            # Spark Connect's Arrow bridge doesn't support unsigned int
            # types (e.g. a Polars rank()/count() column defaults to
            # UInt32) — cast to signed before the pandas/Spark handoff.
            batch = batch.with_columns(
                pl.col(c).cast(pl.Int64) for c in unsigned_cols
            )
        pdf = batch.to_pandas()
        spark_df = delta_store.spark.createDataFrame(pdf)
        # pandas has no date-only dtype: to_pandas() materializes pl.Date as
        # datetime64[ns], which createDataFrame infers as Spark TimestampType.
        # Cast back to DateType explicitly or DeltaPITStore.append's schema
        # check (correctly) rejects it.
        spark_df = spark_df.withColumn(
            "effective_date", spark_df["effective_date"].cast("date")
        )
        delta_store.append(dataset, spark_df, knowledge_ts=ts, keys=keys)
        total += len(pdf)
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Port a local PITStore dataset's full batch history into Delta"
    )
    parser.add_argument("--dataset", default="yfinance_daily")
    parser.add_argument("--keys", nargs="+", default=["security_id"])
    parser.add_argument("--lake", default="lake")
    parser.add_argument("--catalog", default="mfts")
    parser.add_argument("--schema", default="research")
    args = parser.parse_args(argv)

    from databricks.connect import DatabricksSession  # deferred: only the live port needs it
    from research.data.delta_store import DeltaPITStore  # deferred: same reason

    local_store = PITStore(args.lake)
    spark = DatabricksSession.builder.serverless(True).getOrCreate()
    delta_store = DeltaPITStore(spark, args.catalog, args.schema)

    t0 = time.perf_counter()
    total = port_dataset(local_store, delta_store, args.dataset, args.keys)
    elapsed = time.perf_counter() - t0
    rate = total / elapsed if elapsed > 0 else 0.0
    print(
        f"{args.dataset}: {total} rows ported in {elapsed:.1f}s "
        f"({rate:,.0f} rows/s) — record in docs/METRICS.md"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
