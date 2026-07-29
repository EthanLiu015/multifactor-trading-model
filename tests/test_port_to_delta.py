import datetime as dt

import polars as pl
import pytest

from research.data.port_to_delta import port_dataset
from research.data.store import PITStore


@pytest.fixture()
def store(tmp_path):
    return PITStore(tmp_path / "lake")


def bars(security_id: str, price: float) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "security_id": [security_id],
            "effective_date": [dt.date(2026, 1, 2)],
            "close": [price],
        }
    )


class FakeSparkColumn:
    def cast(self, dtype):
        return self


class FakeSparkDataFrame:
    """Stands in for a real Spark DataFrame: delegates to the underlying
    pandas frame (so `.columns`/`len()` assertions below still work) but
    also answers `withColumn`/column-indexing-then-`.cast` (both no-ops
    here) since port_dataset calls them unconditionally — the real cast
    behavior is Spark/Delta's concern, not something this offline test
    needs to exercise.
    """

    def __init__(self, pdf):
        self._pdf = pdf

    def __getattr__(self, name):
        return getattr(self._pdf, name)

    def __len__(self):
        return len(self._pdf)

    def __getitem__(self, key):
        return FakeSparkColumn()

    def withColumn(self, name, col):
        return self


class FakeSpark:
    def createDataFrame(self, pdf):
        return FakeSparkDataFrame(pdf)


class FakeDeltaStore:
    def __init__(self):
        self.spark = FakeSpark()
        self.calls = []  # (dataset, knowledge_ts, keys, pdf)

    def append(self, dataset, df, knowledge_ts, keys):
        self.calls.append((dataset, knowledge_ts, keys, df))


K1 = dt.datetime(2026, 1, 10, 22, 0)
K2 = dt.datetime(2026, 2, 20, 22, 0)


def test_port_preserves_every_knowledge_ts_batch(store):
    store.append("prices_daily", bars("AAPL", 100.0), knowledge_ts=K1)
    store.append("prices_daily", bars("MSFT", 200.0), knowledge_ts=K2)

    delta = FakeDeltaStore()
    total = port_dataset(store, delta, "prices_daily", keys=["security_id"])

    assert total == 2
    assert len(delta.calls) == 2  # one append per distinct knowledge_ts, not one big blob
    ts_seen = {ts for _, ts, _, _ in delta.calls}
    assert ts_seen == {K1, K2}
    for dataset, _, keys, pdf in delta.calls:
        assert dataset == "prices_daily"
        assert keys == ["security_id"]
        # knowledge_ts/load_ts stripped before handing off — DeltaPITStore.append
        # re-stamps them itself and rejects a df that already has them.
        assert "knowledge_ts" not in pdf.columns
        assert "load_ts" not in pdf.columns


def test_port_combines_parts_under_one_knowledge_ts(store):
    store.append("prices_daily", bars("AAPL", 100.0), knowledge_ts=K1, part="2015")
    store.append("prices_daily", bars("MSFT", 101.0), knowledge_ts=K1, part="2016")

    delta = FakeDeltaStore()
    total = port_dataset(store, delta, "prices_daily", keys=["security_id"])

    assert total == 2
    # PITStore's `part` is a physical file-split with no PIT meaning — both
    # parts share one knowledge_ts, so they collapse into a single append.
    assert len(delta.calls) == 1
    assert len(delta.calls[0][3]) == 2
