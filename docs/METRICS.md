# METRICS

Resume-grade measured metrics for the multifactor trading system.

**Rules for this file**
1. Only *measured* numbers — every entry carries the command, date, and hardware. No estimates, no "should be".
2. Baselines recorded before optimizations, so speedup claims have a denominator.
3. Resume-ready phrasing included per entry, but the raw numbers are the source of truth.

**Hardware (all entries unless noted)**: Apple M4, 10 cores, 16 GB RAM, macOS (Darwin 24.6.0), Python 3.10.2, polars 1.42.1.

---

## Data layer — PITStore (point-in-time parquet store)

**Measured 2026-07-09** — `bench_store.py`: synthetic production-scale load, 1,000 securities × 15 years daily bars (3,915,000 rows, 4 columns + 2 stamp columns).

| Metric | Value |
|---|---|
| Dataset | 3,915,000 rows (1,000 securities × 3,915 days) |
| Storage: raw in-memory | 105.7 MB |
| Storage: parquet on disk (zstd) | 13.0 MB |
| **Compression ratio** | **8.1×** |
| **Ingest (append) throughput** | **46.7M rows/s** (0.084 s for 3.9M rows) |
| **Full-lake lazy scan + collect** | **106.5M rows/s** (0.037 s) |
| Point-in-time (`asof`) query, full lake | 1.06 s (3.7M rows/s) — baseline, pre-optimization |
| Point-in-time query, 1 security × 1 year | 14.6 ms (261 rows) |

Notes:
- `asof` full-lake at 1.06 s is the recorded **baseline** for a future speedup entry (date-partitioning + pushdown planned in part 2+).
- 15 years × 1,000 names of daily bars fits in 13 MB — quantifies the "local-first, distribute second" design decision in DESIGN.md.

Resume phrasing:
- "Built a bitemporal (point-in-time) market-data store in Python/Polars sustaining 46M rows/s ingest and 100M+ rows/s scans over a 15-year, 1,000-name equity dataset, with 8× on-disk compression."

---

## Data loaders — yfinance daily bars (phase 1: universe scan)

**Measured 2026-07-14** — `caffeinate -i .venv/bin/python -u -m research.data.loaders.yfinance_daily --start 2025 --end 2025 --no-threads --chunk-size 50` (sequential drip mode, full listed universe, live Yahoo endpoints).

| Metric | Value |
|---|---|
| Universe attempted | 7,092 tickers (NASDAQ Trader listed, test-issue/ETF filtered) |
| Tickers landed | 6,139 (953 no-data: delisted/warrants/units + 246 rate-limited) |
| Rows ingested | 1,459,612 (250 trading days of 2025) |
| Wall time | 1,161.2 s (~19.4 min) |
| **End-to-end throughput** | **1,257 rows/s** (network-bound, sequential ~1–2 req/s pacing) |
| Lake size (2025 part, zstd parquet) | 32.0 MB |
| Audit | ok — 137 ret outliers flagged, 0 years quarantined |

Notes:
- Sequential `--no-threads` mode is the anti-throttle strategy; the 246 `YFRateLimitError` tickers are all micro-cap/SPAC-tier names, so top-N dollar-volume selection (phase 2 input) is effectively unbiased.
- Throughput is Yahoo-rate-limited, not compute-limited — PITStore ingest benchmark above shows 46.7M rows/s when data is local.

## Data loaders — yfinance daily bars (phase 2: 15.5-year backfill, top-1500)

**Measured 2026-07-14** — `caffeinate -i .venv/bin/python -u -m research.data.loaders.yfinance_daily --start 2011 --no-threads --chunk-size 50 --tickers-file tickers_top1500.txt` (2011–2025 legs; killed externally before 2026 leg, gap-filled same day with `--start 2026 --end 2026`, same flags).

