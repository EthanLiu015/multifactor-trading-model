import datetime as dt

import polars as pl
import pytest

from research.data import PITStore
from research.signals import SIGNAL_REGISTRY
from research.signals.low_vol import compute_low_vol
from research.signals.momentum import compute_momentum
from research.signals.reversal import compute_reversal

BARS_DATASET = "yfinance_daily"
K1 = dt.datetime(2026, 3, 1, 22, 0)


def trading_days(n: int, start: dt.date = dt.date(2020, 1, 1)) -> list[dt.date]:
    """n consecutive weekdays starting at (or after) start."""
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


def test_momentum_matches_closed_form_for_constant_return(store):
    lookback, skip, c = 252, 21, 0.001
    dates = trading_days(lookback + 1)
    store.append(BARS_DATASET, ret_bars("AAA", [c] * len(dates), dates), knowledge_ts=K1)
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])

    out = compute_momentum(bars, dates[-1], lookback_days=lookback, skip_days=skip)

    expected = (1 + c) ** (lookback - skip) - 1
    assert out["security_id"].to_list() == ["AAA"]
    assert out["signal_value"][0] == pytest.approx(expected)
    assert out["effective_date"][0] == dates[-1]


def test_momentum_short_history_returns_empty(store):
    dates = trading_days(100)  # well under the 252+1 requirement
    store.append(BARS_DATASET, ret_bars("AAA", [0.001] * len(dates), dates), knowledge_ts=K1)
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])

    out = compute_momentum(bars, dates[-1])
    assert out.is_empty()


def test_momentum_ignores_data_after_rebuild_date(store):
    lookback, skip, c = 252, 21, 0.001
    dates = trading_days(lookback + 1)
    later_dates = trading_days(5, start=dates[-1] + dt.timedelta(days=1))
    all_dates = dates + later_dates
    # Extreme later return would blow up momentum if the look-ahead guard failed.
    rets = [c] * len(dates) + [5.0] * len(later_dates)
    store.append(BARS_DATASET, ret_bars("AAA", rets, all_dates), knowledge_ts=K1)
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])

    out = compute_momentum(bars, dates[-1], lookback_days=lookback, skip_days=skip)
    expected = (1 + c) ** (lookback - skip) - 1
    assert out["signal_value"][0] == pytest.approx(expected)


def test_reversal_matches_closed_form_for_constant_return(store):
    window, c = 21, 0.002
    dates = trading_days(window + 1)
    store.append(BARS_DATASET, ret_bars("BBB", [c] * len(dates), dates), knowledge_ts=K1)
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])

    out = compute_reversal(bars, dates[-1], window_days=window)

    expected = (1 + c) ** window - 1
    assert out["signal_value"][0] == pytest.approx(expected)


def test_low_vol_zero_for_constant_return(store):
    window = 252
    dates = trading_days(window)
    store.append(BARS_DATASET, ret_bars("CCC", [0.001] * len(dates), dates), knowledge_ts=K1)
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])

    out = compute_low_vol(bars, dates[-1], window_days=window)

    assert out["signal_value"][0] == pytest.approx(0.0, abs=1e-12)


def test_low_vol_short_history_returns_empty(store):
    dates = trading_days(50)
    store.append(BARS_DATASET, ret_bars("CCC", [0.001] * len(dates), dates), knowledge_ts=K1)
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])

    out = compute_low_vol(bars, dates[-1], window_days=252)
    assert out.is_empty()


def test_signal_registry_contains_all_three():
    assert set(SIGNAL_REGISTRY) == {"momentum", "reversal", "low_vol"}
    assert SIGNAL_REGISTRY["momentum"] is compute_momentum
    assert SIGNAL_REGISTRY["reversal"] is compute_reversal
    assert SIGNAL_REGISTRY["low_vol"] is compute_low_vol
