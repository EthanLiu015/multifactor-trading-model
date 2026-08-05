import datetime as dt

import numpy as np
import polars as pl
import pytest

from research.attribution.decompose import decompose_backtest
from research.backtest import BacktestStep
from research.data import PITStore

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
        {"security_id": [security_id] * len(dates), "effective_date": dates, "ret": rets}
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
    store.append(
        UNIVERSE_DATASET,
        pl.concat(
            [
                pl.DataFrame({"effective_date": [d] * len(tickers), "security_id": tickers})
                for d in rebuild_dates
            ]
        ),
        knowledge_ts=K1,
    )
    return store, rebuild_dates, tickers


def test_decompose_backtest_empty_steps_returns_empty_result(store):
    result = decompose_backtest([], store)

    assert result.dates == []
    assert len(result.factor_contribution) == 0


def test_decompose_backtest_end_to_end_shape(populated_store):
    store, rebuild_dates, tickers = populated_store
    d = rebuild_dates[-1]
    step = BacktestStep(
        rebuild_date=d,
        security_ids=tickers,
        weights=np.array([0.2, -0.2, 0.15, -0.15, 0.1, -0.1]),
        status="optimal",
        trade_cost=np.zeros(len(tickers)),
        turnover=0.0,
        period_return=0.01,
    )

    result = decompose_backtest([step], store, knowledge_ts=K1)

    assert result.dates == [d]
    assert len(result.factor_contribution) == 1
    assert len(result.specific_contribution) == 1
    assert result.total[0] == pytest.approx(
        result.factor_contribution[0] + result.specific_contribution[0]
    )


def test_decompose_backtest_excludes_non_optimal_steps(populated_store):
    store, rebuild_dates, tickers = populated_store
    d = rebuild_dates[-1]
    step = BacktestStep(
        rebuild_date=d,
        security_ids=tickers,
        weights=np.array([0.2, -0.2, 0.15, -0.15, 0.1, -0.1]),
        status="infeasible",  # not optimal -- weights aren't real trades
        trade_cost=np.zeros(len(tickers)),
        turnover=0.0,
        period_return=None,
    )

    result = decompose_backtest([step], store, knowledge_ts=K1)

    assert result.dates == [d]
    assert result.factor_contribution[0] == 0.0
    assert result.specific_contribution[0] == 0.0


def test_decompose_backtest_date_with_no_matching_data_is_zero_not_missing(populated_store):
    store, rebuild_dates, tickers = populated_store
    out_of_range_date = dt.date(1999, 1, 1)
    step = BacktestStep(
        rebuild_date=out_of_range_date,
        security_ids=tickers,
        weights=np.array([0.2, -0.2, 0.15, -0.15, 0.1, -0.1]),
        status="optimal",
        trade_cost=np.zeros(len(tickers)),
        turnover=0.0,
        period_return=0.0,
    )

    result = decompose_backtest([step], store, knowledge_ts=K1)

    assert result.dates == [out_of_range_date]
    assert result.factor_contribution[0] == 0.0
    assert result.specific_contribution[0] == 0.0
