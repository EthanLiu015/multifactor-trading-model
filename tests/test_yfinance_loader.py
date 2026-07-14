import datetime as dt

import pandas as pd
import pytest

from research.data.loaders.yfinance_daily import (
    DATASET,
    SHARES_DATASET,
    YFinanceClient,
    YFinanceDailyLoader,
    _rate_limited_errors,
    fetch_listed_tickers,
    read_tickers_file,
    select_liquid_tickers,
)
from research.data.store import PITStore

K = dt.datetime(2026, 7, 13, 12, 0)

# Audit's trading-day bounds only apply to complete (past) years, so happy-path
# fixtures use the current year where a tiny frame is legal.
YEAR = dt.date.today().year
D1, D2 = dt.date(YEAR, 1, 5), dt.date(YEAR, 1, 6)


def wide(data):
    """{ticker: {date: (close, adj_close, volume)}} -> yfinance wide frame."""
    per_ticker = {}
    for ticker, days in data.items():
        idx = pd.to_datetime(sorted(days))
        rows = [days[d] for d in sorted(days)]
        per_ticker[ticker] = pd.DataFrame(
            rows, index=idx, columns=["Close", "Adj Close", "Volume"]
        )
    return pd.concat(per_ticker, axis=1)  # MultiIndex columns (ticker, field)


class FakeClient:
    def __init__(self, data, shares=None, boom=()):
        self.data = data  # full universe; download slices by request
        self.shares = shares or {}
        self.boom = set(boom)  # tickers whose chunk raises

    def download(self, tickers, start, end):
        if self.boom & set(tickers):
            raise ConnectionError("simulated fetch failure")
        got = {t: self.data[t] for t in tickers if t in self.data}
        return wide(got) if got else pd.DataFrame()

    def shares_outstanding(self, ticker):
        return self.shares.get(ticker)


@pytest.fixture()
def store(tmp_path):
    return PITStore(tmp_path / "lake")


def test_happy_path_lands_in_store(store):
    client = FakeClient(
        {
            "AAA": {D1: (10.0, 100.0, 1000.0), D2: (10.1, 101.0, 1100.0)},
            "BBB": {D1: (20.0, 50.0, 500.0), D2: (20.2, 51.0, 600.0)},
        }
    )
    report = YFinanceDailyLoader(client, store).load_year(YEAR, ["AAA", "BBB"], K)

    assert report.ok
    assert report.rows == 4
    assert report.fetch_failures == 0
    out = (
        store.asof(DATASET, K, keys=["security_id"])
        .collect()
        .sort(["security_id", "effective_date"])
    )
    assert out.shape[0] == 4
    aaa = out.filter(out["security_id"] == "AAA")
    assert aaa["ret"][0] is None  # first bar of the chunk: no prior adj close
    assert aaa["ret"][1] == pytest.approx(101.0 / 100.0 - 1)  # from Adj Close
    assert aaa["dollar_volume"][1] == pytest.approx(10.1 * 1100.0)  # raw close
    assert out["knowledge_ts"][0] == K


def test_rerun_same_year_is_idempotent(store):
    client = FakeClient({"AAA": {D1: (10.0, 100.0, 1000.0)}})
    loader = YFinanceDailyLoader(client, store)
    loader.load_year(YEAR, ["AAA"], K)
    loader.load_year(YEAR, ["AAA"], K)
    assert store.scan(DATASET).collect().shape[0] == 1


def test_grid_artifacts_dropped_partial_nulls_kept(store):
    client = FakeClient(
        {
            "AAA": {D1: (10.0, 100.0, 1000.0), D2: (10.1, 101.0, 1100.0)},
            # BBB listed later: no D1 bar -> concat grid gives all-null row
            "BBB": {D2: (20.0, 50.0, 500.0)},
            # CCC halted on D2: null close, volume present -> real row, kept
            "CCC": {D1: (30.0, 60.0, 700.0), D2: (None, None, 0.0)},
        }
    )
    report = YFinanceDailyLoader(client, store).load_year(
        YEAR, ["AAA", "BBB", "CCC"], K
    )

    assert report.ok
    assert report.rows == 5  # 2 AAA + 1 BBB (D1 artifact dropped) + 2 CCC
    assert report.null_counts["close"] == 1  # CCC's halted day survives


