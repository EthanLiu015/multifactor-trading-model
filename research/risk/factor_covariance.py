"""Factor covariance matrix F (Block 3 risk model).

DESIGN.md: "Factor covariance F: exponentially-weighted (recent data
counts more), Ledoit-Wolf shrinkage (K×K sample covariance is noisy),
Newey-West adjustment for autocorrelation in factor returns."

sklearn's ``LedoitWolf`` has no native sample-weight support, so EWMA
weighting is applied by rescaling rows before fitting: a weighted
covariance can be recovered from the *unweighted* (``assume_centered``)
covariance of sqrt(weight)-scaled, weighted-mean-centered rows — standard
reweighting trick for feeding a weighted problem to an unweighted
estimator. Newey-West is then added on top as lagged cross-covariance
terms (Bartlett kernel), using the same EWMA-scaled rows, per the
standard HAC (heteroskedasticity/autocorrelation-consistent) formula.
"""

from __future__ import annotations

import numpy as np
from sklearn.covariance import LedoitWolf


def _ewma_weights(n: int, halflife_days: float) -> np.ndarray:
    """n weights, oldest first, most recent = 1.0; normalized so mean = 1."""
    lags = np.arange(n - 1, -1, -1)  # n-1 (oldest) ... 0 (most recent)
    w = 0.5 ** (lags / halflife_days)
    return w * n / w.sum()


def _ewma_scaled_centered(
    factor_return_history: np.ndarray, halflife_days: float
) -> np.ndarray:
    n = factor_return_history.shape[0]
    weights = _ewma_weights(n, halflife_days)
    weighted_mean = np.average(factor_return_history, axis=0, weights=weights)
    centered = factor_return_history - weighted_mean
    return centered * np.sqrt(weights)[:, None]


def build_factor_covariance(
    factor_return_history: np.ndarray,
    halflife_days: float = 63.0,
    newey_west_lags: int = 5,
) -> tuple[np.ndarray, float]:
    """EWMA + Ledoit-Wolf shrunk + Newey-West adjusted factor covariance.

    ``factor_return_history``: (T, K), rows = dates oldest-first, columns
    = factors (from research/risk/regression.py's per-date coefficients,
    stacked over time). Returns ``(F, shrinkage_intensity)`` — F is K×K.
    """
    scaled = _ewma_scaled_centered(factor_return_history, halflife_days)

    lw = LedoitWolf(assume_centered=True).fit(scaled)
    F = lw.covariance_

    adjustment = np.zeros_like(F)
    n = scaled.shape[0]
    for lag in range(1, min(newey_west_lags, n - 1) + 1):
        gamma_l = (scaled[lag:].T @ scaled[:-lag]) / n
        kernel = 1.0 - lag / (newey_west_lags + 1)  # Bartlett kernel
        adjustment += kernel * (gamma_l + gamma_l.T)

    return F + adjustment, lw.shrinkage_
