"""Block 4c: the mean-variance QP (DESIGN.md Block 4).

max_w  αᵀw − λ·wᵀΣw − κ·‖w − w_prev‖²
s.t.   (research/portfolio/constraints.py's full constraint set)

Σ = B·F·Bᵀ + diag(D) is never materialized as an N×N matrix — the risk
penalty is computed in factor form, ``quad_form(Bᵀw, F) + Σ(D_i · w_i²)``,
the same "~K² factor covariances instead of ~N² stock covariances"
rationale as DESIGN.md's risk-model section and block 4a's docstring.

``cp.quad_form(..., assume_PSD=True)``: ``F`` is Ledoit-Wolf shrunk
(research/risk/factor_covariance.py), theoretically PSD by construction:
skipping cvxpy's own PSD check avoids a spurious DCP failure from tiny
floating-point negative eigenvalues on an already-guaranteed-PSD matrix.

The quadratic turnover-cost term ``κ·‖w − w_prev‖²`` in the objective is
DELIBERATELY on top of block 4b's hard ``turnover_cap`` constraint, not a
replacement for it — the hard cap prevents blowups, the soft cost shapes
behavior within the cap. Both ``λ`` and ``κ`` are placeholder constants;
nothing calibrates them yet without a working backtester (same posture
as every other block 4 constant so far).
"""

from __future__ import annotations

import cvxpy as cp

from research.portfolio.constraints import build_constraints
from research.portfolio.inputs import OptimizerInputs


def solve_qp(
    inputs: OptimizerInputs,
    *,
    risk_aversion: float = 5.0,
    cost_penalty: float = 10.0,
    **constraint_kwargs,
) -> tuple[cp.Variable, cp.Problem]:
    """Build and solve the QP for one ``OptimizerInputs``.

    ``constraint_kwargs`` are forwarded to
    :func:`research.portfolio.constraints.build_constraints` (gross_cap,
    turnover_cap, factor_exposure_cap, adv_days, book_notional).

    Returns ``(w, problem)`` unsolved-variable-object-style: read
    ``w.value`` for the target weights, ``problem.status`` for the
    solver outcome, ``problem.value`` for the achieved objective.
    """
    n = len(inputs.security_ids)
    w = cp.Variable(n)
    constraints = build_constraints(inputs, w, **constraint_kwargs)

    risk = cp.quad_form(inputs.B.T @ w, inputs.F, assume_PSD=True) + cp.sum(
        cp.multiply(inputs.D, cp.square(w))
    )
    cost = cp.sum_squares(w - inputs.w_prev)
    objective = cp.Maximize(inputs.alpha @ w - risk_aversion * risk - cost_penalty * cost)

    problem = cp.Problem(objective, constraints)
    problem.solve()
    return w, problem
