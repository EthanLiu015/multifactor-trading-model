import datetime as dt

import polars as pl
import pytest

from research.data import PITStore


@pytest.fixture()
def store(tmp_path):
    return PITStore(tmp_path / "lake")


def bars(price: float) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "security_id": ["AAPL"],
            "effective_date": [dt.date(2026, 1, 2)],
            "close": [price],
        }
    )


K1 = dt.datetime(2026, 1, 10, 22, 0)
K2 = dt.datetime(2026, 2, 20, 22, 0)


def test_round_trip(store):
    store.append("prices_daily", bars(100.0), knowledge_ts=K1)
    out = store.scan("prices_daily").collect()
    assert out.shape[0] == 1
    assert out["close"][0] == 100.0
    assert out["knowledge_ts"][0] == K1
    assert "load_ts" in out.columns


def test_asof_point_in_time(store):
    store.append("prices_daily", bars(100.0), knowledge_ts=K1)  # v1
    store.append("prices_daily", bars(99.5), knowledge_ts=K2)  # revision

    keys = ["security_id"]
    # Before anything was known: empty.
    before = store.asof("prices_daily", dt.datetime(2026, 1, 5), keys).collect()
    assert before.shape[0] == 0
    # After v1, before revision: sees v1.
    mid = store.asof("prices_daily", dt.datetime(2026, 1, 15), keys).collect()
    assert mid.shape[0] == 1
    assert mid["close"][0] == 100.0
    # After revision: sees only v2.
    late = store.asof("prices_daily", dt.datetime(2026, 3, 1), keys).collect()
    assert late.shape[0] == 1
    assert late["close"][0] == 99.5


def test_append_idempotent(store):
    store.append("prices_daily", bars(100.0), knowledge_ts=K1)
    store.append("prices_daily", bars(100.0), knowledge_ts=K1)  # re-run same load
    out = store.scan("prices_daily").collect()
    assert out.shape[0] == 1


def test_append_parts_coexist_and_overwrite(store):
    p2015 = store.append("prices_daily", bars(100.0), knowledge_ts=K1, part="2015")
    p2016 = store.append("prices_daily", bars(101.0), knowledge_ts=K1, part="2016")
    assert p2015 != p2016
    assert store.scan("prices_daily").collect().shape[0] == 2

    # Re-running one part overwrites only that part's file.
    store.append("prices_daily", bars(100.5), knowledge_ts=K1, part="2015")
    out = store.scan("prices_daily").collect()
    assert out.shape[0] == 2
    assert sorted(out["close"].to_list()) == [100.5, 101.0]

    with pytest.raises(ValueError, match="part"):
        store.append("prices_daily", bars(1.0), knowledge_ts=K1, part="../evil")


def test_append_rejects_bad_schema(store):
    no_eff = pl.DataFrame({"security_id": ["AAPL"], "close": [1.0]})
    with pytest.raises(ValueError, match="effective_date"):
        store.append("prices_daily", no_eff, knowledge_ts=K1)

    stamped = bars(1.0).with_columns(pl.lit(K1).alias("knowledge_ts"))
    with pytest.raises(ValueError, match="stamped by the store"):
        store.append("prices_daily", stamped, knowledge_ts=K1)
