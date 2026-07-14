"""Point-in-time (bitemporal) parquet store.

Every dataset in the lake carries two time axes:

- ``effective_date``: when the fact was true in the market (trade date,
  fiscal period end). Supplied by the caller.
- ``knowledge_ts``: when we learned the fact (download time, filing time).
  Stamped by :meth:`PITStore.append`.

All reads for research go through :meth:`PITStore.asof`, which filters to
rows known on-or-before a cutoff and keeps only the latest known revision
of each row. Look-ahead bias is therefore prevented by construction, not
by caller discipline.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

# Columns appended by the store itself; callers must not supply them.
STAMP_COLUMNS = ("knowledge_ts", "load_ts")


class PITStore:
    """A directory-per-dataset parquet lake with point-in-time reads."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _dataset_dir(self, dataset: str) -> Path:
        return self.root / dataset

    def append(
        self,
        dataset: str,
        df: pl.DataFrame,
        knowledge_ts: dt.datetime,
        part: str | None = None,
    ) -> Path:
        """Write one load batch. Idempotent: same knowledge_ts overwrites.

        The batch file is named by ``knowledge_ts``, so re-running a load
        replaces its previous output instead of duplicating rows.

        ``part`` splits one logical load into several files (e.g. one per
        year) under the same ``knowledge_ts``; re-running a part overwrites
        only that part's file.
        """
        if part is not None and not part.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"{dataset}: part {part!r} must be alphanumeric/-/_")
        if "effective_date" not in df.columns:
            raise ValueError(f"{dataset}: missing required column 'effective_date'")
        if df.schema["effective_date"] != pl.Date:
            raise ValueError(
                f"{dataset}: 'effective_date' must be pl.Date, "
                f"got {df.schema['effective_date']}"
            )
        for col in STAMP_COLUMNS:
            if col in df.columns:
                raise ValueError(f"{dataset}: column '{col}' is stamped by the store")

        stamped = df.with_columns(
            pl.lit(knowledge_ts).alias("knowledge_ts"),
            pl.lit(dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)).alias(
                "load_ts"
            ),
        )
        out_dir = self._dataset_dir(dataset)
        out_dir.mkdir(parents=True, exist_ok=True)
        suffix = "" if part is None else f"_part={part}"
        out_path = (
            out_dir / f"k={knowledge_ts.isoformat().replace(':', '-')}{suffix}.parquet"
        )
        stamped.write_parquet(out_path)
        return out_path

    def scan(self, dataset: str) -> pl.LazyFrame:
        """Lazy scan of every batch in a dataset (no PIT filtering)."""
        pattern = self._dataset_dir(dataset) / "*.parquet"
        return pl.scan_parquet(pattern)

    def asof(
        self,
        dataset: str,
        knowledge_ts: dt.datetime,
        keys: list[str],
    ) -> pl.LazyFrame:
        """The world as we knew it at ``knowledge_ts``.

        Drops rows learned after the cutoff, then keeps only the latest
        known revision of each (keys, effective_date) row — so vendor
        restatements are visible only once they were knowable.
        """
        return (
            self.scan(dataset)
            .filter(pl.col("knowledge_ts") <= knowledge_ts)
            .sort("knowledge_ts")
            .group_by([*keys, "effective_date"], maintain_order=True)
            .last()
        )
