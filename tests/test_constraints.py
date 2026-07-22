import datetime as dt

import cvxpy as cp
import numpy as np
import pytest

from research.portfolio.constraints import build_constraints
from research.portfolio.inputs import OptimizerInputs


@pytest.fixture()
def synthetic_inputs() -> OptimizerInputs:
    security_ids = ["A", "B", "C", "D", "E", "F"]
    factor_names = ["market", "sector_Energy", "momentum", "low_vol"]
    # Technology (reference sector, dropped) = A,B,C; Energy = D,E,F.
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
    return OptimizerInputs(
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


def _solve(inputs: OptimizerInputs, **kwargs) -> tuple[cp.Variable, list[cp.Constraint]]:
    n = len(inputs.security_ids)
    w = cp.Variable(n)
    constraints = build_constraints(inputs, w, **kwargs)
    # Ridge-regularized linear objective: pushes w toward alpha's direction
    # (not just w=0, which would trivially satisfy every constraint here)
    # while staying bounded/DCP-valid.
    problem = cp.Problem(cp.Minimize(-inputs.alpha @ w + 0.01 * cp.sum_squares(w)), constraints)
    problem.solve()
    assert problem.status in ("optimal", "optimal_inaccurate")
    return w, constraints


def test_constraints_are_dcp_and_solution_respects_every_bound(synthetic_inputs):
    gross_cap, turnover_cap, factor_exposure_cap, adv_days, book_notional = (
        2.0,
        0.5,
        0.5,
        5.0,
        10_000_000.0,
    )
    w, constraints = _solve(
        synthetic_inputs,
        gross_cap=gross_cap,
        turnover_cap=turnover_cap,
        factor_exposure_cap=factor_exposure_cap,
        adv_days=adv_days,
        book_notional=book_notional,
    )
    val = w.value
    tol = 1e-4

    assert abs(val.sum()) < tol  # dollar-neutral
    assert abs(synthetic_inputs.beta @ val) < tol  # beta-neutral

    sector_col = synthetic_inputs.B[:, synthetic_inputs.factor_names.index("sector_Energy")]
    assert abs(sector_col @ val) < tol  # sector-neutral

    adv_bound = adv_days * synthetic_inputs.adv / book_notional
    assert np.all(np.abs(val) <= adv_bound + tol)  # ADV-relative position caps

    assert np.abs(val - synthetic_inputs.w_prev).sum() <= turnover_cap + tol
    assert np.abs(val).sum() <= gross_cap + tol

    for name in ("momentum", "low_vol"):
        col = synthetic_inputs.B[:, synthetic_inputs.factor_names.index(name)]
        assert abs(col @ val) <= factor_exposure_cap + tol


def test_constraints_bind_when_alpha_pushes_against_them(synthetic_inputs):
    """A tight ADV cap forces the ADV constraint to actually bind, not just hold slack."""
    tiny_adv = np.full(6, 1e5)  # tiny dollar volume -> tiny weight-space cap
    tight_inputs = OptimizerInputs(**{**synthetic_inputs.__dict__, "adv": tiny_adv})
    w, _ = _solve(tight_inputs, adv_days=5.0, book_notional=10_000_000.0)

    adv_bound = 5.0 * tiny_adv / 10_000_000.0
    assert np.any(np.abs(w.value) >= adv_bound - 1e-4)  # at least one name pinned at its cap
