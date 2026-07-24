"""Block 4d: end-to-end optimizer orchestration (DESIGN.md Block 4).

Chains build_optimizer_inputs (4a) -> solve_qp (4b/4c) into one call,
mirroring research/risk/model.py's build_risk_model role: one function a
caller (eventually the backtester) invokes per rebalance date, without
needing to know the inputs-assembly/constraints/solve split underneath.

``None`` propagates from build_optimizer_inputs exactly like
build_risk_model propagates None (insufficient history, or no security
survives the signal/exposure/beta/ADV intersection that date) --
"absent means insufficient data" all the way up the chain.

A non-``None`` result can still carry a non-optimal ``status`` (e.g.
"infeasible" if w_prev no longer satisfies that day's ADV/factor caps).
This is NOT collapsed into None: infeasibility is a distinct, real
signal a future backtester needs to see and react to (e.g. skip the
rebalance, relax a cap), not a data-availability gap. Callers must check
``status`` before trusting ``weights``.
"""

from __future__ import annotations

import dataclasses
import datetime as dt

import numpy as np
import polars as pl

from research.data import PITStore
from research.portfolio.inputs import build_optimizer_inputs
from research.portfolio.solve import solve_qp


@dataclasses.dataclass
class TargetPortfolio:
    rebuild_date: dt.date
    security_ids: list[str]
    weights: np.ndarray  # N, row-aligned to security_ids; only trust if status is optimal*
    w_prev: np.ndarray  # N, the aligned previous weights the solve used (block 5's cost calc needs this)
    adv: np.ndarray  # N, $ median daily dollar volume, same alignment (block 5's cost calc needs this)
    objective_value: float
    status: str  # cvxpy problem.status, e.g. "optimal", "infeasible"


def build_target_portfolio(
    store: PITStore,
    rebuild_date: dt.date,
    w_prev: pl.DataFrame | None = None,
    *,
    lookback_years: int = 3,
    shrink: float = 0.5,
    cap: float = 3.0,
    risk_aversion: float = 5.0,
    cost_penalty: float = 10.0,
    knowledge_ts: dt.datetime | None = None,
    **constraint_kwargs,
) -> TargetPortfolio | None:
    """Target weights for one rebalance date, or ``None`` if inputs can't be built.

    ``constraint_kwargs`` (gross_cap, turnover_cap, factor_exposure_cap,
    adv_days, book_notional) are forwarded to
    :func:`research.portfolio.constraints.build_constraints` via
    :func:`research.portfolio.solve.solve_qp`.
    """
    inputs = build_optimizer_inputs(
        store,
        rebuild_date,
        w_prev,
        lookback_years=lookback_years,
        shrink=shrink,
        cap=cap,
        knowledge_ts=knowledge_ts,
    )
    if inputs is None:
        return None

    w, problem = solve_qp(
        inputs,
        risk_aversion=risk_aversion,
        cost_penalty=cost_penalty,
        **constraint_kwargs,
    )

    return TargetPortfolio(
        rebuild_date=rebuild_date,
        security_ids=inputs.security_ids,
        weights=w.value,
        w_prev=inputs.w_prev,
        adv=inputs.adv,
        objective_value=problem.value,
        status=problem.status,
    )
