"""Security master (part 4, block 1): schema + PITStore fit.

Problem this exists to fix: ``crsp_daily.security_id`` is CRSP's permno;
``yfinance_daily`` and ``universe_monthly`` key on ticker string. Same
column name, two incompatible identifier spaces — joining them today would
silently produce garbage. DESIGN.md (1b) additionally requires *point-in-time*
identifier resolution: tickers get reused by unrelated companies over time,
so any external identifier is only valid over a date range, resolved as of
an observation date — never with today's mapping.

This block only settles the schema/storage fit; extraction from vendor
data (block 2) and the ``resolve_security()`` lookup (block 3) come later.

Ticker-only for now: CRSP access is WRDS-seasonal-blocked, so permno/CUSIP
mapping has no live source yet. ``id_type`` stays a free column (not
hardcoded to "ticker") so CRSP identifiers slot in later with no schema
migration.

Storage reuses PITStore exactly as ``universe.py`` does: the store's
required ``effective_date`` column plays the role of ``valid_from`` here
(the date this identifier mapping became true), and ``knowledge_ts``
(stamped by the store) is when we computed/asserted the mapping — the same
two PIT axes every other dataset uses, repurposed per dataset rather than
reimplemented.
"""

from __future__ import annotations

import argparse
import datetime as dt

import polars as pl

from research.data import PITStore

DATASET = "security_master"
BARS_DATASET = "yfinance_daily"

SCHEMA = {
    "effective_date": pl.Date,  # valid_from: when this mapping became true
    "internal_id": pl.UInt32,  # permanent spine id, stable across id_type/id_value
    "id_type": pl.String,  # "ticker" today; "permno"/"cusip"/... once CRSP lands
    "id_value": pl.String,  # e.g. "AAPL"
    "valid_to": pl.Date,  # null = still current
    "source": pl.String,  # provenance, e.g. "yfinance_daily"
}


def empty_master() -> pl.DataFrame:
    """Zero-row frame with the security master schema."""
    return pl.DataFrame(schema=SCHEMA)


def _ticker_segments(bars: pl.LazyFrame, gap_days: int) -> pl.DataFrame:
    """One row per (ticker, contiguous trading run).

    A gap of more than ``gap_days`` calendar days between two consecutive
    trading dates for the same ticker starts a new segment — a heuristic
    proxy for "this symbol was reassigned to an unrelated company"
    (DESIGN.md 1b). This is NOT a real corporate-actions feed: it cannot
    distinguish an actual delisting+relist from an unusually long halt on
    the same company. Real disambiguation needs CUSIP from CRSP (block 4).
    """
    dates = (
        bars.select("security_id", "effective_date")
        .unique()
        .sort(["security_id", "effective_date"])
        .collect()
    )
    gap = pl.col("effective_date").diff().over("security_id").dt.total_days()
    return (
        dates.with_columns((gap.fill_null(0) > gap_days).alias("_new_segment"))
        .with_columns(
            pl.col("_new_segment").cum_sum().over("security_id").alias("_segment")
        )
        .group_by(["security_id", "_segment"])
        .agg(
            pl.col("effective_date").min().alias("valid_from"),
            pl.col("effective_date").max().alias("valid_to_raw"),
        )
    )


def build_ticker_segments(
    bars: pl.LazyFrame, *, gap_days: int = 90, source: str = BARS_DATASET
) -> pl.DataFrame:
    """Ticker identity segments from ``bars``, ready for ``store.append``.

    ``internal_id`` is assigned deterministically by sorting segments on
    (valid_from, ticker) — reruns over unchanged bars reproduce the same
    IDs. A segment reaching the lake's most recent trading date gets
    ``valid_to = null`` (still current); any earlier-ending segment gets a
    concrete ``valid_to``.
    """
    segments = _ticker_segments(bars, gap_days)
    if segments.is_empty():
        return empty_master()
    latest_date = segments["valid_to_raw"].max()
    return (
        segments.sort(["valid_from", "security_id"])
        .with_row_index("internal_id", offset=1)
        .select(
            pl.col("valid_from").alias("effective_date"),
            pl.col("internal_id").cast(pl.UInt32),
            pl.lit("ticker").alias("id_type"),
            pl.col("security_id").alias("id_value"),
            pl.when(pl.col("valid_to_raw") == latest_date)
            .then(None)
            .otherwise(pl.col("valid_to_raw"))
            .alias("valid_to"),
            pl.lit(source).alias("source"),
        )
    )


def resolve_securities(
    store: PITStore,
    id_values,
    as_of: dt.date,
    *,
    id_type: str = "ticker",
    knowledge_ts: dt.datetime | None = None,
) -> pl.DataFrame:
    """internal_id for a whole panel of identifiers, all as of one date.

    One vectorized query — the house rule (no Python loops over stocks,
    house convention) means callers resolving e.g. a universe snapshot's
    1,000 tickers pass them all here at once, not in a per-ticker loop.
    Unresolvable identifiers (no segment covers ``as_of``) are simply
    absent from the output — compare output height against ``len(id_values)``
    to detect gaps, there is no per-row null placeholder.
    """
    if knowledge_ts is None:
        knowledge_ts = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    return (
        store.asof(DATASET, knowledge_ts, keys=["internal_id"])
        .filter(
            (pl.col("id_type") == id_type)
            & pl.col("id_value").is_in(list(id_values))
            & (pl.col("effective_date") <= as_of)
            & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= as_of))
        )
        .select("id_value", "internal_id")
        .collect()
    )


def resolve_security(
    store: PITStore,
    id_value: str,
    as_of: dt.date,
    *,
    id_type: str = "ticker",
    knowledge_ts: dt.datetime | None = None,
) -> int | None:
    """Scalar convenience over :func:`resolve_securities` — one identifier.

    For tests/debugging/CLI use. Production panel code should call
    :func:`resolve_securities` directly instead of looping this.
    """
    hit = resolve_securities(
        store, [id_value], as_of, id_type=id_type, knowledge_ts=knowledge_ts
    )
    return hit["internal_id"][0] if hit.height else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract ticker identity segments into security_master"
    )
    parser.add_argument("--lake", default="lake")
    parser.add_argument(
        "--gap-days",
        type=int,
        default=90,
        help="trading gap (calendar days) that splits one ticker into two identities",
    )
    args = parser.parse_args(argv)

    store = PITStore(args.lake)
    knowledge_ts = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    bars = store.asof(BARS_DATASET, knowledge_ts, keys=["security_id"])
    rows = build_ticker_segments(bars, gap_days=args.gap_days)
    if rows.is_empty():
        print("no segments built — bars lake empty")
        return 1

    store.append(DATASET, rows, knowledge_ts=knowledge_ts)
    reused = rows.group_by("id_value").agg(pl.len().alias("n")).filter(pl.col("n") > 1)
    print(
        f"done: {rows.height} identity segments, {rows['id_value'].n_unique()} tickers, "
        f"{reused.height} tickers with >1 segment (gap-detected reuse) — "
        f"record in docs/METRICS.md"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
