import datetime as dt

import numpy as np
import pytest

from research.attribution.scorecard import score_backtest
from research.backtest.result import summarize_backtest
from research.backtest.simulate import BacktestStep


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


def test_sharpe_ratio_matches_hand_computation():
    steps = [
        _step(dt.date(2026, 1, 1), 0.02, [1.0]),
        _step(dt.date(2026, 2, 1), -0.01, [1.0]),
        _step(dt.date(2026, 3, 1), 0.015, [1.0]),
    ]
    result = summarize_backtest(steps, book_notional=10_000_000.0)  # zero cost -> net == gross

    scorecard = score_backtest(result, steps)

    returns = np.array([0.02, -0.01, 0.015])
    expected = returns.mean() / returns.std(ddof=1) * np.sqrt(252)
    assert scorecard.sharpe_ratio == pytest.approx(expected)


def test_sharpe_ratio_none_with_fewer_than_two_points():
    steps = [_step(dt.date(2026, 1, 1), 0.02, [1.0])]
    result = summarize_backtest(steps, book_notional=10_000_000.0)

    scorecard = score_backtest(result, steps)

    assert scorecard.sharpe_ratio is None


def test_sharpe_ratio_none_with_zero_variance():
    steps = [
        _step(dt.date(2026, 1, 1), 0.01, [1.0]),
        _step(dt.date(2026, 2, 1), 0.01, [1.0]),
    ]
    result = summarize_backtest(steps, book_notional=10_000_000.0)

    scorecard = score_backtest(result, steps)

    assert scorecard.sharpe_ratio is None


def test_max_drawdown_matches_hand_computation():
    # net_returns: +10%, -20%, +5% -> equity curve 1.10, 0.88, 0.924
    # trough vs the running peak (1.10): (0.88 - 1.10) / 1.10 = -0.2
    steps = [
        _step(dt.date(2026, 1, 1), 0.10, [1.0]),
        _step(dt.date(2026, 2, 1), -0.20, [1.0]),
        _step(dt.date(2026, 3, 1), 0.05, [1.0]),
    ]
    result = summarize_backtest(steps, book_notional=10_000_000.0)

    scorecard = score_backtest(result, steps)

    assert scorecard.max_drawdown == pytest.approx(-0.2)


def test_hit_rate_matches_hand_computation():
    steps = [
        _step(dt.date(2026, 1, 1), 0.01, [1.0]),
        _step(dt.date(2026, 2, 1), -0.02, [1.0]),
        _step(dt.date(2026, 3, 1), 0.03, [1.0]),
        _step(dt.date(2026, 4, 1), -0.01, [1.0]),
    ]
    result = summarize_backtest(steps, book_notional=10_000_000.0)

    scorecard = score_backtest(result, steps)

    assert scorecard.hit_rate == pytest.approx(0.5)  # 2 of 4 positive


def test_gross_and_net_exposure_stay_aligned_when_a_step_is_excluded():
    steps = [
        _step(dt.date(2026, 1, 1), 0.01, [0.6, -0.3]),
        _step(dt.date(2026, 2, 1), None, [0.9, -0.1]),  # excluded from result -- must also be
        # excluded from exposure, or it would misalign against result's arrays
        _step(dt.date(2026, 3, 1), 0.02, [0.4, -0.5]),
    ]
    result = summarize_backtest(steps, book_notional=10_000_000.0)

    scorecard = score_backtest(result, steps)

    assert len(scorecard.gross_exposure) == len(result.net_returns) == 2
    assert scorecard.gross_exposure == pytest.approx([0.9, 0.9])  # |0.6|+|-0.3|, |0.4|+|-0.5|
    assert scorecard.net_exposure == pytest.approx([0.3, -0.1])  # 0.6+-0.3, 0.4+-0.5
