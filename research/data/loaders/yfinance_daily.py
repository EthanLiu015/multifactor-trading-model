"""yfinance daily-bars loader (interim free vendor, part 2b).

Fills the lake while Duke's WRDS/CRSP access is season-blocked (summer
2026). Same Block 1d contract as crsp_daily: pull -> transform -> audit
-> PIT append on pass / quarantine on fail. Dataset ``yfinance_daily``
is keyed by ticker and is NEVER merged with ``crsp_daily`` — identifier
reconciliation waits for the security master (part 4).

Known, accepted limitations of this vendor (replaced wholesale by CRSP
in fall):

- Survivorship bias: yfinance only serves currently listed tickers; no
  delisting returns. Documented interim state.
- No point-in-time shares outstanding: only a *current* snapshot exists,
  so it is stored as its own one-row-per-ticker dataset
  (``yfinance_shares_current``) and market-cap work is deferred to CRSP.
  Embedding it per bar row would forge history.
- ``ret`` is computed from adjusted close within each yearly chunk, so
  each ticker's first bar of a year has a null return (counted by the
  audit, never dropped). Full-panel returns are recomputed downstream.
- yfinance back-adjusts history retroactively (splits/dividends); each
  pull lands under a fresh ``knowledge_ts``, so ``asof`` serves every
  backtest date the vintage it could actually have known.
"""

from __future__ import annotations

import argparse
import datetime as dt
import time
import urllib.request
from collections.abc import Callable

import polars as pl

from research.data.loaders.audit import AuditReport, audit_daily_bars
from research.data.store import PITStore

DATASET = "yfinance_daily"
SHARES_DATASET = "yfinance_shares_current"

# NASDAQ Trader symbol directories: every listed US security, pipe-delimited,
# one header row, footer line starting "File Creation Time".
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

# yfinance wide-format field -> internal name. Raw Close feeds price filters
# and dollar_volume; Adj Close (splits+dividends) feeds total returns.
FIELDS = {"Close": "close", "Adj Close": "adj_close", "Volume": "volume"}


def _rate_limited_errors(errors: dict) -> bool:
    """True if a yfinance per-ticker error dict shows Yahoo throttling.

    Batch ``yf.download`` swallows YFRateLimitError per ticker and records
    it in ``yfinance.shared._ERRORS`` instead of raising; values look like
    ``"YFRateLimitError('Too Many Requests. Rate limited. ...')"``.
    Non-throttle errors (delisted: YFTzMissingError etc.) must NOT match —
    they are legitimate fetch failures, not something a retry can fix.
    """
    return any(
        "ratelimit" in str(v).replace(" ", "").lower() for v in errors.values()
    )


