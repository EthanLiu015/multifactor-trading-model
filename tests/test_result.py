import datetime as dt

import numpy as np
import pytest

from research.backtest.result import summarize_backtest
from research.backtest.simulate import BacktestStep


def _step(
    date: dt.date, period_return: float | None, trade_cost_total: float, turnover: float = 0.0
) -> BacktestStep:
    return BacktestStep(
        rebuild_date=date,
        security_ids=["AAA"],
        weights=np.array([1.0]),
        status="optimal",
        trade_cost=np.array([trade_cost_total]),
        turnover=turnover,
        period_return=period_return,
    )


def test_summarize_backtest_equity_curve_matches_hand_computation():
    steps = [
        _step(dt.date(2026, 1, 1), period_return=0.02, trade_cost_total=10_000.0),
        _step(dt.date(2026, 2, 1), period_return=-0.01, trade_cost_total=5_000.0),
        _step(dt.date(2026, 3, 1), period_return=None, trade_cost_total=2_000.0),  # final step
    ]
    result = summarize_backtest(steps, book_notional=10_000_000.0)

    # final step (no period_return) is excluded
    assert result.dates == [dt.date(2026, 1, 1), dt.date(2026, 2, 1)]
    assert result.gross_returns == pytest.approx([0.02, -0.01])
    assert result.costs == pytest.approx([10_000.0, 5_000.0])

    net_1 = 0.02 - 10_000.0 / 10_000_000.0  # 0.02 - 0.001 = 0.019
    net_2 = -0.01 - 5_000.0 / 10_000_000.0  # -0.01 - 0.0005 = -0.0105
    assert result.net_returns == pytest.approx([net_1, net_2])

    expected_curve = [1.0 * (1 + net_1), 1.0 * (1 + net_1) * (1 + net_2)]
    assert result.equity_curve == pytest.approx(expected_curve)


def test_net_return_below_gross_return_when_cost_positive():
    steps = [_step(dt.date(2026, 1, 1), period_return=0.03, trade_cost_total=50_000.0)]
    result = summarize_backtest(steps, book_notional=10_000_000.0)

    assert result.net_returns[0] < result.gross_returns[0]


def test_summarize_backtest_empty_steps_gives_empty_result():
    result = summarize_backtest([], book_notional=10_000_000.0)

    assert result.dates == []
    assert result.gross_returns.shape == (0,)
    assert result.costs.shape == (0,)
    assert result.net_returns.shape == (0,)
    assert result.equity_curve.shape == (0,)
    assert result.turnover.shape == (0,)
