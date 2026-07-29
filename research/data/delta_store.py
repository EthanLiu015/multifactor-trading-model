"""Delta-backed point-in-time store — Unity Catalog mirror of PITStore.

Same bitemporal invariant as :class:`research.data.store.PITStore`
(``effective_date`` supplied by the caller, ``knowledge_ts`` stamped by the
store), but the *mechanism* differs from the local parquet store in two
ways forced by the storage engine, not by preference:

- **Idempotency is a MERGE, not a file overwrite.** PITStore dedups by
  overwriting a same-named parquet file (``k=<knowledge_ts>.parquet``).
  Delta tables have no per-batch file identity to overwrite, so
  :meth:`DeltaPITStore.append` MERGEs each batch into the table keyed on
  ``keys + effective_date + knowledge_ts`` instead. Same guarantee
  (re-running a load replaces its own rows, never duplicates), different
  implementation — this is why ``append`` here takes a ``keys`` argument
  that :meth:`PITStore.append` does not need.
- **No ``part`` concept.** PITStore's ``part`` splits one logical load into
  several physical files under one ``knowledge_ts`` purely as a storage
  detail — no read path ever filters on it. A MERGE has no equivalent unit,
  so it is not reproduced here.

Requires the ``delta`` extra (``databricks-connect``), installed into its
own venv (``.venv-delta/``) — never the project's main ``.venv``, which
pins ``numpy>=2.0``; ``databricks-connect`` forces a ``numpy<2`` downgrade
that would silently violate it. See docs/STATE.md Block 6b.
"""

from __future__ import annotations

import datetime as dt

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

# Columns appended by the store itself; callers must not supply them.
# Mirrors research.data.store.STAMP_COLUMNS exactly (same invariant).
STAMP_COLUMNS = ("knowledge_ts", "load_ts")


class DeltaPITStore:
    """A Unity Catalog schema (``catalog.schema``) with point-in-time reads."""

    def __init__(self, spark: SparkSession, catalog: str, schema: str) -> None:
        self.spark = spark
        self.catalog = catalog
        self.schema = schema

    def _table(self, dataset: str) -> str:
        return f"{self.catalog}.{self.schema}.{dataset}"

    def append(
        self,
        dataset: str,
        df: DataFrame,
        knowledge_ts: dt.datetime,
        keys: list[str],
    ) -> None:
        """MERGE one load batch. Idempotent: same (keys, effective_date,
        knowledge_ts) rows are replaced, never duplicated.
        """
        if "effective_date" not in df.columns:
            raise ValueError(f"{dataset}: missing required column 'effective_date'")
        if dict(df.dtypes)["effective_date"] != "date":
            raise ValueError(
                f"{dataset}: 'effective_date' must be a date column, "
                f"got {dict(df.dtypes)['effective_date']}"
            )
        for col in STAMP_COLUMNS:
            if col in df.columns:
                raise ValueError(f"{dataset}: column '{col}' is stamped by the store")

        load_ts = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        stamped = df.withColumn("knowledge_ts", F.lit(knowledge_ts)).withColumn(
            "load_ts", F.lit(load_ts)
        )

        table = self._table(dataset)
        if not self.spark.catalog.tableExists(table):
            stamped.write.format("delta").saveAsTable(table)
            return

        merge_keys = [*keys, "effective_date", "knowledge_ts"]
        condition = " AND ".join(f"t.{k} = s.{k}" for k in merge_keys)
        (
            DeltaTable.forName(self.spark, table)
            .alias("t")
            .merge(stamped.alias("s"), condition)
            .whenMatchedUpdateAll()
            .whenNotMatchedInsertAll()
            .execute()
        )

    def scan(self, dataset: str) -> DataFrame:
        """Every batch in a dataset (no PIT filtering)."""
        return self.spark.table(self._table(dataset))

    def asof(
        self,
        dataset: str,
        knowledge_ts: dt.datetime,
        keys: list[str],
    ) -> DataFrame:
        """The world as known at ``knowledge_ts`` — same semantics as
        PITStore.asof: drop rows learned after the cutoff, keep only the
        latest known revision of each (keys, effective_date) row.
        """
        window = Window.partitionBy(*keys, "effective_date").orderBy(
            F.col("knowledge_ts").desc()
        )
        return (
            self.scan(dataset)
            .filter(F.col("knowledge_ts") <= knowledge_ts)
            .withColumn("_rank", F.row_number().over(window))
            .filter(F.col("_rank") == 1)
            .drop("_rank")
        )
