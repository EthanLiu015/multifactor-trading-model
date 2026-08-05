"""Risk model orchestration (Block 3): assembles Σ = B·F·Bᵀ + D.

Ties together exposures.py, regression.py, factor_covariance.py, and
specific_variance.py: build exposures for each rebalance date, run the
cross-sectional regression to get that date's factor/specific returns,
accumulate a history across many dates, estimate F and D from that
history, then assemble Σ for the target date's exposure matrix.

**Known simplification**: research/risk/exposures.py drops a different
reference sector per date (whichever is alphabetically first AMONG
SECTORS PRESENT that day) to avoid the market/sector-dummy multicollinearity
trap — so the factor-return columns can differ date to date (a sector with
zero members one month, present the next). Rather than reconcile that
here, dates missing any factor in the common set are simply excluded from
the factor-covariance/specific-variance history — consistent with this
codebase's "absent means insufficient data, never fabricated" convention,
at the cost of using less history than technically available. A production
version would use a constrained (not reference-dropping) regression to
keep every date's columns identical; out of scope for this v1.
"""

from __future__ import annotations

import dataclasses
import datetime as dt

import numpy as np
import polars as pl

from research.data import PITStore
from research.risk.exposures import build_exposure_matrix
from research.risk.factor_covariance import build_factor_covariance
from research.risk.regression import cross_sectional_regression
from research.risk.specific_variance import build_specific_variance

BARS_DATASET = "yfinance_daily"
UNIVERSE_DATASET = "universe_monthly"
SECTOR_DATASET = "yfinance_sector_current"


@dataclasses.dataclass
class RiskModel:
    rebuild_date: dt.date
    security_ids: list[str]
    factor_names: list[str]
    B: np.ndarray  # N x K exposures
    F: np.ndarray  # K x K factor covariance
    D: np.ndarray  # N specific variances (diagonal of D)
    shrinkage: float

    def sigma(self) -> np.ndarray:
        """Full N×N stock covariance Σ = B·F·Bᵀ + diag(D).

        **May emit spurious numpy RuntimeWarnings on macOS** (divide by
        zero / overflow / invalid value in matmul) — confirmed benign,
        not a real bug: numpy here is backed by Apple's Accelerate BLAS
        (``np.show_config()``), a documented source of false-positive FP
        exception flags during blocked matmul even on fully finite,
        well-conditioned inputs. Verified 2026-07-19 against the real
        lake: 147 such warnings fired across one build, while explicit
        ``np.isnan``/``np.isinf`` checks on every intermediate (B, F, D)
        and the final Σ all passed. Don't re-chase this warning without
        first checking the actual values for non-finite entries.
        """
        return self.B @ self.F @ self.B.T + np.diag(self.D)


