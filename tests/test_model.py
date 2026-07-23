import datetime as dt

import numpy as np
import polars as pl
import pytest

from research.data import PITStore
from research.portfolio.model import build_target_portfolio

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


def test_build_target_portfolio_end_to_end(populated_store):
    store, rebuild_dates, tickers = populated_store
    result = build_target_portfolio(store, rebuild_dates[-1], lookback_years=10, knowledge_ts=K1)

    assert result is not None
    assert result.status in ("optimal", "optimal_inaccurate")
    n = len(result.security_ids)
    assert n > 0
    assert set(result.security_ids).issubset(set(tickers))
    assert result.weights.shape == (n,)
    assert isinstance(result.objective_value, float)
    # dollar-neutral constraint from build_constraints holds on the real solve
    assert abs(result.weights.sum()) < 1e-4


def test_build_target_portfolio_none_when_risk_model_none(store):
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

    result = build_target_portfolio(store, dates[-1], lookback_years=10, knowledge_ts=K1)
    assert result is None


def test_build_target_portfolio_respects_constraint_kwargs(populated_store):
    store, rebuild_dates, tickers = populated_store
    result = build_target_portfolio(
        store,
        rebuild_dates[-1],
        lookback_years=10,
        knowledge_ts=K1,
        gross_cap=0.1,
    )

    assert result is not None
    assert result.status in ("optimal", "optimal_inaccurate")
    assert np.abs(result.weights).sum() <= 0.1 + 1e-4