def test_fetch_failures_counted_not_fatal(store):
    client = FakeClient({"AAA": {D1: (10.0, 100.0, 1000.0)}})
    report = YFinanceDailyLoader(client, store).load_year(
        YEAR, ["AAA", "GONE"], K
    )
    assert report.ok  # missing ticker flagged, chunk still stored
    assert report.fetch_failures == 1
    assert store.scan(DATASET).collect().shape[0] == 1


def test_failed_chunk_skipped_others_land(store):
    client = FakeClient(
        {"AAA": {D1: (10.0, 100.0, 1000.0)}, "BAD": {D1: (1.0, 1.0, 1.0)}},
        boom={"BAD"},
    )
    # chunk_size=1 -> BAD isolated in its own failing chunk
    report = YFinanceDailyLoader(client, store).load_year(
        YEAR, ["AAA", "BAD"], K, chunk_size=1
    )
    assert report.ok
    assert report.rows == 1
    assert report.fetch_failures == 1


def test_duplicate_rows_quarantined_not_stored(store):
    dup = wide({"AAA": {D1: (10.0, 100.0, 1000.0)}})
    dup = pd.concat([dup, dup])  # same (ticker, date) twice

    class DupClient(FakeClient):
        def download(self, tickers, start, end):
            return dup

    report = YFinanceDailyLoader(DupClient({}), store).load_year(YEAR, ["AAA"], K)
    assert not report.ok
    assert "duplicate" in report.failures[0]
    qfiles = list((store.root / "_quarantine").glob("*.parquet"))
    assert len(qfiles) == 1
    assert not (store.root / DATASET).exists()


def test_short_past_year_fails_audit(store):
    d = dt.date(2015, 1, 5)
    client = FakeClient({"AAA": {d: (10.0, 100.0, 1000.0)}})
    report = YFinanceDailyLoader(client, store).load_year(2015, ["AAA"], K)
    assert not report.ok
    assert "trading days" in report.failures[0]


def test_load_shares_current(store):
    client = FakeClient({}, shares={"AAA": 5_000_000.0, "BBB": None})
    got = YFinanceDailyLoader(client, store).load_shares_current(["AAA", "BBB"], K)

    assert got == 1
    out = store.asof(SHARES_DATASET, K, keys=["security_id"]).collect()
    assert out.shape[0] == 2
    aaa = out.filter(out["security_id"] == "AAA")
    assert aaa["shares_outstanding_current"][0] == 5_000_000.0
    assert aaa["effective_date"][0] == K.date()


NASDAQ_TXT = """Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
AAPL|Apple Inc.|Q|N|N|100|N|N
ZTEST|Test Listing|Q|Y|N|100|N|N
QQQ|Invesco QQQ Trust|Q|N|N|100|Y|N
File Creation Time: 0713202622:00|||||||"""

OTHER_TXT = """ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
BRK.B|Berkshire Hathaway Class B|N|BRK B|N|100|N|BRK=B
SPY|SPDR S&P 500|P|SPY|Y|100|N|SPY
ABC$P|Some Preferred|N|ABC$P|N|100|N|ABC-P
File Creation Time: 0713202622:00|||||||"""


def test_fetch_listed_tickers_filters_and_maps():
    texts = iter([NASDAQ_TXT, OTHER_TXT])
    got = fetch_listed_tickers(fetch_text=lambda url: next(texts))
    # test issues, ETFs, and '$' preferreds excluded; '.' -> '-' for yfinance
    assert got == ["AAPL", "BRK-B"]


