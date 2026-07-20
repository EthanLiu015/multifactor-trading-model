import datetime as dt

import numpy as np
import polars as pl
import pytest

from research.data import PITStore
from research.risk.model import build_risk_model

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

    # 6 securities: with market + 1 sector dummy (2 sectors) + momentum + low_vol
    # = 4 factor columns, cross_sectional_regression needs >= 5 observations
    # to be non-underdetermined (3 alone was not enough — caught by a real test failure).
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
        pl.concat(
            [ret_bars(t, wiggly(b), dates) for t, b in zip(tickers, bases)]
        ),
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
    store.append(
        UNIVERSE_DATASET,
        pl.concat(
            [
                pl.DataFrame(
                    {
                        "effective_date": [d] * len(tickers),
                        "security_id": tickers,
                    }
                )
                for d in rebuild_dates
            ]
        ),
        knowledge_ts=K1,
    )
    return store, rebuild_dates


def test_build_risk_model_end_to_end_shape(populated_store):
    store, rebuild_dates = populated_store
    model = build_risk_model(store, rebuild_dates[-1], lookback_years=10, knowledge_ts=K1)

    assert model is not None
    n = len(model.security_ids)
    k = len(model.factor_names)
    assert model.B.shape == (n, k)
    assert model.F.shape == (k, k)
    assert model.D.shape == (n,)
    assert "market" in model.factor_names
    # exactly one of the two sectors survives as a dummy (the other is the reference)
    assert sum(1 for f in model.factor_names if f.startswith("sector_")) == 1

    sigma = model.sigma()
    assert sigma.shape == (n, n)
    assert sigma == pytest.approx(sigma.T, abs=1e-10)  # symmetric
    assert np.all(np.diag(sigma) > 0)  # positive variance on the diagonal


def test_build_risk_model_none_with_insufficient_history(store):
    dates = trading_days(50)  # far short of momentum's 273-day requirement
    store.append(BARS_DATASET, ret_bars("AAA", [0.001] * len(dates), dates), knowledge_ts=K1)
    store.append(
        SECTOR_DATASET,
        pl.DataFrame(
            {
                "security_id": ["AAA"],
                "effective_date": [K1.date()],
                "sector": ["Technology"],
            }
        ),
        knowledge_ts=K1,
    )
    store.append(
        UNIVERSE_DATASET,
        pl.DataFrame({"effective_date": [dates[-1]], "security_id": ["AAA"]}),
        knowledge_ts=K1,
    )

    model = build_risk_model(store, dates[-1], lookback_years=10, knowledge_ts=K1)
    assert model is None
