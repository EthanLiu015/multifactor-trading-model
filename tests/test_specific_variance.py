import datetime as dt

import polars as pl
import pytest

from research.risk.specific_variance import build_specific_variance


def _dates(n):
    return [dt.date(2020, 1, 1) + dt.timedelta(days=i) for i in range(n)]


def test_constant_returns_give_zero_variance():
    dates = _dates(20)
    df = pl.DataFrame(
        {
            "effective_date": dates,
            "security_id": ["AAA"] * 20,
            "specific_return": [0.001] * 20,
        }
    )
    out = build_specific_variance(df)
    assert out["specific_variance"][0] == pytest.approx(0.0, abs=1e-12)


def test_varying_returns_give_positive_variance():
    dates = _dates(20)
    df = pl.DataFrame(
        {
            "effective_date": dates,
            "security_id": ["AAA"] * 20,
            "specific_return": [0.01 if i % 2 == 0 else -0.01 for i in range(20)],
        }
    )
    out = build_specific_variance(df)
    assert out["specific_variance"][0] > 0.0


def test_single_observation_excluded():
    df = pl.DataFrame(
        {
            "effective_date": [dt.date(2020, 1, 1)],
            "security_id": ["AAA"],
            "specific_return": [0.01],
        }
    )
    out = build_specific_variance(df)
    assert out.is_empty()


def test_empty_input_returns_empty():
    out = build_specific_variance(
        pl.DataFrame(
            schema={
                "effective_date": pl.Date,
                "security_id": pl.String,
                "specific_return": pl.Float64,
            }
        )
    )
    assert out.is_empty()
