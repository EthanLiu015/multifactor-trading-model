"""Factor exposure matrix B (Block 3 risk model).

Per rebalance date: one row per universe member, columns = market (constant
1.0) + sector dummies (one dropped as reference — see below) + z-scored
style factors (momentum, low-vol, reused from research/signals/).

**Known limitation, documented not hidden**: sector comes from
``yfinance_sector_current``, a CURRENT snapshot only (yfinance has no free
historical sector-reassignment source) — the same caveat as
``yfinance_shares_current``. A 2013 rebalance date uses 2026's sector
classification. Reasonable approximation since sector reclassification is
rare/slow relative to price, but genuinely not point-in-time correct.

**Multicollinearity fix**: every stock has market=1 and belongs to exactly
one sector, so market ≡ sum(all sector dummies) — a singular design matrix
(the "dummy variable trap"). Fixed by dropping one sector (alphabetically
first among sectors actually present that date) as the reference category;
its coefficient is implicitly folded into market. The other sectors'
factor returns are then relative-to-reference, not absolute.

Securities missing ANY exposure (no sector row, NULL sector value — a few
real tickers failed yfinance's ``.info`` resolution, see docs/METRICS.md —
or insufficient signal history) are excluded from that date's cross-section
entirely — consistent with research/signals/'s own "absent means
insufficient data" convention, never a fabricated/imputed value.
"""

from __future__ import annotations

import datetime as dt

import polars as pl

from research.signals.low_vol import compute_low_vol
from research.signals.momentum import compute_momentum

EXPOSURE_META_COLS = ("effective_date", "security_id")


def _zscore(df: pl.DataFrame, col: str) -> pl.DataFrame:
    return df.with_columns(
        ((pl.col(col) - pl.col(col).mean()) / pl.col(col).std()).alias(col)
    )


def build_exposure_matrix(
    bars: pl.LazyFrame,
    sectors: pl.DataFrame,
    rebuild_date: dt.date,
    members: list[str],
) -> pl.DataFrame:
    """Exposure matrix B for one rebalance date.

    ``sectors`` is the already-asof'd ``yfinance_sector_current`` frame
    (security_id, sector); ``members`` is that date's universe membership
    (from ``universe_monthly``).
    """
    mom = compute_momentum(bars, rebuild_date).select("security_id", "signal_value")
    lv = compute_low_vol(bars, rebuild_date).select("security_id", "signal_value")

    base = (
        pl.DataFrame({"security_id": members})
        .join(
            sectors.select("security_id", "sector").filter(pl.col("sector").is_not_null()),
            on="security_id",
            how="inner",
        )
        .join(mom, on="security_id", how="inner")
        .rename({"signal_value": "momentum"})
        .join(lv, on="security_id", how="inner")
        .rename({"signal_value": "low_vol"})
    )
    if base.is_empty():
        return base.with_columns(
            pl.lit(rebuild_date, dtype=pl.Date).alias("effective_date")
        )

    reference_sector = sorted(base["sector"].unique().to_list())[0]
    sector_names = sorted(s for s in base["sector"].unique().to_list() if s != reference_sector)

    result = base.with_columns(
        pl.lit(rebuild_date, dtype=pl.Date).alias("effective_date"),
        pl.lit(1.0).alias("market"),
        *[
            (pl.col("sector") == name).cast(pl.Float64).alias(f"sector_{name}")
            for name in sector_names
        ],
    )
    result = _zscore(result, "momentum")
    result = _zscore(result, "low_vol")
    return result.select(
        "effective_date",
        "security_id",
        "market",
        *[f"sector_{name}" for name in sector_names],
        "momentum",
        "low_vol",
    )
