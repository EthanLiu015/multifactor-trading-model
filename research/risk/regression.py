"""Cross-sectional factor regression (Block 3 risk model).

One OLS regression per rebalance date: that date's realized return ~ that
date's exposures (research/risk/exposures.py). The regression coefficients
ARE the factor returns for that date (DESIGN.md: "daily cross-sectional
regression of returns on exposures B gives factor returns f_t"); the
residuals are specific returns, which feed specific_variance.py.

May emit spurious numpy RuntimeWarnings on macOS (Apple Accelerate BLAS
quirk, confirmed benign) — see research/risk/model.py's ``RiskModel.sigma``
docstring before treating one as a real bug.
"""

from __future__ import annotations

import numpy as np
import polars as pl

SPECIFIC_RETURN_SCHEMA = {"security_id": pl.String, "specific_return": pl.Float64}


def cross_sectional_regression(
    returns: pl.DataFrame,
    exposures: pl.DataFrame,
) -> tuple[dict[str, float], pl.DataFrame]:
    """OLS regression of returns on exposures for one date.

    ``returns``: [security_id, ret]. ``exposures``: [security_id, <factor
    columns>] (effective_date, if present, is ignored here). Securities
    missing from either side, or with a NULL ``ret`` (the loader's known
    first-bar-of-year-chunk null — see yfinance_daily.py's module
    docstring), are dropped via inner join before conversion to numpy —
    a null silently became NaN via ``.to_numpy()`` and corrupted every
    downstream matmul with RuntimeWarnings until this was caught against
    the real lake (2026-07-19, see docs/METRICS.md). Same "absent means
    insufficient data" convention as the exposures themselves, never
    imputed.

    Returns ``({factor_name: coefficient}, specific_returns_df)``. Empty
    results if there are fewer observations than factors (underdetermined,
    no reliable fit).
    """
    factor_cols = [
        c for c in exposures.columns if c not in ("effective_date", "security_id")
    ]
    joined = exposures.select("security_id", *factor_cols).join(
        returns.select("security_id", "ret").filter(pl.col("ret").is_not_null()),
        on="security_id",
        how="inner",
    )
    if joined.height < len(factor_cols) + 1:
        return {}, pl.DataFrame(schema=SPECIFIC_RETURN_SCHEMA)

    X = joined.select(factor_cols).to_numpy()
    y = joined["ret"].to_numpy()
    coefs, *_ = np.linalg.lstsq(X, y, rcond=None)
    residuals = y - X @ coefs

    factor_returns = dict(zip(factor_cols, coefs.tolist()))
    specific_returns = pl.DataFrame(
        {"security_id": joined["security_id"], "specific_return": residuals}
    )
    return factor_returns, specific_returns
