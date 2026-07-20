import datetime as dt

import polars as pl
import pytest

from research.data import PITStore
from research.risk.exposures import build_exposure_matrix

BARS_DATASET = "yfinance_daily"
K1 = dt.datetime(2026, 3, 1, 22, 0)


def trading_days(n: int, start: dt.date = dt.date(2020, 1, 1)) -> list[dt.date]:
    out = []
    d = start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def ret_bars(security_id: str, rets: list[float], dates: list[dt.date]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "security_id": [security_id] * len(dates),
            "effective_date": dates,
            "ret": rets,
        }
    )


@pytest.fixture()
def store(tmp_path):
    return PITStore(tmp_path / "lake")


def test_build_exposure_matrix_shape_and_sector_dummies(store):
    dates = trading_days(300)  # enough for momentum (273) and low_vol (252)
    store.append(
        BARS_DATASET,
        pl.concat(
            [
                ret_bars("AAA", [0.002 if i % 2 == 0 else -0.001 for i in range(len(dates))], dates),
                ret_bars("BBB", [0.006 if i % 2 == 0 else -0.003 for i in range(len(dates))], dates),
            ]
        ),
        knowledge_ts=K1,
    )
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])
    sectors = pl.DataFrame(
        {"security_id": ["AAA", "BBB"], "sector": ["Technology", "Energy"]}
    )

    result = build_exposure_matrix(bars, sectors, dates[-1], ["AAA", "BBB"])

    # "Energy" < "Technology" alphabetically -> Energy is the dropped reference.
    assert "sector_Technology" in result.columns
    assert "sector_Energy" not in result.columns
    assert result["market"].to_list() == [1.0, 1.0]
    aaa = result.filter(pl.col("security_id") == "AAA")
    bbb = result.filter(pl.col("security_id") == "BBB")
    assert aaa["sector_Technology"][0] == 1.0
    assert bbb["sector_Technology"][0] == 0.0
    # z-scored: 2 symmetric points -> mean 0.
    assert result["momentum"].mean() == pytest.approx(0.0, abs=1e-9)
    assert result["low_vol"].mean() == pytest.approx(0.0, abs=1e-9)


def test_security_missing_sector_is_excluded(store):
    dates = trading_days(300)
    store.append(
        BARS_DATASET,
        pl.concat(
            [
                ret_bars("AAA", [0.002 if i % 2 == 0 else -0.001 for i in range(len(dates))], dates),
                ret_bars("BBB", [0.006 if i % 2 == 0 else -0.003 for i in range(len(dates))], dates),
            ]
        ),
        knowledge_ts=K1,
    )
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])
    sectors = pl.DataFrame({"security_id": ["AAA"], "sector": ["Technology"]})  # BBB missing

    result = build_exposure_matrix(bars, sectors, dates[-1], ["AAA", "BBB"])
    assert result["security_id"].to_list() == ["AAA"]


def test_null_sector_value_excluded_not_crashed(store):
    # Real bug (2026-07-19): 3 real tickers in yfinance_sector_current have
    # sector=None (unresolved by yfinance's .info) — sorted(unique) on a
    # list containing None raised TypeError against the real lake. Row is
    # PRESENT (unlike test_security_missing_sector_is_excluded's absent row).
    dates = trading_days(300)
    store.append(
        BARS_DATASET,
        pl.concat(
            [
                ret_bars("AAA", [0.002 if i % 2 == 0 else -0.001 for i in range(len(dates))], dates),
                ret_bars("BBB", [0.006 if i % 2 == 0 else -0.003 for i in range(len(dates))], dates),
            ]
        ),
        knowledge_ts=K1,
    )
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])
    sectors = pl.DataFrame(
        {"security_id": ["AAA", "BBB"], "sector": ["Technology", None]}
    )

    result = build_exposure_matrix(bars, sectors, dates[-1], ["AAA", "BBB"])
    assert result["security_id"].to_list() == ["AAA"]


def test_empty_when_no_members_have_enough_history(store):
    dates = trading_days(50)  # well under momentum's 273-day requirement
    store.append(BARS_DATASET, ret_bars("AAA", [0.001] * len(dates), dates), knowledge_ts=K1)
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])
    sectors = pl.DataFrame({"security_id": ["AAA"], "sector": ["Technology"]})

    result = build_exposure_matrix(bars, sectors, dates[-1], ["AAA"])
    assert result.is_empty()