class YFinanceClient:
    """Thin adapter over the yfinance package; tests inject a fake instead.

    Paces requests to survive Yahoo's rate limiter: ``pause_s`` between
    chunk downloads keeps the steady-state request rate low; a throttled
    chunk is retried with exponential backoff (``backoff_base_s`` doubling
    per attempt: 60s, 120s, 240s, ...). ``sleep`` is injectable for tests.
    """

    def __init__(
        self,
        pause_s: float = 2.0,
        max_retries: int = 5,
        backoff_base_s: float = 60.0,
        threads: bool = True,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.pause_s = pause_s
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        # threads=False fetches tickers sequentially (~1-2 req/s) — the only
        # rate Yahoo's per-request limiter tolerates for bulk pulls; True
        # bursts a whole chunk in parallel and gets stealth-throttled.
        self.threads = threads
        self._sleep = sleep

    def download(self, tickers: list[str], start: str, end: str):
        import yfinance as yf  # deferred: only live pulls need it
        import yfinance.shared as shared
        from yfinance.exceptions import YFRateLimitError

        delay = self.backoff_base_s
        for attempt in range(self.max_retries + 1):
            self._sleep(self.pause_s)
            try:
                pdf = yf.download(
                    tickers,
                    start=start,
                    end=end,
                    auto_adjust=False,  # keep raw Close alongside Adj Close
                    group_by="ticker",
                    threads=self.threads,
                    progress=False,
                )
            except YFRateLimitError:
                pass  # single-ticker code paths raise instead of logging
            else:
                if not _rate_limited_errors(getattr(shared, "_ERRORS", {})):
                    return pdf  # clean or legitimately-partial chunk
            if attempt < self.max_retries:
                self._sleep(delay)
                delay *= 2
        # Exhausted: load_year's per-chunk except skips this chunk and its
        # tickers surface in fetch_failures.
        raise YFRateLimitError()

    def shares_outstanding(self, ticker: str) -> float | None:
        import yfinance as yf

        try:
            return float(yf.Ticker(ticker).fast_info["shares"])
        except Exception:
            return None  # missing/errored symbol: recorded as null, never fatal


class YFinanceDailyLoader:
    """scrub -> audit -> PIT store, per DESIGN.md Block 1d contract.

    ``client`` exposes ``download`` and ``shares_outstanding`` (see
    :class:`YFinanceClient`); tests pass an offline fake.
    """

    def __init__(self, client, store: PITStore) -> None:
        self.client = client
        self.store = store

    def load_year(
        self,
        year: int,
        tickers: list[str],
        knowledge_ts: dt.datetime,
        chunk_size: int = 200,
    ) -> AuditReport:
        """Pull one calendar year for all tickers, audit, append or quarantine.

        Downloads in ticker chunks (yfinance degrades on huge batches). A
        chunk that raises is skipped; its tickers surface in
        ``fetch_failures`` because they never appear in the result.
        """
        frames = []
        # len=5,size=2 -> [0:2][2:4][4:5] = 3 chunks
        for i in range(0, len(tickers), chunk_size):
            chunk = tickers[i : i + chunk_size]
            try:
                # yfinance date range is [start, end): next Jan 1 exclusive
                # covers exactly this calendar year.
                pdf = self.client.download(
                    chunk, start=f"{year}-01-01", end=f"{year + 1}-01-01"
                )
            except Exception:
                continue  # tickers counted below via the fetched-set diff
            if pdf is not None and not pdf.empty:
                frames.append(pdf)

        df = self._transform(frames)
        fetched = set() if df.is_empty() else set(df["security_id"].unique())
        report = self._audit(df, year, fetch_failures=len(set(tickers) - fetched))
        if report.ok:
            path = self.store.append(
                DATASET, df, knowledge_ts=knowledge_ts, part=str(year)
            )
        else:
            path = self._quarantine(df, year, knowledge_ts)
        report.written_to = str(path)
        return report

    def _transform(self, frames) -> pl.DataFrame:
        """Wide yfinance frames -> long internal schema.

        yfinance returns one column block per ticker over a shared date
        grid; tickers not trading on a date (pre-IPO, suspended) get
        all-null rows. Those grid artifacts are not observations and are
        removed (close AND volume both null) — distinct from the audit's
        flag-don't-drop rule, which applies to real rows with bad fields.
        """
        import pandas as pd

        if not frames:
            return pl.DataFrame(
                schema={
                    "security_id": pl.String,
                    "effective_date": pl.Date,
                    "close": pl.Float64,
                    "adj_close": pl.Float64,
                    "volume": pl.Float64,
                    "ret": pl.Float64,
                    "dollar_volume": pl.Float64,
                }
            )

        wide = pd.concat(frames, axis=1)  # aligns chunks on the date index
        long = wide.stack(level=0, future_stack=True).reset_index()
        long.columns = ["effective_date", "security_id", *long.columns[2:]]
        long = long[["effective_date", "security_id", *FIELDS]].rename(columns=FIELDS)

        df = (
            pl.from_pandas(long)
            .filter(~(pl.col("close").is_null() & pl.col("volume").is_null()))
            .with_columns(
                pl.col("security_id").cast(pl.String),
                pl.col("effective_date").cast(pl.Date),
            )
            .sort(["security_id", "effective_date"])
            .with_columns(
                # total return from adjusted close; first bar per ticker
                # in this chunk is null by construction
                pl.col("adj_close").pct_change().over("security_id").alias("ret"),
                (pl.col("close") * pl.col("volume")).alias("dollar_volume"),
            )
        )
        return df

    def _audit(
        self, df: pl.DataFrame, year: int, fetch_failures: int
    ) -> AuditReport:
        return audit_daily_bars(
            df,
            year,
            null_cols=("close", "ret", "volume"),
            fetch_failures=fetch_failures,
        )

    def _quarantine(self, df: pl.DataFrame, year: int, knowledge_ts: dt.datetime):
        qdir = self.store.root / "_quarantine"
        qdir.mkdir(parents=True, exist_ok=True)
        stamp = knowledge_ts.isoformat().replace(":", "-")
        path = qdir / f"{DATASET}_{year}_k={stamp}.parquet"
        df.write_parquet(path)
        return path

    def load_shares_current(
        self, tickers: list[str], knowledge_ts: dt.datetime
    ) -> int:
        """Snapshot current shares outstanding into its own dataset.

        One row per ticker, effective_date = snapshot date (that is when
        the fact is true — using it for history would be look-ahead).
        Returns the count of tickers that resolved to a value.
        """
        values = [self.client.shares_outstanding(t) for t in tickers]
        df = pl.DataFrame(
            {
                "security_id": pl.Series(tickers, dtype=pl.String),
                "effective_date": pl.Series(
                    [knowledge_ts.date()] * len(tickers), dtype=pl.Date
                ),
                "shares_outstanding_current": pl.Series(values, dtype=pl.Float64),
            }
        )
        self.store.append(SHARES_DATASET, df, knowledge_ts=knowledge_ts)
        return sum(1 for v in values if v is not None)


def select_liquid_tickers(store: PITStore, top_n: int, year: int) -> list[str]:
    """Top ``top_n`` tickers by median daily dollar volume in ``year``.

    Fetch triage for the two-phase backfill (phase 1 pulls one recent year
    for everything; phase 2 backfills history only for these) — NOT the
    tradeable universe, which part 3 derives with PIT membership rules.
    Median, not mean: one spike day should not buy a backfill slot.
    """
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    ranked = (
        store.asof(DATASET, now, keys=["security_id"])
        .filter(pl.col("effective_date").dt.year() == year)
        .group_by("security_id")
        .agg(pl.col("dollar_volume").median().alias("median_dv"))
        .sort("median_dv", descending=True, nulls_last=True)
        .head(top_n)
        .collect()
    )
    return ranked["security_id"].to_list()


def read_tickers_file(path: str) -> list[str]:
    """One ticker per line; blank lines and '#' comments skipped."""
    with open(path, encoding="utf-8") as fh:
        return [
            ln.strip()
            for ln in fh
            if ln.strip() and not ln.strip().startswith("#")
        ]


def fetch_listed_tickers(fetch_text=None) -> list[str]:
    """Listed US common-stock-ish tickers from the NASDAQ Trader symbol files.

    Excludes test issues and ETFs (flags in the files). Symbols with '$'
    (preferreds/warrants/units in ACT notation) are skipped; '.' class
    separators become '-' (yfinance convention, e.g. BRK.B -> BRK-B).
    ``fetch_text`` is injectable for offline tests.
    """
    if fetch_text is None:
        import ssl

        import certifi  # via requests/yfinance; framework Pythons ship no CA bundle

        ctx = ssl.create_default_context(cafile=certifi.where())

        def fetch_text(url: str) -> str:
            with urllib.request.urlopen(url, timeout=30, context=ctx) as resp:
                return resp.read().decode("utf-8", errors="replace")

    tickers: set[str] = set()
    for url, symbol_col in (
        (NASDAQ_LISTED_URL, "Symbol"),
        (OTHER_LISTED_URL, "ACT Symbol"),
    ):
        lines = [ln for ln in fetch_text(url).splitlines() if ln.strip()]
        header = lines[0].split("|")
        idx = {name: header.index(name) for name in (symbol_col, "Test Issue", "ETF")}
        for line in lines[1:]:
            if line.startswith("File Creation Time"):
                continue  # footer
            row = line.split("|")
            if len(row) <= max(idx.values()):
                continue
            if row[idx["Test Issue"]] != "N" or row[idx["ETF"]] != "N":
                continue
            sym = row[idx[symbol_col]].strip()
            if not sym or "$" in sym:
                continue
            tickers.add(sym.replace(".", "-"))
    return sorted(tickers)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load yfinance daily bars into the lake"
    )
    parser.add_argument("--start", type=int, default=2011)
    parser.add_argument("--end", type=int, default=dt.date.today().year)
    parser.add_argument("--lake", default="lake")
    parser.add_argument("--chunk-size", type=int, default=200)
    parser.add_argument(
        "--pause", type=float, default=2.0, help="seconds between chunk downloads"
    )
    parser.add_argument(
        "--max-retries", type=int, default=5, help="retries per throttled chunk"
    )
    parser.add_argument(
        "--backoff",
        type=float,
        default=60.0,
        help="base backoff seconds, doubles per retry (60, 120, 240, ...)",
    )
    parser.add_argument(
        "--shares",
        action="store_true",
        help="also snapshot current shares outstanding (slow: one call/ticker)",
    )
    parser.add_argument(
        "--no-threads",
        action="store_true",
        help="sequential per-ticker fetch (~1-2 req/s) — survives Yahoo throttle",
    )
    parser.add_argument(
        "--tickers-file",
        default=None,
        help="one ticker per line; skips the NASDAQ Trader universe fetch",
    )
    parser.add_argument(
        "--select-top",
        type=int,
        default=None,
        metavar="N",
        help="no download: print top-N tickers by median dollar volume and exit",
    )
    parser.add_argument(
        "--select-year",
        type=int,
        default=dt.date.today().year - 1,
        help="ranking year for --select-top (default: last complete year)",
    )
    args = parser.parse_args(argv)

    if args.select_top is not None:
        # Redirect-friendly: tickers only, one per line, nothing else on stdout.
        for t in select_liquid_tickers(
            PITStore(args.lake), args.select_top, args.select_year
        ):
            print(t)
        return 0

    if args.tickers_file is not None:
        tickers = read_tickers_file(args.tickers_file)
        print(f"{len(tickers)} tickers from {args.tickers_file}")
    else:
        print("fetching listed-ticker universe from NASDAQ Trader...")
        tickers = fetch_listed_tickers()
        print(f"{len(tickers)} tickers after test-issue/ETF filter")

    client = YFinanceClient(
        pause_s=args.pause,
        max_retries=args.max_retries,
        backoff_base_s=args.backoff,
        threads=not args.no_threads,
    )
    loader = YFinanceDailyLoader(client, PITStore(args.lake))
    # Naive UTC, matching the store's own load_ts convention.
    knowledge_ts = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    t0 = time.perf_counter()
    total_rows = 0
    quarantined = 0
    for year in range(args.start, args.end + 1):
        try:
            report = loader.load_year(
                year, tickers, knowledge_ts, chunk_size=args.chunk_size
            )
        except Exception as exc:  # keep going; re-run of a year is idempotent
            print(f"{year}: FAILED — {exc}")
            quarantined += 1
            continue
        total_rows += report.rows
        status = "ok" if report.ok else f"QUARANTINED ({'; '.join(report.failures)})"
        print(
            f"{year}: {report.rows} rows, {report.trading_days} days, "
            f"{report.ret_outliers} ret outliers, "
            f"{report.fetch_failures} tickers missing, "
            f"nulls={report.null_counts} — {status}"
        )
        if not report.ok:
            quarantined += 1

    elapsed = time.perf_counter() - t0
    rate = total_rows / elapsed if elapsed > 0 else 0.0
    print(
        f"done: {total_rows} rows in {elapsed:.1f}s ({rate:,.0f} rows/s), "
        f"{quarantined} year(s) quarantined/failed — record in docs/METRICS.md"
    )

    if args.shares:
        got = loader.load_shares_current(tickers, knowledge_ts)
        print(f"shares snapshot: {got}/{len(tickers)} tickers resolved")

    return 1 if quarantined else 0


if __name__ == "__main__":
    raise SystemExit(main())
