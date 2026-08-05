import datetime as dt

import numpy as np
import polars as pl
import pytest

from research.attribution.scorecard import score_backtest
from research.backtest.result import summarize_backtest
from research.backtest.simulate import BacktestStep
from research.data import PITStore

BARS_DATASET = "yfinance_daily"
K1 = dt.datetime(2026, 3, 1, 22, 0)


def _step(
    date: dt.date,
    period_return: float | None,
    weights: list[float],
    trade_cost_total: float = 0.0,
) -> BacktestStep:
    return BacktestStep(
        rebuild_date=date,
        security_ids=[f"S{i}" for i in range(len(weights))],
        weights=np.array(weights),
        status="optimal",
        trade_cost=np.array([trade_cost_total]),
        turnover=0.0,
        period_return=period_return,
    )


@pytest.fixture()
def store(tmp_path):
    # A store.asof() on a dataset that was never appended to raises Polars'
    # ComputeError (scan_parquet on an empty glob), not an empty result --
    # documented house quirk (handoff.md §13). score_backtest always reads
    # BARS_DATASET for the realized-beta calc, so every test needs the
    # directory to exist, even tests that don't care about beta at all.
    s = PITStore(tmp_path / "lake")
    s.append(
        BARS_DATASET,
        pl.DataFrame(
            {"security_id": ["PLACEHOLDER"], "effective_date": [dt.date(2020, 1, 1)], "ret": [0.0]}
        ),
        knowledge_ts=K1,
    )
    return s


def test_sharpe_ratio_matches_hand_computation(store):
    steps = [
        _step(dt.date(2026, 1, 1), 0.02, [1.0]),
        _step(dt.date(2026, 2, 1), -0.01, [1.0]),
        _step(dt.date(2026, 3, 1), 0.015, [1.0]),
    ]
    result = summarize_backtest(steps, book_notional=10_000_000.0)  # zero cost -> net == gross

    scorecard = score_backtest(result, steps, store, knowledge_ts=K1)

    returns = np.array([0.02, -0.01, 0.015])
    expected = returns.mean() / returns.std(ddof=1) * np.sqrt(252)
    assert scorecard.sharpe_ratio == pytest.approx(expected)


def test_sharpe_ratio_none_with_fewer_than_two_points(store):
    steps = [_step(dt.date(2026, 1, 1), 0.02, [1.0])]
    result = summarize_backtest(steps, book_notional=10_000_000.0)

    scorecard = score_backtest(result, steps, store, knowledge_ts=K1)

    assert scorecard.sharpe_ratio is None


def test_sharpe_ratio_none_with_zero_variance(store):
    steps = [
        _step(dt.date(2026, 1, 1), 0.01, [1.0]),
        _step(dt.date(2026, 2, 1), 0.01, [1.0]),
    ]
    result = summarize_backtest(steps, book_notional=10_000_000.0)

    scorecard = score_backtest(result, steps, store, knowledge_ts=K1)

    assert scorecard.sharpe_ratio is None


def test_max_drawdown_matches_hand_computation(store):
    # net_returns: +10%, -20%, +5% -> equity curve 1.10, 0.88, 0.924
    # trough vs the running peak (1.10): (0.88 - 1.10) / 1.10 = -0.2
    steps = [
        _step(dt.date(2026, 1, 1), 0.10, [1.0]),
        _step(dt.date(2026, 2, 1), -0.20, [1.0]),
        _step(dt.date(2026, 3, 1), 0.05, [1.0]),
    ]
    result = summarize_backtest(steps, book_notional=10_000_000.0)

    scorecard = score_backtest(result, steps, store, knowledge_ts=K1)

    assert scorecard.max_drawdown == pytest.approx(-0.2)


def test_hit_rate_matches_hand_computation(store):
    steps = [
        _step(dt.date(2026, 1, 1), 0.01, [1.0]),
        _step(dt.date(2026, 2, 1), -0.02, [1.0]),
        _step(dt.date(2026, 3, 1), 0.03, [1.0]),
        _step(dt.date(2026, 4, 1), -0.01, [1.0]),
    ]
    result = summarize_backtest(steps, book_notional=10_000_000.0)

    scorecard = score_backtest(result, steps, store, knowledge_ts=K1)

    assert scorecard.hit_rate == pytest.approx(0.5)  # 2 of 4 positive


