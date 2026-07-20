import datetime as dt

import polars as pl
import pytest

from research.data import PITStore
from research.security_master import (
    BARS_DATASET,
    DATASET,
    SCHEMA,
    build_ticker_segments,
    empty_master,
    main,
    resolve_securities,
    resolve_security,
)

K1 = dt.datetime(2026, 7, 14, 12, 0)


@pytest.fixture()
def store(tmp_path):
    return PITStore(tmp_path / "lake")


def mapping_row(
    internal_id: int,
    id_value: str,
    valid_from: dt.date,
    valid_to: dt.date | None,
    id_type: str = "ticker",
    source: str = "yfinance_daily",
) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "effective_date": pl.Series([valid_from], dtype=pl.Date),
            "internal_id": pl.Series([internal_id], dtype=pl.UInt32),
            "id_type": [id_type],
            "id_value": [id_value],
            "valid_to": pl.Series([valid_to], dtype=pl.Date),
            "source": [source],
        }
    )


def test_empty_master_has_declared_schema():
    empty = empty_master()
    assert empty.shape == (0, len(SCHEMA))
    assert empty.schema == pl.Schema(SCHEMA)


def test_round_trip_through_store(store):
    row = mapping_row(1, "AAPL", dt.date(2011, 1, 1), None)
    store.append(DATASET, row, knowledge_ts=K1)
    out = store.scan(DATASET).collect()
    assert out.shape[0] == 1
    assert out["internal_id"][0] == 1
    assert out["id_value"][0] == "AAPL"
    assert out["valid_to"][0] is None
    assert out["knowledge_ts"][0] == K1


def test_store_rejects_missing_effective_date(store):
    bad = mapping_row(1, "AAPL", dt.date(2011, 1, 1), None).drop("effective_date")
    with pytest.raises(ValueError, match="effective_date"):
        store.append(DATASET, bad, knowledge_ts=K1)


def test_reused_ticker_resolves_to_distinct_internal_ids_by_date(store):
    """DESIGN.md 1b: a ticker can point at two unrelated companies over time.

    Company A held "ZVZZT" 2012-01-01..2015-06-30 (internal_id=10); after a
    gap the exchange reassigned it to Company B from 2019-01-01 onward
    (internal_id=20, still current: valid_to=None). Both rows must survive
    independently, and resolving "as of" a date must land on the right one.
    """
    old = mapping_row(10, "ZVZZT", dt.date(2012, 1, 1), dt.date(2015, 6, 30))
    new = mapping_row(20, "ZVZZT", dt.date(2019, 1, 1), None)
    store.append(DATASET, old, knowledge_ts=K1, part="old")
    store.append(DATASET, new, knowledge_ts=K1, part="new")

    rows = store.asof(DATASET, K1, keys=["internal_id"]).collect()
    assert sorted(rows["internal_id"].to_list()) == [10, 20]

    def resolve(as_of: dt.date) -> int | None:
        hit = rows.filter(
            (pl.col("id_value") == "ZVZZT")
            & (pl.col("effective_date") <= as_of)
            & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= as_of))
        )
        return hit["internal_id"][0] if hit.height else None

    assert resolve(dt.date(2013, 6, 1)) == 10  # Company A era
    assert resolve(dt.date(2017, 1, 1)) is None  # gap: ticker unassigned
    assert resolve(dt.date(2020, 1, 1)) == 20  # Company B era


def bars_row(ticker: str, dates: list[dt.date]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "security_id": [ticker] * len(dates),
            "effective_date": pl.Series(dates, dtype=pl.Date),
        }
    )


