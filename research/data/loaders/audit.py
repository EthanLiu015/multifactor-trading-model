"""Shared audit for daily-bars loaders (DESIGN.md Block 1d).

Every vendor chunk passes the same gate before it may enter the PIT
store: duplicates hard-fail (a dup here would silently double positions
downstream), a complete past year must look like a full trading year,
and data-quality issues (nulls, absurd returns, tickers the vendor
failed to deliver) are *counted and kept* — the audit's job is to make
problems visible, never to silently repair or drop data.

Extracted from crsp_daily.py (part 2b) so every loader shares one
definition of "clean".
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import polars as pl

MAX_ABS_RET = 2.0  # |ret| above this is counted as an outlier, never dropped
FULL_YEAR_TRADING_DAYS = (240, 260)  # sanity bounds for a complete year


@dataclass
class AuditReport:
    year: int
    rows: int
    trading_days: int
    null_counts: dict[str, int]
    ret_outliers: int
    failures: list[str] = field(default_factory=list)
    written_to: str | None = None
    # Symbols requested from the vendor but absent from its response
    # (yfinance: usually delisted tickers). Flagged, never a failure.
    fetch_failures: int = 0

    @property
    def ok(self) -> bool:
        return not self.failures


def audit_daily_bars(
    df: pl.DataFrame,
    year: int,
    *,
    null_cols: tuple[str, ...],
    max_abs_ret: float = MAX_ABS_RET,
    full_year_days: tuple[int, int] = FULL_YEAR_TRADING_DAYS,
    fetch_failures: int = 0,
) -> AuditReport:
    """Audit one yearly chunk of daily bars keyed (security_id, effective_date).

    Hard failures (chunk quarantined): empty chunk, duplicate
    (security_id, effective_date) rows, implausible trading-day count for
    a complete past year. Everything else is counted and kept.
    """
    failures: list[str] = []
    rows = df.shape[0]
    if rows == 0:
        return AuditReport(
            year, 0, 0, {}, 0, failures=["empty chunk"], fetch_failures=fetch_failures
        )

    dups = rows - df.select(["security_id", "effective_date"]).unique().shape[0]
    if dups > 0:
        failures.append(f"{dups} duplicate (security_id, effective_date) rows")

    trading_days = df["effective_date"].n_unique()
    lo, hi = full_year_days
    # Bounds apply only to complete years: [lo, hi] inclusive both ends.
    if year < dt.date.today().year and not lo <= trading_days <= hi:
        failures.append(
            f"{trading_days} trading days for complete year, expected {lo}-{hi}"
        )

    null_counts = {c: int(df[c].null_count()) for c in null_cols}
    ret_outliers = int(df.filter(pl.col("ret").abs() > max_abs_ret).shape[0])
    return AuditReport(
        year,
        rows,
        trading_days,
        null_counts,
        ret_outliers,
        failures,
        fetch_failures=fetch_failures,
    )
