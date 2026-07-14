"""CRSP daily-bars loader (WRDS, CRSP 2.0 / "CIZ" format).

Pulls daily bars for all US common stocks from ``crsp.dsf_v2``, scrubs and
audits each yearly chunk, and appends passing chunks to the PITStore under
one ``knowledge_ts`` per download run (``part=<year>`` per chunk, so a
re-run of one year overwrites only that year's file).

Delisting returns: in the CIZ format the daily total-return field
(``dlyret``) already includes the delisting distribution on a security's
final trading day, so no separate delisting merge is needed.

Column names and filter values below are CIZ-format expectations taken from
CRSP documentation; :meth:`CRSPDailyLoader.verify_schema` asserts them
against the live table before any pull.
"""

from __future__ import annotations

import argparse
import datetime as dt
import time
from dataclasses import dataclass, field

import polars as pl

from research.data.store import PITStore

DATASET = "crsp_daily"
LIBRARY = "crsp"
TABLE = "dsf_v2"

# CIZ source column -> internal name. permno is CRSP's permanent security
# identifier and becomes the security master's spine in part 4.
SRC_COLUMNS = {
    "permno": "security_id",
    "dlycaldt": "effective_date",
    "dlyclose": "close",
    "dlyret": "ret",  # total return incl. dividends and delisting
    "dlyretx": "retx",  # price-only return
    "dlyvol": "volume",
    "shrout": "shrout",  # shares outstanding, thousands
}

# CIZ common-stock universe: US-incorporated ordinary common shares on
# NYSE ('N'), AMEX ('A'), NASDAQ ('Q'), regular-way, actively trading.
COMMON_STOCK_WHERE = (
    "sharetype = 'NS' AND securitytype = 'EQTY' AND securitysubtype = 'COM'"
    " AND usincflg = 'Y' AND issuertype IN ('ACOR', 'CORP')"
    " AND primaryexch IN ('N', 'A', 'Q') AND conditionaltype = 'RW'"
    " AND tradingstatusflg = 'A'"
)

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

    @property
    def ok(self) -> bool:
        return not self.failures


class CRSPDailyLoader:
    """scrub -> audit -> PIT store, per DESIGN.md Block 1d contract.

    ``conn`` is a ``wrds.Connection`` (or a test double exposing
    ``raw_sql`` and ``describe_table``).
    """

    def __init__(self, conn, store: PITStore) -> None:
        self.conn = conn
        self.store = store

    def verify_schema(self) -> list[str]:
        """Assert expected CIZ columns exist on the live table."""
        info = self.conn.describe_table(LIBRARY, TABLE)
        actual = {str(name).lower() for name in info["name"]}
        missing = sorted(c for c in SRC_COLUMNS if c not in actual)
        if missing:
            raise RuntimeError(
                f"{LIBRARY}.{TABLE} missing expected columns: {missing}"
            )
        return sorted(actual)

    def load_year(self, year: int, knowledge_ts: dt.datetime) -> AuditReport:
        """Pull one calendar year, audit it, append or quarantine it."""
        pdf = self.conn.raw_sql(
            f"SELECT {', '.join(SRC_COLUMNS)} FROM {LIBRARY}.{TABLE}"
            f" WHERE {COMMON_STOCK_WHERE}"
            # dates (not timestamps): BETWEEN is inclusive both ends,
            # covering exactly [Jan 1, Dec 31] of the year.
            " AND dlycaldt BETWEEN %(start)s AND %(end)s",
            params={"start": f"{year}-01-01", "end": f"{year}-12-31"},
            date_cols=["dlycaldt"],
        )
        df = self._transform(pdf)
        report = self._audit(df, year)
        if report.ok:
            path = self.store.append(
                DATASET, df, knowledge_ts=knowledge_ts, part=str(year)
            )
        else:
            path = self._quarantine(df, year, knowledge_ts)
        report.written_to = str(path)
        return report

    def _transform(self, pdf) -> pl.DataFrame:
        df = pl.from_pandas(pdf).rename(SRC_COLUMNS)
        return df.with_columns(
            pl.col("security_id").cast(pl.Int64),
            pl.col("effective_date").cast(pl.Date),
            (pl.col("close") * pl.col("volume")).alias("dollar_volume"),
            # shrout is in thousands of shares
            (pl.col("close") * pl.col("shrout") * 1000).alias("market_cap"),
        )

    def _audit(self, df: pl.DataFrame, year: int) -> AuditReport:
        failures: list[str] = []
        rows = df.shape[0]
        if rows == 0:
            return AuditReport(year, 0, 0, {}, 0, failures=["empty chunk"])

        dups = rows - df.select(["security_id", "effective_date"]).unique().shape[0]
        if dups > 0:
            failures.append(f"{dups} duplicate (security_id, effective_date) rows")

        trading_days = df["effective_date"].n_unique()
        lo, hi = FULL_YEAR_TRADING_DAYS
        if year < dt.date.today().year and not lo <= trading_days <= hi:
            failures.append(
                f"{trading_days} trading days for complete year, expected {lo}-{hi}"
            )

        null_counts = {
            c: int(df[c].null_count()) for c in ("close", "ret", "volume", "shrout")
        }
        ret_outliers = int(
            df.filter(pl.col("ret").abs() > MAX_ABS_RET).shape[0]
        )
        return AuditReport(year, rows, trading_days, null_counts, ret_outliers, failures)

    def _quarantine(self, df: pl.DataFrame, year: int, knowledge_ts: dt.datetime):
        qdir = self.store.root / "_quarantine"
        qdir.mkdir(parents=True, exist_ok=True)
        stamp = knowledge_ts.isoformat().replace(":", "-")
        path = qdir / f"{DATASET}_{year}_k={stamp}.parquet"
        df.write_parquet(path)
        return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load CRSP daily bars into the lake")
    parser.add_argument("--start", type=int, default=2011)
    parser.add_argument("--end", type=int, default=dt.date.today().year)
    parser.add_argument("--lake", default="lake")
    args = parser.parse_args(argv)

    import wrds  # deferred: only the live pull needs credentials

    conn = wrds.Connection()
    loader = CRSPDailyLoader(conn, PITStore(args.lake))
    loader.verify_schema()
    print(f"schema verified: {LIBRARY}.{TABLE}")

    # Naive UTC, matching the store's own load_ts convention.
    knowledge_ts = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    t0 = time.perf_counter()
    total_rows = 0
    quarantined = 0
    for year in range(args.start, args.end + 1):
        try:
            report = loader.load_year(year, knowledge_ts)
        except Exception as exc:  # keep going; re-run of a year is idempotent
            print(f"{year}: FAILED — {exc}")
            quarantined += 1
            continue
        total_rows += report.rows
        status = "ok" if report.ok else f"QUARANTINED ({'; '.join(report.failures)})"
        print(
            f"{year}: {report.rows} rows, {report.trading_days} days, "
            f"{report.ret_outliers} ret outliers, nulls={report.null_counts} — {status}"
        )
        if not report.ok:
            quarantined += 1

    elapsed = time.perf_counter() - t0
    rate = total_rows / elapsed if elapsed > 0 else 0.0
    print(
        f"done: {total_rows} rows in {elapsed:.1f}s ({rate:,.0f} rows/s), "
        f"{quarantined} year(s) quarantined/failed — record in docs/METRICS.md"
    )
    return 1 if quarantined else 0


if __name__ == "__main__":
    raise SystemExit(main())
