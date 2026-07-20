import datetime as dt
import math

import polars as pl
import pytest

from research.alpha.ic import (
    IcSummary,
    build_ic_series,
    compute_forward_returns,
    compute_ic,
    ic_summary,
)
from research.data import PITStore

BARS_DATASET = "yfinance_daily"
UNIVERSE_DATASET = "universe_monthly"
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


def test_forward_returns_matches_closed_form(store):
    horizon, c = 5, 0.001
    dates = trading_days(horizon + 10)  # extra days after rebuild_date
    store.append(BARS_DATASET, ret_bars("AAA", [c] * len(dates), dates), knowledge_ts=K1)
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])
    rebuild_date = dates[0]

    out = compute_forward_returns(bars, rebuild_date, horizon_days=horizon)

    expected = (1 + c) ** horizon - 1
    assert out["security_id"].to_list() == ["AAA"]
    assert out["forward_return"][0] == pytest.approx(expected)


def test_forward_returns_empty_when_insufficient_future_data(store):
    dates = trading_days(5)
    store.append(BARS_DATASET, ret_bars("AAA", [0.001] * len(dates), dates), knowledge_ts=K1)
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])

    out = compute_forward_returns(bars, dates[-1], horizon_days=21)  # no future rows at all
    assert out.is_empty()


def test_compute_ic_perfect_positive_correlation():
    d = dt.date(2020, 1, 1)
    signal_df = pl.DataFrame(
        {
            "effective_date": [d, d, d],
            "security_id": ["A", "B", "C"],
            "signal_value": [1.0, 2.0, 3.0],
        }
    )
    forward_df = pl.DataFrame(
        {
            "effective_date": [d, d, d],
            "security_id": ["A", "B", "C"],
            "forward_return": [0.10, 0.20, 0.30],
        }
    )
    assert compute_ic(signal_df, forward_df) == pytest.approx(1.0)


def test_compute_ic_perfect_negative_correlation():
    d = dt.date(2020, 1, 1)
    signal_df = pl.DataFrame(
        {
            "effective_date": [d, d, d],
            "security_id": ["A", "B", "C"],
            "signal_value": [1.0, 2.0, 3.0],
        }
    )
    forward_df = pl.DataFrame(
        {
            "effective_date": [d, d, d],
            "security_id": ["A", "B", "C"],
            "forward_return": [0.30, 0.20, 0.10],  # decreasing as signal increases
        }
    )
    assert compute_ic(signal_df, forward_df) == pytest.approx(-1.0)


def test_compute_ic_none_when_fewer_than_two_joined_rows():
    d = dt.date(2020, 1, 1)
    signal_df = pl.DataFrame(
        {"effective_date": [d], "security_id": ["A"], "signal_value": [1.0]}
    )
    forward_df = pl.DataFrame(
        {"effective_date": [d], "security_id": ["A"], "forward_return": [0.1]}
    )
    assert compute_ic(signal_df, forward_df) is None


def test_build_ic_series_restricts_to_universe_membership(store):
    dates = trading_days(10)
    d3, d6 = dates[3], dates[6]
    store.append(
        BARS_DATASET,
        pl.concat(
            [
                ret_bars("A", [0.001] * len(dates), dates),
                ret_bars("B", [0.002] * len(dates), dates),
            ]
        ),
        knowledge_ts=K1,
    )
    # A is a member on both rebuild dates; B only joins on the second.
    store.append(
        UNIVERSE_DATASET,
        pl.DataFrame(
            {"effective_date": [d3, d6, d6], "security_id": ["A", "A", "B"]}
        ),
        knowledge_ts=K1,
    )

    def fake_signal(bars, rebuild_date):
        return pl.DataFrame(
            {
                "effective_date": [rebuild_date, rebuild_date],
                "security_id": ["A", "B"],
                "signal_value": [1.0, 100.0],
            }
        )

    result = build_ic_series(
        store,
        {"fake": fake_signal},
        dates[0].year,
        dates[-1].year,
        horizon_days=2,
        knowledge_ts=K1,
    )

    assert set(result) == {"fake"}
    series = result["fake"]
    assert series.height == 2
    row_d3 = series.filter(pl.col("effective_date") == d3)
    row_d6 = series.filter(pl.col("effective_date") == d6)
    # Only A is a member on d3 -> compute_ic sees 1 joined row -> None.
    assert row_d3["ic"][0] is None
    # Both members on d6, B's higher signal matches its higher forward return.
    assert row_d6["ic"][0] == pytest.approx(1.0)


def test_ic_summary_basic():
    values = [0.1, 0.2, 0.3]
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    std = math.sqrt(variance)
    tstat = mean / (std / math.sqrt(len(values)))

    series = pl.DataFrame({"effective_date": [dt.date(2020, 1, i + 1) for i in range(3)], "ic": values})
    summary = ic_summary(series)

    assert summary == IcSummary(n=3, mean_ic=pytest.approx(mean), ic_std=pytest.approx(std), ic_tstat=pytest.approx(tstat))


def test_ic_summary_ignores_nulls_and_handles_empty():
    series = pl.DataFrame(
        {"effective_date": [dt.date(2020, 1, 1), dt.date(2020, 1, 2)], "ic": [0.5, None]}
    )
    summary = ic_summary(series)
    assert summary.n == 1
    assert summary.mean_ic == pytest.approx(0.5)
    assert summary.ic_std is None  # single value: sample std undefined
    assert summary.ic_tstat is None

    empty = pl.DataFrame(schema={"effective_date": pl.Date, "ic": pl.Float64})
    assert ic_summary(empty) == IcSummary(n=0, mean_ic=None, ic_std=None, ic_tstat=None)
