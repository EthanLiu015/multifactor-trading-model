import datetime as dt

import pandas as pd
import pytest

from research.data.loaders.crsp_daily import DATASET, SRC_COLUMNS, CRSPDailyLoader
from research.data.store import PITStore

K = dt.datetime(2026, 7, 13, 12, 0)

# Audit's trading-day bounds only apply to complete (past) years, so happy-path
# fixtures use the current year where a tiny frame is legal.
YEAR = dt.date.today().year


def row(permno=10001, date=f"{YEAR}-01-02", close=10.0, ret=0.01, vol=1000.0):
    return {
        "permno": permno,
        "dlycaldt": pd.Timestamp(date),
        "dlyclose": close,
        "dlyret": ret,
        "dlyretx": ret,
        "dlyvol": vol,
        "shrout": 500.0,  # thousands
    }


def frame(rows):
    return pd.DataFrame(rows, columns=list(SRC_COLUMNS))


class FakeConn:
    def __init__(self, pdf, columns=None):
        self.pdf = pdf
        self.columns = list(SRC_COLUMNS) + ["extra"] if columns is None else columns

    def raw_sql(self, sql, params=None, date_cols=None, **kwargs):
        return self.pdf

    def describe_table(self, library, table):
        return pd.DataFrame({"name": self.columns})


@pytest.fixture()
def store(tmp_path):
    return PITStore(tmp_path / "lake")


def test_happy_path_lands_in_store(store):
    conn = FakeConn(frame([row(), row(permno=10002, close=20.0)]))
    report = CRSPDailyLoader(conn, store).load_year(YEAR, K)

    assert report.ok
    assert report.rows == 2
    out = store.asof(DATASET, K, keys=["security_id"]).collect()
    assert out.shape[0] == 2
    aapl = out.filter(out["security_id"] == 10001)
    assert aapl["dollar_volume"][0] == 10.0 * 1000.0
    assert aapl["market_cap"][0] == 10.0 * 500.0 * 1000
    assert out["knowledge_ts"][0] == K


def test_rerun_same_year_is_idempotent(store):
    conn = FakeConn(frame([row()]))
    loader = CRSPDailyLoader(conn, store)
    loader.load_year(YEAR, K)
    loader.load_year(YEAR, K)
    assert store.scan(DATASET).collect().shape[0] == 1


def test_duplicate_rows_quarantined_not_stored(store):
    conn = FakeConn(frame([row(), row()]))  # same (permno, date) twice
    report = CRSPDailyLoader(conn, store).load_year(YEAR, K)

    assert not report.ok
    assert "duplicate" in report.failures[0]
    qfiles = list((store.root / "_quarantine").glob("*.parquet"))
    assert len(qfiles) == 1
    assert not (store.root / DATASET).exists()  # nothing written to the dataset


def test_short_past_year_fails_audit(store):
    conn = FakeConn(frame([row(date="2015-01-02")]))
    report = CRSPDailyLoader(conn, store).load_year(2015, K)
    assert not report.ok
    assert "trading days" in report.failures[0]


def test_nulls_and_outliers_flagged_not_dropped(store):
    rows = [
        row(),
        row(permno=10002, close=None),  # e.g. halted — null close
        row(permno=10003, ret=-9.99),  # outlier return
    ]
    report = CRSPDailyLoader(FakeConn(frame(rows)), store).load_year(YEAR, K)

    assert report.ok  # flagged, never dropped or failed
    assert report.null_counts["close"] == 1
    assert report.ret_outliers == 1
    assert store.scan(DATASET).collect().shape[0] == 3


def test_verify_schema():
    conn = FakeConn(frame([]))
    cols = CRSPDailyLoader(conn, PITStore("unused")).verify_schema()
    assert "permno" in cols

    bad = FakeConn(frame([]), columns=["permno", "dlycaldt"])
    with pytest.raises(RuntimeError, match="missing expected columns"):
        CRSPDailyLoader(bad, PITStore("unused")).verify_schema()
