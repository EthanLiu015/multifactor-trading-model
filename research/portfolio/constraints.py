"""Block 4b: optimizer constraints (DESIGN.md Block 4).

Builds the cvxpy constraint list for the target-holdings QP (block 4c)
from one ``OptimizerInputs`` and a cvxpy weight variable ``w`` (shape
``(N,)``, same order as ``inputs.security_ids``).

Implemented (DESIGN.md's named constraints):
- **dollar-neutral**: ``sum(w) == 0``.
- **beta-neutral**: ``beta @ w == 0``, using ``inputs.beta`` (the
  per-stock rolling beta from research/portfolio/beta.py — NOT the risk
  model's constant ``"market"`` exposure column, which is 1.0 for every
  stock and would make this collapse to dollar-neutral again).
- **sector-neutral**: each ``sector_*`` column of ``inputs.B`` dotted
  with ``w`` == 0.
- **position limits, liquidity-relative**: ``|w_i| <= (adv_days *
  adv_i) / book_notional`` — a days-of-ADV cap converted into
  weight-space by ``book_notional`` (placeholder — no real capital
  figure exists anywhere in this project; Alpaca paper trading has no
  bearing on the number, it's a pure QP-scaling constant), not a flat
  percent of book (DESIGN.md is explicit: "fine for AAPL, untradeable
  for name #997").
- **turnover cap**: ``norm1(w - w_prev) <= turnover_cap``.
- **gross leverage cap**: ``norm1(w) <= gross_cap``.
- **factor exposure bounds**: every non-sector, non-market column of
  ``inputs.B`` (i.e. the style factors — momentum, low_vol) bounded to
  ``[-factor_exposure_cap, +factor_exposure_cap]``.

Deliberately NOT implemented:
- **Net leverage limit**: with dollar-neutral (``sum(w) == 0``) already
  enforced, net exposure is always exactly 0 — a separate net-leverage
  constraint would be redundant given this book's structure.
- The risk model's constant ``"market"`` exposure column is left
  unconstrained here too, for the same reason: ``B[:, market] @ w ==
  sum(w)`` (every entry is 1.0), already forced to 0 by dollar-neutral.
- **Borrow-availability filter** (exclude/cap hard-to-borrow shorts):
  no free borrow-rate/availability data source exists anywhere in the
  lake (DESIGN.md's own Block 5 section already flags this as hard to
  get). Documented gap, not a design choice.

All numeric bounds (``gross_cap``, ``turnover_cap``,
``factor_exposure_cap``, ``adv_days``, ``book_notional``) are placeholder
constants — nothing calibrates them yet without a working backtester,
same posture as block 4a's ``shrink``/``cap``.
"""

from __future__ import annotations

import cvxpy as cp

from research.portfolio.inputs import OptimizerInputs


def build_constraints(
    inputs: OptimizerInputs,
    w: cp.Variable,
    *,
    gross_cap: float = 2.0,
    turnover_cap: float = 0.5,
    factor_exposure_cap: float = 0.5,
    adv_days: float = 5.0,
    book_notional: float = 10_000_000.0,
) -> list[cp.Constraint]:
    """Constraint list for ``w`` (shape ``(N,)``, aligned to ``inputs.security_ids``)."""
    constraints: list[cp.Constraint] = [
        cp.sum(w) == 0,
        inputs.beta @ w == 0,
        cp.norm1(w - inputs.w_prev) <= turnover_cap,
        cp.norm1(w) <= gross_cap,
        cp.abs(w) <= (adv_days * inputs.adv) / book_notional,
    ]

    for i, name in enumerate(inputs.factor_names):
        if name == "market":
            continue
        column = inputs.B[:, i]
        if name.startswith("sector_"):
            constraints.append(column @ w == 0)
        else:
            constraints.append(cp.abs(column @ w) <= factor_exposure_cap)

    return constraints
