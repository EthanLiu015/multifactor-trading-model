import datetime as dt

import numpy as np
import polars as pl
import pytest

from research.data import PITStore
from research.portfolio.beta import compute_market_beta

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


def test_beta_matches_numpy_recomputation(store):
    window = 252
    dates = trading_days(window)
    rng = np.random.default_rng(0)
    a = rng.normal(0, 0.01, window)
    b = rng.normal(0, 0.01, window)
    c = rng.normal(0, 0.01, window)

    store.append(
        BARS_DATASET,
        pl.concat(
            [
                ret_bars("AAA", a.tolist(), dates),
                ret_bars("BBB", b.tolist(), dates),
                ret_bars("CCC", c.tolist(), dates),
            ]
        ),
        knowledge_ts=K1,
    )
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])

    out = compute_market_beta(bars, dates[-1], ["AAA", "BBB", "CCC"], window_days=window)

    mkt = (a + b + c) / 3.0
    expected = {
        "AAA": np.cov(a, mkt, ddof=1)[0, 1] / np.var(mkt, ddof=1),
        "BBB": np.cov(b, mkt, ddof=1)[0, 1] / np.var(mkt, ddof=1),
        "CCC": np.cov(c, mkt, ddof=1)[0, 1] / np.var(mkt, ddof=1),
    }
    got = dict(zip(out["security_id"].to_list(), out["beta"].to_list()))
    for sid, exp in expected.items():
        assert got[sid] == pytest.approx(exp)


def test_beta_short_history_returns_empty(store):
    dates = trading_days(50)  # well under the 252-day default window's min_obs
    store.append(
        BARS_DATASET,
        pl.concat(
            [
                ret_bars("AAA", [0.001] * len(dates), dates),
                ret_bars("BBB", [0.002] * len(dates), dates),
            ]
        ),
        knowledge_ts=K1,
    )
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])

    out = compute_market_beta(bars, dates[-1], ["AAA", "BBB"])
    assert out.is_empty()


def test_beta_only_computed_over_named_securities(store):
    """A security outside `security_ids` neither gets a beta nor pollutes the market proxy."""
    window = 252
    dates = trading_days(window)
    rng = np.random.default_rng(1)
    a = rng.normal(0, 0.01, window)
    b = rng.normal(0, 0.01, window)
    outsider = rng.normal(0, 0.05, window)  # wildly different vol; would skew mkt if included

    store.append(
        BARS_DATASET,
        pl.concat(
            [
                ret_bars("AAA", a.tolist(), dates),
                ret_bars("BBB", b.tolist(), dates),
                ret_bars("ZZZ", outsider.tolist(), dates),
            ]
        ),
        knowledge_ts=K1,
    )
    bars = store.asof(BARS_DATASET, K1, keys=["security_id"])

    out = compute_market_beta(bars, dates[-1], ["AAA", "BBB"], window_days=window)

    assert set(out["security_id"].to_list()) == {"AAA", "BBB"}
    mkt = (a + b) / 2.0
    expected_aaa = np.cov(a, mkt, ddof=1)[0, 1] / np.var(mkt, ddof=1)
    got = dict(zip(out["security_id"].to_list(), out["beta"].to_list()))
    assert got["AAA"] == pytest.approx(expected_aaa)
