import datetime as dt

import numpy as np
import pytest

from research.portfolio.inputs import OptimizerInputs
from research.portfolio.solve import solve_qp


def _synthetic_inputs(**overrides) -> OptimizerInputs:
    security_ids = ["A", "B", "C", "D", "E", "F"]
    factor_names = ["market", "sector_Energy", "momentum", "low_vol"]
    B = np.array(
        [
            [1.0, 0.0, 0.5, -0.3],
            [1.0, 0.0, -0.8, 0.2],
            [1.0, 0.0, 1.2, -0.1],
            [1.0, 1.0, -0.4, 0.6],
            [1.0, 1.0, 0.9, -0.7],
            [1.0, 1.0, -1.1, 0.4],
        ]
    )
    defaults = dict(
        rebuild_date=dt.date(2026, 7, 14),
        security_ids=security_ids,
        factor_names=factor_names,
        B=B,
        F=np.eye(4),
        D=np.ones(6) * 0.01,
        alpha=np.array([2.0, -1.0, 1.0, -2.0, 0.5, -0.5]),
        beta=np.array([1.2, 0.8, 1.0, 0.9, 1.1, 1.0]),
        adv=np.array([5e6, 2e7, 1e6, 8e6, 3e6, 1.5e7]),
        w_prev=np.zeros(6),
    )
    defaults.update(overrides)
    return OptimizerInputs(**defaults)


def test_solve_qp_optimal_and_respects_every_constraint():
    inputs = _synthetic_inputs()
    gross_cap, turnover_cap, factor_exposure_cap, adv_days, book_notional = (
        2.0,
        0.5,
        0.5,
        5.0,
        10_000_000.0,
    )
    w, problem = solve_qp(
        inputs,
        risk_aversion=5.0,
        cost_penalty=10.0,
        gross_cap=gross_cap,
        turnover_cap=turnover_cap,
        factor_exposure_cap=factor_exposure_cap,
        adv_days=adv_days,
        book_notional=book_notional,
    )

    assert problem.status in ("optimal", "optimal_inaccurate")
    val = w.value
    assert val.shape == (6,)
    tol = 1e-4

    assert abs(val.sum()) < tol
    assert abs(inputs.beta @ val) < tol
    sector_col = inputs.B[:, inputs.factor_names.index("sector_Energy")]
    assert abs(sector_col @ val) < tol
    adv_bound = adv_days * inputs.adv / book_notional
    assert np.all(np.abs(val) <= adv_bound + tol)
    assert np.abs(val - inputs.w_prev).sum() <= turnover_cap + tol
    assert np.abs(val).sum() <= gross_cap + tol
    for name in ("momentum", "low_vol"):
        col = inputs.B[:, inputs.factor_names.index(name)]
        assert abs(col @ val) <= factor_exposure_cap + tol


def test_solve_qp_zero_alpha_and_flat_start_returns_flat_book():
    """No alpha view + already flat: risk/cost penalties give zero incentive to deviate."""
    inputs = _synthetic_inputs(alpha=np.zeros(6), w_prev=np.zeros(6))
    w, problem = solve_qp(inputs, risk_aversion=5.0, cost_penalty=10.0)

    assert problem.status in ("optimal", "optimal_inaccurate")
    assert w.value == pytest.approx(np.zeros(6), abs=1e-4)


def test_solve_qp_higher_risk_aversion_shrinks_gross_exposure():
    inputs = _synthetic_inputs()
    _, low_lambda_problem = solve_qp(inputs, risk_aversion=1.0, cost_penalty=10.0)
    w_low, _ = solve_qp(inputs, risk_aversion=1.0, cost_penalty=10.0)
    w_high, high_lambda_problem = solve_qp(inputs, risk_aversion=50.0, cost_penalty=10.0)

    assert low_lambda_problem.status in ("optimal", "optimal_inaccurate")
    assert high_lambda_problem.status in ("optimal", "optimal_inaccurate")
    assert np.abs(w_high.value).sum() < np.abs(w_low.value).sum()
