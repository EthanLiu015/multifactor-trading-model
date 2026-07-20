import polars as pl
import pytest

from research.risk.regression import cross_sectional_regression


def test_recovers_known_coefficients_with_zero_noise():
    # y = 0.01*market + 0.02*mom - 0.005*low_vol, exactly, no noise.
    exposures = pl.DataFrame(
        {
            "security_id": ["A", "B", "C", "D"],
            "market": [1.0, 1.0, 1.0, 1.0],
            "momentum": [1.0, -1.0, 0.5, -0.5],
            "low_vol": [0.2, 0.8, -0.3, 1.1],
        }
    )
    true_coefs = {"market": 0.01, "momentum": 0.02, "low_vol": -0.005}
    rets = [
        true_coefs["market"] * row["market"]
        + true_coefs["momentum"] * row["momentum"]
        + true_coefs["low_vol"] * row["low_vol"]
        for row in exposures.iter_rows(named=True)
    ]
    returns = pl.DataFrame({"security_id": ["A", "B", "C", "D"], "ret": rets})

    factor_returns, specific = cross_sectional_regression(returns, exposures)

    assert factor_returns["market"] == pytest.approx(0.01)
    assert factor_returns["momentum"] == pytest.approx(0.02)
    assert factor_returns["low_vol"] == pytest.approx(-0.005)
    assert specific["specific_return"].abs().max() == pytest.approx(0.0, abs=1e-10)


def test_drops_securities_missing_from_either_side():
    exposures = pl.DataFrame(
        {
            "security_id": ["A", "B", "C", "D"],
            "market": [1.0, 1.0, 1.0, 1.0],
            "momentum": [1.0, 0.5, -0.5, 0.3],
        }
    )
    returns = pl.DataFrame(
        {"security_id": ["A", "B", "C"], "ret": [0.01, 0.02, -0.01]}
    )  # D missing from returns, exposures has no E -> both-direction drop

    _, specific = cross_sectional_regression(returns, exposures)
    assert set(specific["security_id"].to_list()) == {"A", "B", "C"}


def test_null_ret_excluded_not_corrupted():
    # Real bug (2026-07-19): the loader's known first-bar-of-year-chunk
    # null `ret` flowed unfiltered into y, became NaN via .to_numpy(), and
    # corrupted lstsq's coefficients -> RuntimeWarnings against the real
    # lake (divide-by-zero/overflow/invalid-value in every downstream
    # matmul: regression residuals, LedoitWolf, Newey-West, sigma()).
    exposures = pl.DataFrame(
        {
            "security_id": ["A", "B", "C", "D", "E"],
            "market": [1.0] * 5,
            "momentum": [1.0, -1.0, 0.5, -0.5, 0.2],
        }
    )
    returns = pl.DataFrame(
        {"security_id": ["A", "B", "C", "D", "E"], "ret": [0.01, 0.02, None, -0.01, 0.015]}
    )

    factor_returns, specific = cross_sectional_regression(returns, exposures)

    assert "C" not in specific["security_id"].to_list()
    assert specific.height == 4
    assert all(v == v for v in factor_returns.values())  # v==v is False for NaN
    assert not specific["specific_return"].is_nan().any()


def test_underdetermined_returns_empty():
    # 1 observation, 2 factors -> underdetermined, no reliable fit.
    exposures = pl.DataFrame({"security_id": ["A"], "market": [1.0], "momentum": [1.0]})
    returns = pl.DataFrame({"security_id": ["A"], "ret": [0.01]})

    factor_returns, specific = cross_sectional_regression(returns, exposures)
    assert factor_returns == {}
    assert specific.is_empty()
