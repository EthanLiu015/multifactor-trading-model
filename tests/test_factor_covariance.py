import numpy as np
import pytest

from research.risk.factor_covariance import build_factor_covariance


def test_shape_symmetry_and_shrinkage_bounds():
    rng_pattern = np.array([0.01, -0.01, 0.02, -0.02, 0.005] * 40)  # T=200
    factor_a = rng_pattern
    factor_b = rng_pattern * 2.0  # perfectly correlated with a
    factor_c = np.roll(rng_pattern, 2)  # same values, different phase
    history = np.column_stack([factor_a, factor_b, factor_c])

    F, shrinkage = build_factor_covariance(history, halflife_days=63.0)

    assert F.shape == (3, 3)
    assert F == pytest.approx(F.T, abs=1e-10)  # symmetric
    assert np.all(np.diag(F) > 0)  # positive variance, shrinkage keeps it off zero
    assert 0.0 <= shrinkage <= 1.0


def test_correlated_factors_show_higher_covariance_than_uncorrelated():
    t = np.arange(200)
    factor_a = np.sin(t * 0.3) * 0.01
    factor_b = factor_a * 1.5  # perfectly correlated, same phase
    factor_c = np.sin(t * 0.3 + np.pi / 2) * 0.01  # 90-degree phase shift, ~uncorrelated
    history = np.column_stack([factor_a, factor_b, factor_c])

    F, _ = build_factor_covariance(history, halflife_days=1000.0)  # near-uniform weights

    assert abs(F[0, 1]) > abs(F[0, 2])  # a-b (correlated) > a-c (uncorrelated)


def test_recent_weighted_more_than_old_with_short_halflife():
    # Old regime: a,b uncorrelated. Recent regime: a,b perfectly correlated.
    # A short halflife should pick up the recent correlation; a long one dilutes it.
    t = np.arange(300)
    old_a = np.sin(t * 0.3) * 0.01
    old_b = np.sin(t * 0.3 + np.pi / 2) * 0.01  # uncorrelated with old_a
    recent_a = np.array([0.01, -0.01] * 50)
    recent_b = recent_a * 2.0  # perfectly correlated with recent_a
    factor_a = np.concatenate([old_a, recent_a])
    factor_b = np.concatenate([old_b, recent_b])
    history = np.column_stack([factor_a, factor_b])

    F_short, _ = build_factor_covariance(history, halflife_days=10.0)
    F_long, _ = build_factor_covariance(history, halflife_days=5000.0)

    assert abs(F_short[0, 1]) > abs(F_long[0, 1])