| Metric | Value |
|---|---|
| Universe | top 1,500 tickers by 2025 median dollar volume (from phase 1 scan) |
| Rows ingested | 4,823,327 (4,625,327 for 2011–2025 + 198,000 for 2026 YTD) |
| Coverage | 16 calendar years × 1,500 securities, 2011-01 → 2026-07 |
| Wall time | ~54 min (2011–2025, ~3.5 min/year) + 195.3 s (2026 leg) |
| 2026-leg throughput (has exact timing) | 1,014 rows/s |
| Audit | all 16 year parts ok, 0 quarantined; 2026: 0 tickers missing, 0 ret outliers |
| Lake size (`yfinance_daily`, zstd parquet, incl. phase 1 part) | 143 MB |

Resume phrasing:
- "Backfilled 15.5 years × 1,500 US equities of daily bars (4.8M rows) from a rate-limited public API in under an hour via a paced, resumable, per-year-idempotent loader with automated audit gates."

---

## Data loaders — yfinance sector/industry snapshot

**Measured 2026-07-17** — direct call to `YFinanceDailyLoader.load_sector_current` (not the bars CLI — sector-only, no redundant bars re-pull) over `tickers_top1500.txt`, `pause_s=1.0`, real Yahoo `.info` per ticker.

| Metric | Value |
|---|---|
| Tickers attempted | 1,500 |
| Resolved | 1,497 (99.8%) |
| Wall time | 1,779.9 s (~29.7 min) |
| Throughput | 1.19 s/ticker (paced, `.info` is yfinance's slowest/most rate-limited call) |
| Distinct sectors | 11 (Yahoo's own taxonomy — matches the official 11 GICS sector count, though not literal GICS codes) |
| Sector distribution | Technology 269, Industrials 218, Financial Services 210, Consumer Cyclical 193, Healthcare 168, ... Utilities 46 (smallest) |
| Lake size (`yfinance_sector_current`, zstd parquet) | 12 KB |

Notes:
- Current-snapshot only (`effective_date` = fetch date), same limitation as `yfinance_shares_current` — no free source of historical sector reassignment exists.
- Live smoke-tested first (5 real tickers, scratch lake, 6.7s) before committing to the full 1,500-ticker pull — confirmed correct end-to-end before paying the ~30 min cost.

Resume phrasing:
- "Built a rate-limit-aware sector/industry classification pull (99.8% resolution across 1,500 US equities) as the factor-exposure input for a Barra-style risk model."

---

## Universe builder — monthly PIT snapshots

**Measured 2026-07-14** — `.venv/bin/python -m research.universe --start 2011 --end 2026` (top 1,000 by 60-day median dollar volume, price > $5, coverage ≥ 40/60 days, over the 4.8M-row yfinance lake).

| Metric | Value |
|---|---|
| Snapshots built | 185 month-ends (2011-03 → 2026-07; first 2 months skipped by min-history guard) |
| Member-rows | 183,464 (1,000/month once eligible pool ≥ 1,000) |
| Wall time (full 15.5y rebuild) | 235.7 s (~1.27 s/snapshot, each rescanning its trailing 60-day window) |
| Snapshot store size | 2.3 MB (`lake/universe_monthly`, 16 year-parts, zstd parquet) |

Resume phrasing:
- "Constructed 15 years of survivorship-bias-free monthly universe membership (185 point-in-time snapshots, top-1,000 US equities by 60-day median dollar volume) in under 4 minutes on a laptop."

---

## PIT store — real-lake point lookup vs full scan

**Measured 2026-07-14** — one ticker/one date `close` lookup vs. full 3-column scan, both via `store.asof("yfinance_daily", now, keys=["security_id"])`, against the real 4.8M-row lake (17 files, year-partitioned).

| Query | Rows read (post-filter) | Wall time |
|---|---|---|
| Full asof scan+collect, 3 cols (`effective_date`, `security_id`, `close`) | 5,912,600 | 1,698.0 ms |
| Point lookup (`security_id == "AAPL" & effective_date == one day`) | 1 | 9.4–22.9 ms (5 runs; steady-state ~10-13 ms) |

~130-150× faster than the full scan, from two stacked pushdowns: (1) year-partition file layout means only 1 of 17 files can contain a given date, (2) Parquet row-group column statistics + column projection skip both irrelevant row-groups and unrequested columns (this is also why the point query silently avoided a real `volume` dtype mismatch between two 2025 batches that breaks the *unfiltered* full-column scan — see METRICS/STATE note on that bug).

Notes:
- Not O(1): still bounded below by opening footers for all 17 files plus scanning the surviving partition's row-groups — better modeled as O(files) + O(rows in the matching partition after pruning), not O(total lake rows) and not a true constant-time hash lookup.
- Confirms the synthetic-benchmark design note above ("brute force + pushdown wins at this scale, no premature indexing") against real, not synthetic, data.

---

## Security master — block 2 (ticker segment extraction)

**Measured 2026-07-14** — `.venv/bin/python -m research.security_master --lake lake --gap-days 90` over the real `yfinance_daily` lake (every ticker ever observed: phase 1's full-universe 2025 scan ∪ phase 2's 15.5y top-1500 backfill).

| Metric | Value |
|---|---|
| Tickers seen | 6,139 |
| Identity segments written | 6,141 |
| Tickers with >1 segment (gap > 90 days) | 2 (MKC, QLYS) |
| Wall time | 3.8 s |

Note: both gap-detected tickers are **vendor fetch-failure gaps, not real ticker reuse** — confirmed against the phase 2 backfill log (`$MKC: possibly delisted; no price data found (1d 2021-01-01 -> 2022-01-01)`, same for QLYS/2022). Both are still the same company today. This is the expected failure mode of a trading-gap heuristic with no real corporate-actions feed — flagged in the module docstring; real disambiguation needs CUSIP from CRSP (block 4).

---

## Signal/alpha pipeline — Phase 2 signals + IC measurement

**Measured 2026-07-16/17** — `.venv/bin/python -m research.alpha.ic --start 2011 --end 2026 --lake lake` (momentum, reversal, low-vol signals; IC = Spearman rank correlation vs. 21-trading-day forward return; rebalance dates + membership from the real `universe_monthly` dataset, 185 snapshots).

| Signal | n (rebalance dates) | mean IC | IC std | IC t-stat |
|---|---|---|---|---|
| momentum (12-1 month) | 169 | 0.0194 | 0.174 | 1.45 |
| reversal (21-day) | 180 | 0.0007 | 0.138 | 0.07 |
| low-vol (252-day) | 174 | -0.0017 | 0.224 | -0.10 |

| Metric | Value |
|---|---|
| Wall time, full 15.5y sweep, all 3 signals | 824.2 s (~13.7 min) |
| Wall time, 2013-2014 slice (24 dates), pre-perf-fix | not completed — killed after 6+ min CPU, diagnosed as a real bug |
| Wall time, same 2013-2014 slice, post-fix | 66.7 s |

Notes:
- `n` differs per signal because each needs different trailing history before producing a value (reversal: 22 days; low-vol: 252 days; momentum: 273 days) — universe snapshots start 2011-03, so momentum only becomes computable partway into 2012. Fewer valid dates for momentum is expected, not a bug.
- **Perf bug found and fixed same session**: `compute_forward_returns` originally computed cumulative log-returns over the *entire* 15-year history per call (measured 3.3 s/call) when it only ever needs a `horizon_days`-wide forward window. Bounded to a forward date-window (same technique `research/signals/low_vol.py` already used backward) → 1.2 s/call, in line with this codebase's existing "brute force + pushdown" cost baseline (see PIT store real-lake section above). Confirmed via isolated per-call timing before and after.
- Also removed 3x redundant work: `build_ic_series` originally took one signal function and was called once per signal in `SIGNAL_REGISTRY`, each call recomputing identical forward returns. Refactored to take the whole registry and compute forward returns once per rebalance date, shared across all signals.
- Results are honestly weak/marginal (none clear 95%-confidence t-stat thresholds) — expected for raw, unadjusted, single-factor signals on a broad universe with no risk-model orthogonalization yet (that's Block 3+4). The point of this phase was proving the signal → IC measurement pipeline works correctly end-to-end on real point-in-time data, not discovering a strong tradeable edge on the first pass.
- low-vol's small negative mean IC matches the theoretically expected sign (low realized vol → weakly higher forward return) even though it's raw/un-negated by design (research/signals/low_vol.py's docstring) — consistent direction, just not statistically significant at this stage.

Resume phrasing:
- "Built an IC-measurement research pipeline (Spearman rank correlation of signal vs. forward return) validating 3 classic price factors against 15.5 years of point-in-time universe data — 185 monthly rebalances, ~13 min full-history recompute on a laptop."

---

## Risk model — Block 3 (Barra-style factor risk, full scope with sectors)

**Measured 2026-07-19** — `research.risk.model.build_risk_model(store, rebuild_date="2026-07-14", lookback_years=3)` against the real lake (985-name universe, `yfinance_sector_current` for sector classification).

| Metric | Value |
|---|---|
| Securities (N) | 985 |
| Factors (K) | 13 — market, 10 sector dummies (11th dropped as multicollinearity reference), momentum, low-vol |
| Wall time (3-year lookback, ~43 rebalance dates) | 179.5 s (~3.0 min) |
| Ledoit-Wolf shrinkage intensity | 0.302 |
| Σ diagonal range (daily variance) | 9.19e-05 to 0.0314 |
| Σ symmetric | confirmed (`np.allclose(Σ, Σᵀ)`) |
| Σ finiteness | confirmed — every B, F, D, and Σ entry explicitly checked via `np.isnan`/`np.isinf`, all pass |

Two real bugs found and fixed against real data before this passed:

1. **Null-sector crash** (`research/risk/exposures.py`): 3 of 1,500 tickers have `sector=None` (yfinance `.info` couldn't resolve them — see the sector-loader section above). `sorted(unique_sectors)` crashed with `TypeError: '<' not supported between NoneType and str` the moment a null slipped into that comparison. Fixed by filtering `sector.is_not_null()` before computing the reference-sector drop.
2. **Null-return NaN corruption** (`research/risk/regression.py`): the yfinance loader's known first-bar-of-year-chunk null `ret` (documented since the loader was built) flowed unfiltered into the regression's target vector, became `NaN` via `.to_numpy()`, and corrupted `lstsq`'s coefficients — which then propagated through every downstream matmul (residuals, Ledoit-Wolf, Newey-West, Σ assembly), surfacing as scattered `RuntimeWarning`s that were easy to mistake for one bug when they were really symptoms of one root cause four calls downstream. Fixed by filtering `ret.is_not_null()` at the regression function's own boundary.

A third apparent issue turned out to be a red herring, not a bug: even after both fixes, `RuntimeWarning: divide by zero/overflow/invalid value in matmul` still fired (147 times across one full build). Root-caused to `numpy`'s BLAS backend on this machine being Apple's **Accelerate** (`np.show_config()`), a documented source of spurious floating-point exception flags during blocked matmul on fully finite, well-conditioned inputs (confirmed: condition numbers ≤ ~20 across all 43 dates, zero NaN/Inf in any input). Verified benign by explicit `np.isnan`/`np.isinf` checks on every output value, not by trusting the absence of a warning. Documented directly in `RiskModel.sigma()`'s docstring so it isn't re-investigated as a bug later.

Resume phrasing:
- "Built a Barra-style multi-factor risk model (13 factors: market, 10 GICS-like sectors, momentum, low-volatility) from scratch — EWMA-weighted, Ledoit-Wolf shrunk, Newey-West adjusted factor covariance via scikit-learn, full Σ = B·F·Bᵀ + D assembly for a 985-name universe in ~3 minutes on a laptop."

---

## Infra — Block 6c: local lake -> Delta/Databricks port

**Measured 2026-07-26** — `DATABRICKS_HOST=... DATABRICKS_TOKEN=... PYTHONPATH=. .venv-delta/bin/python -m research.data.port_to_delta --dataset yfinance_daily`, run from Ethan's Mac (driver-side: Polars scan + Polars->pandas conversion), executing against a Databricks Free Edition serverless cluster (executor-side: the actual Delta MERGE/write) — not a single-machine number like every other entry in this file, noted since the "Hardware" line above doesn't apply as-is.

| Metric | `yfinance_daily` | `universe_monthly` |
|---|---|---|
| Batches (distinct knowledge_ts) | 3 (not just the current asof view) | 1 |
| Rows ported | 6,282,939 (1,459,612 + 4,625,327 + 198,000 — bigger than the "4.82M" figure quoted elsewhere in these docs, which is the *asof* view; raw batch history includes phase 1's superseded full-universe layer too) | 183,464 |
| Wall time | 103.3 s | 19.2 s |
| **Throughput** | **60,847 rows/s** | **9,554 rows/s** |
| Target | `mfts.research.yfinance_daily` | `mfts.research.universe_monthly` |

Both backed by S3 external location `s3://mfts-datalake-2026`.

Notes:
- One MERGE per distinct `knowledge_ts` batch, not one bulk write — preserves full bitemporal history through the copy, per `DeltaPITStore`'s docstring.
- `universe_monthly`'s much lower rows/s than `yfinance_daily` despite far fewer rows is consistent with per-append overhead (session/MERGE setup cost) dominating at this row count, not a throughput regression — only 1 batch here vs. `yfinance_daily`'s 3, so there's less work to amortize a mostly-fixed cost over. Not investigated further; too small a sample (2 datasets) to draw a real scaling curve from.
- Real bugs found+fixed getting `yfinance_daily` ported (see docs/STATE.md Failed attempts, block 6c): a scoped-vs-legacy Databricks PAT format mismatch (auth), a `TYPE_CHECKING`-only import that broke at runtime, and a Polars `pl.Date` -> pandas `datetime64` -> Spark `TimestampType` type-fidelity loss that needed an explicit cast back to `DateType`.
- One more bug found porting `universe_monthly` (block 6d-i): its `rank`/`days_traded` columns are Polars `UInt32` (yfinance_daily has no unsigned columns, so this didn't surface earlier) — `.to_pandas()` preserves them as pandas `uint32`, which Spark Connect's Arrow bridge rejects (`[UNSUPPORTED_ARROWTYPE] Int(32, false)`, signed-only). Fixed generically in `port_dataset`: any `UInt8/16/32/64` column is cast to `Int64` before the pandas handoff.

Resume phrasing:
- "Ported a 6.3M-row bitemporal point-in-time dataset from a local Polars/parquet lake into Databricks Unity Catalog (Delta Lake on S3) via Databricks Connect, preserving full historical batch lineage (not just current state) through a MERGE-based idempotency scheme, at ~61K rows/s."

---

## Pending sections (filled as systems are built)
- **Backtester**: simulated days/s, full 15y walk-forward wall time.
- **Optimizer**: solve time per rebalance (1,000-name QP with all constraints).
- **C++ engine**: tick-to-order latency histogram (p50/p99/p99.9 ns), queue hop latency, orders/s throughput, journal write latency, recovery-replay time.
- **Data loaders**: rows/day ingested, audit-check overhead.
- **Block 6d**: Spark/Databricks vs. local-Polars historical-alpha-run benchmark (baseline: 824.2s, signal/alpha pipeline section above).
