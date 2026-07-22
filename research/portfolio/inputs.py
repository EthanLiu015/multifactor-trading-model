"""Block 4a: optimizer inputs — aligned alpha + w_prev vectors against the risk model.

Assembles the per-security-name inputs the QP (block 4c) needs: factor
exposures B, factor covariance F, specific variance D (reused as-is from
research/risk/, kept in factor form rather than materialized into a full
N×N Σ — same "estimate ~210 factor covariances, not ~500,000 stock
covariances" rationale as DESIGN.md's risk-model section), an alpha
vector, and the previous target weight vector — all row-aligned to one
deterministic security order.

**Placeholder alpha, not real alpha research** (explicit decision,
2026-07-20, see docs/STATE.md Decisions): ``alpha`` is an equal-weight
blend of all 3 signals in ``research.signals.SIGNAL_REGISTRY``
(momentum/reversal/low_vol), z-scored then averaged — even though the
real IC measurement (docs/METRICS.md) shows only momentum carries a real
signal (t=1.45); reversal/low_vol are statistically noise (t=0.07,
t=-0.10). This blend exists to exercise the full optimizer pipeline, not
because it is a real alpha model — real signal-combination weights are
deferred to the alpha research phase.

A security is dropped from the cross-section for the date if it is
missing ANY of the 3 signals, the risk model's exposures, a computable
beta (research/portfolio/beta.py), or an ADV figure (universe_monthly's
``median_dollar_volume``, needed for block 4b's liquidity-relative
position caps) — consistent with research/risk/exposures.py's "absent
means insufficient data, never fabricated" convention. A resumed book's
missing prior weight defaults to 0.0 (new name / flat start), which is
not the same kind of absence — a security simply wasn't held, not a data
gap.

DESIGN.md's stated "optimizer is an error maximizer" defense: alpha is
shrunk toward zero and capped (``alpha_final = clip(shrink * alpha_raw,
-cap, cap)``) before being handed to the optimizer. ``shrink``/``cap``
are placeholder constants — nothing calibrates them yet without a working
backtester.
"""

from __future__ import annotations

import dataclasses
import datetime as dt

import numpy as np
import polars as pl

from research.data import PITStore
from research.portfolio.beta import compute_market_beta
from research.risk.model import BARS_DATASET, UNIVERSE_DATASET, build_risk_model
from research.signals import SIGNAL_REGISTRY


def _zscore(df: pl.DataFrame, col: str) -> pl.DataFrame:
    return df.with_columns(
        ((pl.col(col) - pl.col(col).mean()) / pl.col(col).std()).alias(col)
    )


@dataclasses.dataclass
class OptimizerInputs:
    rebuild_date: dt.date
    security_ids: list[str]
    factor_names: list[str]
    B: np.ndarray  # N x K, row-aligned to security_ids
    F: np.ndarray  # K x K factor covariance (unchanged by the name subset)
    D: np.ndarray  # N specific variances, row-aligned to security_ids
    alpha: np.ndarray  # N, row-aligned to security_ids
    beta: np.ndarray  # N, row-aligned to security_ids
    adv: np.ndarray  # N, row-aligned to security_ids ($ median daily dollar volume)
    w_prev: np.ndarray  # N, row-aligned to security_ids


def build_optimizer_inputs(
    store: PITStore,
    rebuild_date: dt.date,
    w_prev: pl.DataFrame | None = None,
    *,
    lookback_years: int = 3,
    shrink: float = 0.5,
    cap: float = 3.0,
    knowledge_ts: dt.datetime | None = None,
) -> OptimizerInputs | None:
    """Aligned optimizer inputs for one rebalance date.

    ``w_prev``: ``[security_id, weight]`` from the previous rebalance, or
    ``None`` for a flat starting book (every weight defaults to 0.0).

    ``None`` if the risk model can't be built (insufficient history) or
    no security has all 3 signals plus a risk exposure plus a computable
    beta plus an ADV figure that date — same "absent means insufficient
    data" propagation as :func:`research.risk.model.build_risk_model`.
    """
    if knowledge_ts is None:
        knowledge_ts = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

    risk_model = build_risk_model(
        store, rebuild_date, lookback_years=lookback_years, knowledge_ts=knowledge_ts
    )
    if risk_model is None:
        return None

    bars = store.asof(BARS_DATASET, knowledge_ts, keys=["security_id"])

    signal_names = list(SIGNAL_REGISTRY.keys())
    blended: pl.DataFrame | None = None
    for name in signal_names:
        sig = SIGNAL_REGISTRY[name](bars, rebuild_date).select(
            "security_id", "signal_value"
        )
        if sig.is_empty():
            return None
        sig = _zscore(sig, "signal_value").rename({"signal_value": name})
        blended = sig if blended is None else blended.join(
            sig, on="security_id", how="inner"
        )
    if blended is None or blended.is_empty():
        return None

    alpha_df = (
        blended.with_columns(pl.mean_horizontal(signal_names).alias("alpha_raw"))
        .with_columns((pl.col("alpha_raw") * shrink).clip(-cap, cap).alias("alpha"))
        .select("security_id", "alpha")
    )

    aligned = pl.DataFrame({"security_id": risk_model.security_ids}).join(
        alpha_df, on="security_id", how="inner", maintain_order="left"
    )
    if aligned.is_empty():
        return None

    # Beta computed over the alpha-surviving set — the actual tradable
    # cross-section that day, not the full risk-model universe.
    beta_df = compute_market_beta(bars, rebuild_date, aligned["security_id"].to_list())
    if beta_df.is_empty():
        return None
    aligned = aligned.join(beta_df, on="security_id", how="inner", maintain_order="left")
    if aligned.is_empty():
        return None

    adv_df = (
        store.asof(UNIVERSE_DATASET, knowledge_ts, keys=["security_id"])
        .filter(pl.col("effective_date") == rebuild_date)
        .select("security_id", "median_dollar_volume")
        .collect()
    )
    aligned = aligned.join(adv_df, on="security_id", how="inner", maintain_order="left")
    if aligned.is_empty():
        return None

    security_ids = aligned["security_id"].to_list()
    id_to_idx = {sid: i for i, sid in enumerate(risk_model.security_ids)}
    idx = [id_to_idx[sid] for sid in security_ids]

    if w_prev is None:
        w_prev_arr = np.zeros(len(security_ids))
    else:
        w_prev_arr = (
            aligned.select("security_id")
            .join(w_prev, on="security_id", how="left", maintain_order="left")
            .with_columns(pl.col("weight").fill_null(0.0))["weight"]
            .to_numpy()
        )

    return OptimizerInputs(
        rebuild_date=rebuild_date,
        security_ids=security_ids,
        factor_names=risk_model.factor_names,
        B=risk_model.B[idx],
        F=risk_model.F,
        D=risk_model.D[idx],
        alpha=aligned["alpha"].to_numpy(),
        beta=aligned["beta"].to_numpy(),
        adv=aligned["median_dollar_volume"].to_numpy(),
        w_prev=w_prev_arr,
    )
