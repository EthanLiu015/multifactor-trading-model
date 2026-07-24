import datetime as dt

import numpy as np
import polars as pl
import pytest

from research.backtest.simulate import run_backtest
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
    dates = trading_days(430)

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
    # 4 monthly-ish rebalance dates, all deep enough into history for a 10y lookback
    rebuild_dates = [dates[300], dates[330], dates[360], dates[400]]
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


def test_run_backtest_produces_a_step_per_rebalance_date(populated_store):
    store, rebuild_dates, tickers = populated_store
    steps = run_backtest(
        store, rebuild_dates[0], rebuild_dates[-1], lookback_years=10, knowledge_ts=K1
    )

    # rebuild_dates[0] is the earliest of only 4 universe_monthly snapshots,
    # so build_risk_model sees just 1 trailing observation <= itself and
    # returns None (needs >= 2) -- correctly skipped, same convention as
    # test_risk_model.py/test_portfolio_inputs.py's insufficient-history tests.
    usable_dates = rebuild_dates[1:]
    assert len(steps) == len(usable_dates)
    for step, date in zip(steps, usable_dates):
        assert step.rebuild_date == date
        assert step.status in ("optimal", "optimal_inaccurate")
        n = len(step.security_ids)
        assert step.weights.shape == (n,)
        assert step.trade_cost.shape == (n,)
        assert np.all(step.trade_cost >= 0.0)

    # last step has no next date to hold until
    assert steps[-1].period_return is None
    # every other step got a real holding-period return
    for step in steps[:-1]:
        assert step.period_return is not None


def test_run_backtest_threads_w_prev_across_dates(populated_store):
    """First rebalance starts flat (full cost); later ones trade only the delta."""
    store, rebuild_dates, tickers = populated_store
    steps = run_backtest(
        store, rebuild_dates[0], rebuild_dates[-1], lookback_years=10, knowledge_ts=K1
    )

    first_total_cost = steps[0].trade_cost.sum()
    later_total_cost = steps[1].trade_cost.sum()
    # flat start trades the full target weight; a warm start only trades the delta
    assert first_total_cost > 0
    assert later_total_cost < first_total_cost


def test_run_backtest_skips_dates_with_insufficient_history(store):
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

    steps = run_backtest(store, dates[0], dates[-1], lookback_years=10, knowledge_ts=K1)
    assert steps == []
