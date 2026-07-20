import datetime as dt

import polars as pl
import pytest

from research.data import PITStore
from research.universe import (
    BARS_DATASET,
    UNIVERSE_DATASET,
    build_snapshot,
    build_universe,
    main,
    month_end_trading_days,
)

K1 = dt.datetime(2026, 3, 1, 22, 0)
K_LATE = dt.datetime(2026, 6, 1, 22, 0)

# Mon-Fri trading days across Jan+Feb 2026 (Jan 1 skipped as a holiday).
DATES = [
    d
    for d in (dt.date(2026, 1, 2) + dt.timedelta(days=i) for i in range(58))
    if d.weekday() < 5
]


def bars_frame(rows: dict[str, tuple[float, float]]) -> pl.DataFrame:
    """{security_id: (close, dollar_volume)} -> one row per DATES entry."""
    return pl.DataFrame(
        {
            "security_id": [s for s in rows for _ in DATES],
            "effective_date": [d for _ in rows for d in DATES],
            "close": [px for (px, _) in rows.values() for _ in DATES],
            "dollar_volume": [dv for (_, dv) in rows.values() for _ in DATES],
        }
    )


@pytest.fixture()
def store(tmp_path):
    return PITStore(tmp_path / "lake")


def test_month_end_trading_days_picks_last_trade_date(store):
    store.append(BARS_DATASET, bars_frame({"AAA": (10.0, 1e6)}), knowledge_ts=K1)
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])
    assert month_end_trading_days(bars) == [dt.date(2026, 1, 30), dt.date(2026, 2, 27)]


def test_ranks_by_median_dollar_volume_and_cuts_top_n(store):
    df = bars_frame({"BIG": (50.0, 9e6), "MID": (50.0, 5e6), "SML": (50.0, 1e6)})
    # One spike day for SML: median must ignore it (mean would not).
    df = df.with_columns(
        pl.when(
            (pl.col("security_id") == "SML")
            & (pl.col("effective_date") == DATES[-1])
        )
        .then(1e12)
        .otherwise(pl.col("dollar_volume"))
        .alias("dollar_volume")
    )
    store.append(BARS_DATASET, df, knowledge_ts=K1)
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])
    snap = build_snapshot(
        bars, DATES[-1], top_n=2, adv_window=20, min_price=5.0, min_days=10
    )
    assert snap["security_id"].to_list() == ["BIG", "MID"]
    assert snap["rank"].to_list() == [1, 2]
    assert snap["effective_date"].unique().to_list() == [DATES[-1]]


def test_price_filter_uses_unadjusted_close(store):
    df = bars_frame({"LIQ": (50.0, 9e6), "PNY": (4.0, 8e6)})
    store.append(BARS_DATASET, df, knowledge_ts=K1)
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])
    snap = build_snapshot(
        bars, DATES[-1], top_n=10, adv_window=20, min_price=5.0, min_days=10
    )
    assert snap["security_id"].to_list() == ["LIQ"]  # PNY: $4 < $5 floor


def test_coverage_filter_excludes_sparse_ticker(store):
    full = bars_frame({"FUL": (20.0, 5e6)})
    sparse = bars_frame({"SPR": (20.0, 9e6)}).head(3)  # trades 3 of 40 days
    store.append(BARS_DATASET, pl.concat([full, sparse]), knowledge_ts=K1)
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])
    snap = build_snapshot(
        bars, DATES[-1], top_n=10, adv_window=20, min_price=5.0, min_days=10
    )
    assert snap["security_id"].to_list() == ["FUL"]


def test_short_history_returns_empty(store):
    store.append(BARS_DATASET, bars_frame({"AAA": (10.0, 1e6)}), knowledge_ts=K1)
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])
    snap = build_snapshot(
        bars, DATES[-1], top_n=10, adv_window=60, min_price=5.0, min_days=42
    )
    assert snap.is_empty()  # only 41 trading days exist in DATES


def test_knowledge_cutoff_hides_later_loads(store):
    store.append(BARS_DATASET, bars_frame({"OLD": (20.0, 5e6)}), knowledge_ts=K1)
    late = bars_frame({"NEW": (20.0, 9e6)})
    store.append(BARS_DATASET, late, knowledge_ts=K_LATE, part="late")
    uni = build_universe(
        store, 2026, 2026, top_n=10, adv_window=20, min_days=10, knowledge_ts=K1
    )
    assert uni["security_id"].unique().to_list() == ["OLD"]


def test_build_universe_one_snapshot_per_month(store):
    store.append(BARS_DATASET, bars_frame({"AAA": (10.0, 1e6)}), knowledge_ts=K1)
    uni = build_universe(store, 2026, 2026, top_n=10, adv_window=20, min_days=10)
    assert uni["effective_date"].unique().sort().to_list() == [
        dt.date(2026, 1, 30),
        dt.date(2026, 2, 27),
    ]


def test_main_writes_universe_dataset(store, capsys):
    store.append(BARS_DATASET, bars_frame({"AAA": (10.0, 1e6)}), knowledge_ts=K1)
    rc = main(
        [
            "--lake",
            str(store.root),
            "--start",
            "2026",
            "--end",
            "2026",
            "--top",
            "10",
            "--window",
            "20",
            "--min-days",
            "10",
        ]
    )
    assert rc == 0
    assert "done: 2 snapshots" in capsys.readouterr().out
    stored = store.scan(UNIVERSE_DATASET).collect()
    assert stored["effective_date"].n_unique() == 2
    assert set(stored.columns) >= {"security_id", "rank", "median_dollar_volume"}


def test_main_empty_lake_fails(store, capsys):
    store.append(  # one bar only: never satisfies min_days
        BARS_DATASET,
        bars_frame({"AAA": (10.0, 1e6)}).head(1),
        knowledge_ts=K1,
    )
    rc = main(["--lake", str(store.root), "--start", "2026", "--end", "2026"])
    assert rc == 1
