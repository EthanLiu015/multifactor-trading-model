import datetime as dt
import os
import uuid

import pytest

pytest.importorskip("databricks.connect")

from databricks.connect import DatabricksSession  # noqa: E402

from research.data.delta_store import DeltaPITStore  # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABRICKS_TOKEN"),
    reason="requires a live Databricks connection (DATABRICKS_TOKEN unset)",
)

CATALOG = "mfts"
SCHEMA = "research"


@pytest.fixture(scope="module")
def spark():
    return DatabricksSession.builder.serverless(True).getOrCreate()


@pytest.fixture()
def store(spark):
    return DeltaPITStore(spark, CATALOG, SCHEMA)


@pytest.fixture()
def dataset():
    # Unique per test run so re-runs never collide with a prior run's table.
    return f"test_prices_daily_{uuid.uuid4().hex[:8]}"


def bars(spark, price: float):
    return spark.createDataFrame(
        [{"security_id": "AAPL", "effective_date": dt.date(2026, 1, 2), "close": price}]
    )


K1 = dt.datetime(2026, 1, 10, 22, 0)
K2 = dt.datetime(2026, 2, 20, 22, 0)


def test_round_trip(spark, store, dataset):
    store.append(dataset, bars(spark, 100.0), knowledge_ts=K1, keys=["security_id"])
    out = store.scan(dataset).collect()
    assert len(out) == 1
    assert out[0]["close"] == 100.0
    assert out[0]["knowledge_ts"] == K1


def test_asof_point_in_time(spark, store, dataset):
    store.append(dataset, bars(spark, 100.0), knowledge_ts=K1, keys=["security_id"])  # v1
    store.append(dataset, bars(spark, 99.5), knowledge_ts=K2, keys=["security_id"])  # revision

    keys = ["security_id"]
    before = store.asof(dataset, dt.datetime(2026, 1, 5), keys).collect()
    assert len(before) == 0

    mid = store.asof(dataset, dt.datetime(2026, 1, 15), keys).collect()
    assert len(mid) == 1
    assert mid[0]["close"] == 100.0

    late = store.asof(dataset, dt.datetime(2026, 3, 1), keys).collect()
    assert len(late) == 1
    assert late[0]["close"] == 99.5


def test_append_idempotent(spark, store, dataset):
    store.append(dataset, bars(spark, 100.0), knowledge_ts=K1, keys=["security_id"])
    store.append(dataset, bars(spark, 100.0), knowledge_ts=K1, keys=["security_id"])  # re-run
    out = store.scan(dataset).collect()
    assert len(out) == 1


def test_append_rejects_bad_schema(spark, store, dataset):
    no_eff = spark.createDataFrame([{"security_id": "AAPL", "close": 1.0}])
    with pytest.raises(ValueError, match="effective_date"):
        store.append(dataset, no_eff, knowledge_ts=K1, keys=["security_id"])