def test_build_ticker_segments_splits_on_long_gap(store):
    old_run = [dt.date(2012, 1, 1), dt.date(2012, 1, 2)]
    new_run = [dt.date(2019, 6, 1), dt.date(2019, 6, 2)]
    store.append(BARS_DATASET, bars_row("ZVZZT", old_run + new_run), knowledge_ts=K1)
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])

    out = build_ticker_segments(bars, gap_days=90)
    seg = out.filter(pl.col("id_value") == "ZVZZT").sort("effective_date")
    assert seg.height == 2
    assert seg["internal_id"].to_list()[0] != seg["internal_id"].to_list()[1]
    assert seg["effective_date"].to_list() == [dt.date(2012, 1, 1), dt.date(2019, 6, 1)]
    assert seg["valid_to"][0] == dt.date(2012, 1, 2)  # ended before the lake's last date
    assert seg["valid_to"][1] is None  # reaches the lake's most recent date: current


def test_build_ticker_segments_no_gap_stays_one_segment(store):
    store.append(
        BARS_DATASET,
        bars_row("AAPL", [dt.date(2020, 1, 2), dt.date(2020, 1, 3), dt.date(2020, 1, 6)]),
        knowledge_ts=K1,
    )
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])
    out = build_ticker_segments(bars, gap_days=90)
    assert out.height == 1
    assert out["valid_to"][0] is None


def test_build_ticker_segments_internal_id_ordered_by_valid_from(store):
    df = pl.concat(
        [
            bars_row("LATE", [dt.date(2020, 1, 2)]),
            bars_row("EARLY", [dt.date(2011, 1, 3)]),
        ]
    )
    store.append(BARS_DATASET, df, knowledge_ts=K1)
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])
    out = build_ticker_segments(bars, gap_days=90).sort("internal_id")
    assert out["id_value"].to_list() == ["EARLY", "LATE"]


def test_main_writes_security_master_and_reports_reuse(store, capsys):
    old_run = [dt.date(2012, 1, 1), dt.date(2012, 1, 2)]
    new_run = [dt.date(2019, 6, 1), dt.date(2019, 6, 2)]
    store.append(BARS_DATASET, bars_row("ZVZZT", old_run + new_run), knowledge_ts=K1)
    store.append(BARS_DATASET, bars_row("AAPL", new_run), knowledge_ts=K1, part="aapl")

    rc = main(["--lake", str(store.root), "--gap-days", "90"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "done: 3 identity segments, 2 tickers, 1 tickers with >1 segment" in out

    stored = store.scan(DATASET).collect()
    assert stored.height == 3
    assert set(stored.columns) >= set(SCHEMA)


def test_resolve_securities_panel_resolves_multiple_and_drops_gap(store):
    old = mapping_row(10, "ZVZZT", dt.date(2012, 1, 1), dt.date(2015, 6, 30))
    new = mapping_row(20, "ZVZZT", dt.date(2019, 1, 1), None)
    aapl = mapping_row(1, "AAPL", dt.date(2011, 1, 1), None)
    store.append(DATASET, old, knowledge_ts=K1, part="old")
    store.append(DATASET, new, knowledge_ts=K1, part="new")
    store.append(DATASET, aapl, knowledge_ts=K1, part="aapl")

    out = resolve_securities(
        store, ["ZVZZT", "AAPL", "NOPE"], dt.date(2013, 6, 1), knowledge_ts=K1
    )
    assert out.height == 2  # NOPE never existed; not an error, just absent
    got = dict(zip(out["id_value"].to_list(), out["internal_id"].to_list()))
    assert got == {"ZVZZT": 10, "AAPL": 1}

    later = resolve_securities(store, ["ZVZZT"], dt.date(2020, 1, 1), knowledge_ts=K1)
    assert later["internal_id"].to_list() == [20]

    in_gap = resolve_securities(store, ["ZVZZT"], dt.date(2017, 1, 1), knowledge_ts=K1)
    assert in_gap.height == 0


def test_resolve_security_scalar_matches_panel(store):
    aapl = mapping_row(1, "AAPL", dt.date(2011, 1, 1), None)
    store.append(DATASET, aapl, knowledge_ts=K1)
    assert resolve_security(store, "AAPL", dt.date(2020, 1, 1), knowledge_ts=K1) == 1
    assert (
        resolve_security(store, "NOPE", dt.date(2020, 1, 1), knowledge_ts=K1) is None
    )