def test_gross_and_net_exposure_stay_aligned_when_a_step_is_excluded(store):
    steps = [
        _step(dt.date(2026, 1, 1), 0.01, [0.6, -0.3]),
        _step(dt.date(2026, 2, 1), None, [0.9, -0.1]),  # excluded from result -- must also be
        # excluded from exposure, or it would misalign against result's arrays
        _step(dt.date(2026, 3, 1), 0.02, [0.4, -0.5]),
    ]
    result = summarize_backtest(steps, book_notional=10_000_000.0)

    scorecard = score_backtest(result, steps, store, knowledge_ts=K1)

    assert len(scorecard.gross_exposure) == len(result.net_returns) == 2
    assert scorecard.gross_exposure == pytest.approx([0.9, 0.9])  # |0.6|+|-0.3|, |0.4|+|-0.5|
    assert scorecard.net_exposure == pytest.approx([0.3, -0.1])  # 0.6+-0.3, 0.4+-0.5


def test_realized_beta_is_nan_with_insufficient_history(store):
    # 10 days of real bars for the step's own securities -- far short of
    # compute_market_beta's default min_obs (2/3 of window_days=252, ~168)
    # -> it legitimately returns empty, not a crash; realized_beta is NaN.
    dates = [dt.date(2026, 1, 1) + dt.timedelta(days=i) for i in range(10)]
    bars = pl.concat(
        [
            pl.DataFrame(
                {"security_id": [sid] * len(dates), "effective_date": dates, "ret": [0.001] * len(dates)}
            )
            for sid in ("S0", "S1")
        ]
    )
    store.append(BARS_DATASET, bars, knowledge_ts=K1)

    steps = [
        BacktestStep(
            rebuild_date=dates[-1],
            security_ids=["S0", "S1"],
            weights=np.array([0.6, -0.2]),
            status="optimal",
            trade_cost=np.array([0.0]),
            turnover=0.0,
            period_return=0.01,
        )
    ]
    result = summarize_backtest(steps, book_notional=10_000_000.0)

    scorecard = score_backtest(result, steps, store, knowledge_ts=K1)

    assert np.isnan(scorecard.realized_beta[0])


def test_realized_beta_matches_hand_computation_for_identical_securities(store):
    # Two securities with IDENTICAL return series: the equal-weighted market
    # proxy equals each security's own series exactly, so
    # cov(security, market)/var(market) = var(x)/var(x) = 1.0 for both --
    # a closed-form case trusting compute_market_beta's own correctness
    # (tested independently in test_beta.py), only checking scorecard's
    # own integration: weights . beta.
    dates = []
    d = dt.date(2020, 1, 1)
    while len(dates) < 300:
        if d.weekday() < 5:
            dates.append(d)
        d += dt.timedelta(days=1)
    rets = [0.002 if i % 2 == 0 else -0.0012 for i in range(len(dates))]

    bars = pl.concat(
        [
            pl.DataFrame(
                {"security_id": [sid] * len(dates), "effective_date": dates, "ret": rets}
            )
            for sid in ("S0", "S1")
        ]
    )
    store.append(BARS_DATASET, bars, knowledge_ts=K1)

    rebuild_date = dates[290]
    steps = [
        BacktestStep(
            rebuild_date=rebuild_date,
            security_ids=["S0", "S1"],
            weights=np.array([0.6, -0.2]),
            status="optimal",
            trade_cost=np.array([0.0]),
            turnover=0.0,
            period_return=0.01,
        )
    ]
    result = summarize_backtest(steps, book_notional=10_000_000.0)

    scorecard = score_backtest(result, steps, store, knowledge_ts=K1)

    # beta_S0 == beta_S1 == 1.0 exactly -> portfolio beta == weights.sum()
    assert scorecard.realized_beta[0] == pytest.approx(0.4)