def build_factor_return_history(
    store: PITStore,
    start_year: int,
    end_year: int,
    *,
    knowledge_ts: dt.datetime | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Per-date exposures -> regression, stacked into factor + specific return
    history, plus the exposure matrices themselves.

    Returns ``(factor_return_history, specific_return_history,
    exposure_history)``. ``factor_return_history``: [effective_date, <factor
    columns>] with nulls where a date's exposure matrix didn't include that
    factor (see module docstring); callers needing a clean matrix should
    ``.drop_nulls()``. ``specific_return_history``: [effective_date,
    security_id, specific_return], every date concatenated.
    ``exposure_history``: [effective_date, security_id, <factor columns>],
    the same per-date ``build_exposure_matrix`` output this function already
    computes internally for the regression -- exposed for
    research/attribution/decompose.py rather than recomputed there.
    """
    if knowledge_ts is None:
        knowledge_ts = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

    bars = store.asof(BARS_DATASET, knowledge_ts, keys=["security_id"])
    universe = store.asof(UNIVERSE_DATASET, knowledge_ts, keys=["security_id"])
    sectors = (
        store.asof(SECTOR_DATASET, knowledge_ts, keys=["security_id"])
        .collect()
        .select("security_id", "sector")
    )

    rebuild_dates = sorted(
        d
        for d in universe.select(pl.col("effective_date").unique()).collect()[
            "effective_date"
        ]
        if start_year <= d.year <= end_year
    )

    factor_rows: list[dict] = []
    specific_frames: list[pl.DataFrame] = []
    exposure_frames: list[pl.DataFrame] = []
    for d in rebuild_dates:
        members = (
            universe.filter(pl.col("effective_date") == d)
            .select("security_id")
            .collect()["security_id"]
            .to_list()
        )
        exposures = build_exposure_matrix(bars, sectors, d, members)
        if exposures.is_empty():
            continue
        returns = (
            bars.filter(pl.col("effective_date") == d)
            .select("security_id", "ret")
            .collect()
        )
        factor_returns, specific = cross_sectional_regression(returns, exposures)
        if not factor_returns:
            continue
        factor_rows.append({"effective_date": d, **factor_returns})
        specific_frames.append(
            specific.with_columns(pl.lit(d, dtype=pl.Date).alias("effective_date"))
        )
        exposure_frames.append(exposures)

    factor_history = (
        pl.DataFrame(factor_rows)
        if factor_rows
        else pl.DataFrame(schema={"effective_date": pl.Date})
    )
    specific_history = (
        pl.concat(specific_frames)
        if specific_frames
        else pl.DataFrame(
            schema={
                "security_id": pl.String,
                "specific_return": pl.Float64,
                "effective_date": pl.Date,
            }
        )
    )
    exposure_history = (
        pl.concat(exposure_frames, how="diagonal")
        if exposure_frames
        else pl.DataFrame(schema={"effective_date": pl.Date, "security_id": pl.String})
    )
    return factor_history, specific_history, exposure_history


def build_risk_model(
    store: PITStore,
    rebuild_date: dt.date,
    *,
    lookback_years: int = 3,
    halflife_days: float = 63.0,
    knowledge_ts: dt.datetime | None = None,
) -> RiskModel | None:
    """Full Σ = B·F·Bᵀ + D for ``rebuild_date``, using trailing history for F and D.

    ``None`` if there isn't enough history (fewer than 2 usable rebalance
    dates) to estimate a covariance at all.
    """
    if knowledge_ts is None:
        knowledge_ts = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

    factor_history, specific_history, _exposure_history = build_factor_return_history(
        store,
        rebuild_date.year - lookback_years,
        rebuild_date.year,
        knowledge_ts=knowledge_ts,
    )
    factor_history = factor_history.filter(pl.col("effective_date") <= rebuild_date)
    specific_history = specific_history.filter(pl.col("effective_date") <= rebuild_date)
    complete = factor_history.drop_nulls()
    if complete.height < 2:
        return None

    factor_names = [c for c in complete.columns if c != "effective_date"]
    F, shrinkage = build_factor_covariance(
        complete.select(factor_names).to_numpy(), halflife_days=halflife_days
    )
    D_df = build_specific_variance(specific_history, halflife_days=halflife_days)

    bars = store.asof(BARS_DATASET, knowledge_ts, keys=["security_id"])
    universe = store.asof(UNIVERSE_DATASET, knowledge_ts, keys=["security_id"])
    sectors = (
        store.asof(SECTOR_DATASET, knowledge_ts, keys=["security_id"])
        .collect()
        .select("security_id", "sector")
    )
    members = (
        universe.filter(pl.col("effective_date") == rebuild_date)
        .select("security_id")
        .collect()["security_id"]
        .to_list()
    )
    exposures = build_exposure_matrix(bars, sectors, rebuild_date, members)
    # Only the factors also present in the covariance history are usable.
    usable = [c for c in factor_names if c in exposures.columns]
    exposures = exposures.filter(
        pl.all_horizontal([pl.col(c).is_not_null() for c in usable])
    )
    exposures = exposures.join(D_df, on="security_id", how="inner")
    if exposures.is_empty():
        return None

    factor_idx = [factor_names.index(c) for c in usable]
    B = exposures.select(usable).to_numpy()
    F_usable = F[np.ix_(factor_idx, factor_idx)]
    D = exposures["specific_variance"].to_numpy()

    return RiskModel(
        rebuild_date=rebuild_date,
        security_ids=exposures["security_id"].to_list(),
        factor_names=usable,
        B=B,
        F=F_usable,
        D=D,
        shrinkage=shrinkage,
    )