def test_select_liquid_tickers_ranks_by_median_not_mean(store):
    import polars as pl

    def bars(ticker, dvs):
        return pl.DataFrame(
            {
                "security_id": [ticker] * len(dvs),
                "effective_date": pl.Series(
                    [dt.date(YEAR, 1, d + 2) for d in range(len(dvs))],
                    dtype=pl.Date,
                ),
                "dollar_volume": pl.Series(dvs, dtype=pl.Float64),
            }
        )

    # STEADY: median 100. SPIKE: one 10_000 day but median 10. SMALL: median 5.
    df = pl.concat(
        [
            bars("STEADY", [100.0, 100.0, 100.0]),
            bars("SPIKE", [10.0, 10.0, 10_000.0]),
            bars("SMALL", [5.0, 5.0, 5.0]),
        ]
    )
    store.append(DATASET, df, knowledge_ts=K)

    top2 = select_liquid_tickers(store, top_n=2, year=YEAR)
    assert top2 == ["STEADY", "SPIKE"]
    # off-year data must not count
    assert select_liquid_tickers(store, top_n=3, year=YEAR - 1) == []


def test_read_tickers_file(tmp_path):
    p = tmp_path / "tickers.txt"
    p.write_text("AAPL\n\n# comment\nBRK-B \n")
    assert read_tickers_file(str(p)) == ["AAPL", "BRK-B"]


def test_rate_limited_errors_detector():
    assert not _rate_limited_errors({})
    assert _rate_limited_errors(
        {"AAA": "YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')"}
    )
    # delisted-ticker errors are legitimate failures, never retried
    assert not _rate_limited_errors(
        {"GONE": "YFTzMissingError('$GONE: possibly delisted; no timezone found')"}
    )


def _patched_client(monkeypatch, download_results, errors_per_call):
    """YFinanceClient with fake yf.download, shared._ERRORS, recorded sleeps."""
    import yfinance
    import yfinance.shared as shared

    calls = {"n": 0}
    sleeps = []

    def fake_download(tickers, **kwargs):
        i = calls["n"]
        calls["n"] += 1
        monkeypatch.setattr(shared, "_ERRORS", errors_per_call[i], raising=False)
        return download_results[i]

    monkeypatch.setattr(yfinance, "download", fake_download)
    client = YFinanceClient(
        pause_s=1.0, max_retries=2, backoff_base_s=60.0, sleep=sleeps.append
    )
    return client, sleeps


THROTTLED = {"AAA": "YFRateLimitError('Too Many Requests. Rate limited.')"}


def test_client_backoff_then_success(monkeypatch):
    good = wide({"AAA": {D1: (10.0, 100.0, 1000.0)}})
    client, sleeps = _patched_client(
        monkeypatch,
        download_results=[pd.DataFrame(), pd.DataFrame(), good],
        errors_per_call=[THROTTLED, THROTTLED, {}],
    )
    out = client.download(["AAA"], f"{YEAR}-01-01", f"{YEAR + 1}-01-01")

    assert out is good
    # pause before each of 3 calls + exponential backoff after 2 throttles
    assert sleeps == [1.0, 60.0, 1.0, 120.0, 1.0]


def test_client_gives_up_after_max_retries(monkeypatch):
    from yfinance.exceptions import YFRateLimitError

    client, sleeps = _patched_client(
        monkeypatch,
        download_results=[pd.DataFrame()] * 3,
        errors_per_call=[THROTTLED] * 3,
    )
    with pytest.raises(YFRateLimitError):
        client.download(["AAA"], f"{YEAR}-01-01", f"{YEAR + 1}-01-01")
    assert sleeps == [1.0, 60.0, 1.0, 120.0, 1.0]  # no sleep after final attempt


def test_client_returns_legit_partial_without_retry(monkeypatch):
    good = wide({"AAA": {D1: (10.0, 100.0, 1000.0)}})
    delisted = {"GONE": "YFTzMissingError('possibly delisted')"}
    client, sleeps = _patched_client(
        monkeypatch, download_results=[good], errors_per_call=[delisted]
    )
    out = client.download(["AAA", "GONE"], f"{YEAR}-01-01", f"{YEAR + 1}-01-01")

    assert out is good
    assert sleeps == [1.0]  # single paced call, no backoff
