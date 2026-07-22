import datetime as dt

import numpy as np
import polars as pl
import pytest

from research.data import PITStore
from research.portfolio.inputs import build_optimizer_inputs

BARS_DATASET = "yfinance_daily"
UNIVERSE_DATASET = "universe_monthly"
SECTOR_DATASET = "yfinance_sector_current"
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


@pytest.fixture()
def populated_store(store):
    dates = trading_days(400)

    def wiggly(base):
        return [base if i % 2 == 0 else -base * 0.6 for i in range(len(dates))]

    tickers = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]
    sector_map = {
        "AAA": "Technology",
        "BBB": "Energy",
        "CCC": "Technology",
        "DDD": "Energy",
        "EEE": "Technology",
        "FFF": "Energy",
    }
    bases = [0.002, 0.004, 0.001, 0.003, 0.0015, 0.0025]
    store.append(
        BARS_DATASET,
        pl.concat([ret_bars(t, wiggly(b), dates) for t, b in zip(tickers, bases)]),
        knowledge_ts=K1,
    )
    store.append(
        SECTOR_DATASET,
        pl.DataFrame(
            {
                "security_id": tickers,
                "effective_date": [K1.date()] * len(tickers),
                "sector": [sector_map[t] for t in tickers],
            }
        ),
        knowledge_ts=K1,
    )
    rebuild_dates = [dates[300], dates[330], dates[360], dates[390]]
    adv_map = {"AAA": 5e6, "BBB": 2e7, "CCC": 1e6, "DDD": 8e6, "EEE": 3e6, "FFF": 1.5e7}
    store.append(
        UNIVERSE_DATASET,
        pl.concat(
            [
                pl.DataFrame(
                    {
                        "effective_date": [d] * len(tickers),
                        "security_id": tickers,
                        "median_dollar_volume": [adv_map[t] for t in tickers],
                    }
                )
                for d in rebuild_dates
            ]
        ),
        knowledge_ts=K1,
    )
    return store, rebuild_dates, tickers


def test_build_optimizer_inputs_end_to_end_shape(populated_store):
    store, rebuild_dates, tickers = populated_store
    result = build_optimizer_inputs(
        store, rebuild_dates[-1], lookback_years=10, knowledge_ts=K1
    )

    assert result is not None
    n = len(result.security_ids)
    k = len(result.factor_names)
    assert n > 0
    assert set(result.security_ids).issubset(set(tickers))
    assert result.B.shape == (n, k)
    assert result.F.shape == (k, k)
    assert result.D.shape == (n,)
    assert result.alpha.shape == (n,)
    assert result.beta.shape == (n,)
    assert result.adv.shape == (n,)
    assert np.all(result.adv > 0)
    assert result.w_prev.shape == (n,)
    # flat start (w_prev=None) -> every prior weight is 0
    assert np.all(result.w_prev == 0.0)
    # shrink+cap invariant holds regardless of the underlying signal values
    assert np.all(np.abs(result.alpha) <= 3.0)


def test_build_optimizer_inputs_none_when_risk_model_none(store):
    dates = trading_days(50)  # far short of momentum's 273-day requirement
    store.append(BARS_DATASET, ret_bars("AAA", [0.001] * len(dates), dates), knowledge_ts=K1)
    store.append(
        SECTOR_DATASET,
        pl.DataFrame(
            {"security_id": ["AAA"], "effective_date": [K1.date()], "sector": ["Technology"]}
        ),
        knowledge_ts=K1,
    )
    store.append(
        UNIVERSE_DATASET,
        pl.DataFrame({"effective_date": [dates[-1]], "security_id": ["AAA"]}),
        knowledge_ts=K1,
    )

    result = build_optimizer_inputs(store, dates[-1], lookback_years=10, knowledge_ts=K1)
    assert result is None


def test_build_optimizer_inputs_w_prev_supplied(populated_store):
    store, rebuild_dates, tickers = populated_store
    w_prev = pl.DataFrame(
        {"security_id": ["AAA", "BBB"], "weight": [0.05, -0.03]}
    )

    result = build_optimizer_inputs(
        store, rebuild_dates[-1], w_prev, lookback_years=10, knowledge_ts=K1
    )

    assert result is not None
    by_id = dict(zip(result.security_ids, result.w_prev))
    assert by_id["AAA"] == pytest.approx(0.05)
    assert by_id["BBB"] == pytest.approx(-0.03)
    # names absent from w_prev default to flat, not dropped
    for sid in result.security_ids:
        if sid not in ("AAA", "BBB"):
            assert by_id[sid] == 0.0
