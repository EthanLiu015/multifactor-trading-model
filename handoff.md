# HANDOFF — Multifactor Equity Trading System

> Primary-context document for any agent or developer continuing this project.
> Written 2026-07-13, last updated 2026-07-28. Ground truth hierarchy when documents disagree:
> **code + tests > docs/STATE.md > docs/DESIGN.md > this file > everything else.**
> Read docs/STATE.md first in every new session — it is the live state ledger.

---

## 1. Project purpose

Build a multifactor equity trading system that replicates a quant firm's internal stack end-to-end — data lake → signals → alpha → risk model → optimizer → C++ execution → attribution — following the **Grinold & Kahn active-management framework**.

Dual goals, both first-class:

1. **Learning** — the owner (Ethan, Duke sophomore targeting quant recruiting) is using the build to learn how each subsystem of a real quant stack works. This drives the *process* (see §9: explain-before-build) as much as the code.
2. **Resume artifact** — every subsystem is engineered and *measured* like production (docs/METRICS.md holds resume-grade numbers with commands and hardware). "Built on CRSP via WRDS", "bitemporal store", "lock-free C++ hot path" are deliberate recruiting signals.

The unifying theory: **IR = IC × √breadth** (fundamental law of active management). Every block's job is stated in those terms — signals raise IC, universe/cadence raise breadth, optimizer + execution protect the transfer coefficient.

## 2. Long-term vision (from docs/DESIGN.md — the canonical architecture doc)

Six blocks plus cross-cutting layers:

```
┌─────────────────┐
│ 1. Data+Signals │◄─────────────────────────────┐
└───────┬─────────┘                              │
        ▼                                        │ feedback loop
┌─────────────────┐    ┌──────────────┐          │ (edges decay)
│ 2. Alpha        │    │ 3. Risk model│          │
│    Forecast     │    │ (parallel)   │          │
└───────┬─────────┘    └──────┬───────┘          │
        ▼                     ▼                  │
┌─────────────────────────────────┐              │
│ 4. Portfolio construction (QP)  │              │
└───────┬─────────────────────────┘              │
        │  target holdings                       │
        ▼                                        │
┌─────────────────────────────────┐              │
│ 5. Implementation + trading     │ ← C++ hot path
└───────┬─────────────────────────┘              │
        ▼                                        │
┌─────────────────────────────────┐              │
│ 6. Performance analysis         │──────────────┘
└─────────────────────────────────┘
```

Locked decisions (do not relitigate; full table in DESIGN.md):

| Decision | Choice |
|---|---|
| Stack | C++ hot path (execution) + Python research stack |
| Execution | Alpaca paper trading (live data, real order lifecycle, zero risk) |
| Universe | Top ~1,000 US equities by 60d median dollar volume, point-in-time membership |
| Portfolio | Long-short, dollar-neutral + **beta-neutral** + sector-neutral |
| Cadence | Daily rebalance |
| Batch infra (later) | Databricks + Spark + Delta Lake on S3; kdb+ for live ticks |
| Data budget | Free sources only (+ WRDS/CRSP via university access) |
| PIT mechanism | Explicit bitemporal columns primary; Delta time-travel is audit layer only |
| Risk control | No per-name stop losses; book-level protection (drawdown kill switch) |

**Phasing rule — local-first, distribute second**: ~1,000 names × 15y daily ≈ a few GB; fits in Polars on a laptop (measured: 13 MB parquet). The distributed stack is a learning/resume showcase, ported *after* the vertical slice works locally. Never let infra gate alpha work.

## 3. Current implementation status (2026-07-28)

Honest inventory. **Built** means tested code in the repo; nothing else is.

| Component | Status | Evidence |
|---|---|---|
| PITStore (bitemporal parquet store) | **BUILT** | `research/data/store.py`, 5 tests |
| CRSP daily-bars loader (WRDS, CIZ format) | **BUILT, live-pull blocked** | `research/data/loaders/crsp_daily.py`, 6 offline tests. Duke WRDS access is academic-year only — no live pull until ~late Aug 2026. CIZ column names are **UNVERIFIED** against the live table (`verify_schema()` gates every pull) |
| yfinance interim loader + shared `audit.py` | **BUILT, backfill run** | `research/data/loaders/yfinance_daily.py`, `audit.py`; 11 offline tests. Two-phase real backfill complete: `lake/yfinance_daily` holds 2011–2026 YTD × top-1500 tickers by dollar volume (4.82M rows, 143 MB) — see §11 for measured throughput. Volume dtype bug **FIXED 2026-07-15** (§12 item 10) — `_transform` now casts volume to Float64; full-column `asof().collect()` works. Sector/industry snapshot added 2026-07-17 (`YFinanceClient.sector_info`/`load_sector_current`, dataset `yfinance_sector_current`) — real pull: 1,497/1,500 tickers resolved, 11 distinct sectors, ~29.7 min (docs/METRICS.md); factor-exposure input for the Block 3 risk model |
| Universe builder (part 3) | **BUILT** | `research/universe.py`, 9 tests. Real run: 185 monthly PIT snapshots (2011-03→2026-07), top-1000 by 60d median $ volume, price>$5, coverage filter, `lake/universe_monthly` (2.3 MB). Mcap filter deferred to CRSP (no shares data in yfinance bars) |
| Security master (part 4) | **blocks 1-3 of 4 BUILT** | `research/security_master.py`, 14 tests. Block 1: schema + PITStore fit. Block 2: `build_ticker_segments` extracts identity segments from the real lake via a trading-gap heuristic; real run found 2 gap tickers (MKC, QLYS), both confirmed **vendor data gaps, not real reuse** (§12 item 11). Block 3: `resolve_securities` (vectorized panel lookup, house no-loop rule) + `resolve_security` (scalar wrapper); real-lake probe confirms MKC resolves to the correct internal_id on each side of its gap and `None` inside it. Block 4 (CRSP permno/CUSIP hookup) blocked on WRDS |
| Phase 2: signals + IC measurement | **BUILT** | `research/signals/{momentum,reversal,low_vol}.py` + registry (`__init__.py`'s `SIGNAL_REGISTRY`), `research/alpha/ic.py` (`compute_forward_returns`, `compute_ic`, `build_ic_series`, `ic_summary`). 15 tests. Real run over the full 2011–2026 lake: momentum n=169 mean_ic=0.019 t=1.45, reversal n=180 mean_ic=0.0007 t=0.07, low_vol n=174 mean_ic=-0.0017 t=-0.10 (824.2s) — see docs/METRICS.md. Scope is momentum/reversal/low-vol only — value/quality/size need fundamentals not yet ingested (data-availability fact, not a preference). Registry pattern exists specifically so future (non-raw/simple) signals are one file + one line, not a rewrite |
| Risk model (Block 3) | **BUILT, real-lake verified** | `research/risk/` (exposures.py, regression.py, factor_covariance.py, specific_variance.py, model.py) — full Barra-style scope (market + 10 sector dummies + momentum + low-vol = 13 factors, not a sectors-skipped minimal version). Cross-sectional OLS regression per date (`numpy.linalg.lstsq`) → factor + specific returns; EWMA (63-day half-life) + scikit-learn `LedoitWolf` shrinkage + Newey-West → factor covariance F; EWMA specific variance D; `RiskModel.sigma()` assembles Σ = B·F·Bᵀ + D. 17 tests. Real run: 985 securities, 179.5s, shrinkage=0.302, Σ symmetric + explicitly confirmed finite — see docs/METRICS.md. Two real bugs found+fixed against the real lake (null sector crash, null-ret NaN corruption) plus one red herring ruled out (benign Apple Accelerate BLAS warnings, documented in `RiskModel.sigma()`'s docstring) — full chain in docs/METRICS.md and docs/STATE.md Failed attempts |
| Optimizer (Block 4) | **BUILT** | `research/portfolio/` (beta.py, inputs.py, constraints.py, solve.py, model.py). Block 4a: `build_optimizer_inputs`/`OptimizerInputs` — aligns alpha (placeholder equal-weight blend of the 3 signals, shrink 0.5x/cap ±3), per-stock beta, ADV, w_prev against the risk model's B/F/D in factor form. Block 4b: `build_constraints` — dollar/beta/sector-neutral, ADV-relative caps, turnover cap, gross cap, style-factor bounds (borrow-availability filter deferred — no free data source exists). Block 4c: `solve_qp` — cvxpy QP, `max αᵀw − λ·wᵀΣw − κ‖w−w_prev‖²`, risk term kept in factor form (never materializes N×N Σ). Block 4d: `build_target_portfolio`/`TargetPortfolio` — chains inputs→solve into one call, mirroring `research/risk/model.py`'s `build_risk_model` role exactly (incl. no CLI — that mirrored module has none either); non-optimal solve `status` (e.g. infeasible) surfaced on the result, not raised. 11 new tests across 5 files. Real numeric checks, not just shape checks: constraint-boundary tests, zero-alpha exact-zero solve, λ-monotonicity, end-to-end dollar-neutral check. **Block 4 fully built.** |
| Backtester (Block 5) | **BUILT** | `research/backtest/` (new dir, sibling to signals/alpha/risk/portfolio/attribution). Block 5a: `trade_cost` — research-side cost model (spread + square-root impact + fees; borrow/financing deferred, same free-data gap as block 4b) since Block 5/C++ hasn't built its own cost model yet. Block 5b: `run_backtest`/`BacktestStep` — the walk-forward day-loop (the sole sanctioned Python loop-over-dates in this codebase), chains `build_target_portfolio` across `universe_monthly` rebalance dates threading `w_prev` forward, applies 5a's cost model, computes each step's holding-period return (`Σ w_i × period_return_i`, a documented buy-and-hold-between-rebalances approximation). Widened `TargetPortfolio` (block 4d) with `w_prev`/`adv` fields to avoid re-deriving already-aligned data. Block 5c: `summarize_backtest`/`BacktestResult` — pure aggregation into an equity curve (`cumprod(1+net_returns)`), cost, and turnover series; empty input gives an empty result (not `None` — mirrors `research/alpha/ic.py`'s `IcSummary` precedent). Widened `BacktestStep` with a `turnover` field. Block 5d: `HELD_OUT_START = dt.date(2023, 7, 24)` (fixed, DESIGN.md's overfitting defense — final 3y held out until design freeze) + `run_backtest`'s `allow_held_out=False` kwarg, hard `ValueError` block by default. 12 tests across the three files. **Block 5 fully built.** Next in DESIGN.md's build-phasing order: item 6, Spark/Databricks/Delta-on-S3 port (infra showcase layer) — not yet scoped |
| C++ engine — broker simulator skeleton | **BUILT** | `engine/` (CMake + Catch2 v3.9.1, C++20): `IBrokerGateway`/`Order`/`OrderEvent` interface, `BrokerSimulator` (submit/cancel/poll_events + inject_ack/inject_fill/inject_reject/inject_cancel_ack test-scripting API), `EventJournal` CSV append-log stub; 6 Catch2 tests. Order gateway, position keeper, risk checks, market data handler, live AlpacaGateway are separate, unscoped. Requires Homebrew LLVM (`-DCMAKE_CXX_COMPILER=/opt/homebrew/opt/llvm/bin/clang++`) — system AppleClang/CommandLineTools libc++ headers are broken on the dev machine. **Known gap**: `inject_fill` does not validate the fill price against the order's `limit_price` — a test can force-fill at any price regardless of the limit; add a check before testing limit-order-specific behavior |
| Spark/Databricks/Delta port (build-phasing item 6, infra showcase) | **6a-6d-iii BUILT, 6d-iv PAUSED (external)** | AWS S3 bucket `mfts-datalake-2026` + IAM role + Unity Catalog external location/catalog/schema (`mfts.research`) provisioned on Databricks Free Edition (6a). `research/data/delta_store.py`'s `DeltaPITStore` — Delta/Unity-Catalog mirror of PITStore, MERGE-based idempotency (no per-file trick, no `part`), live-verified (6b). `research/data/port_to_delta.py` — one-time copy of local lake datasets into Delta preserving full bitemporal batch history; both `yfinance_daily` (6,282,939 rows, 103.3s) and `universe_monthly` (183,464 rows, 19.2s) live-ported (6c, 6d-i) — see docs/METRICS.md. `research/alpha/ic.py`'s `_ic_for_date` extracted from `build_ic_series`'s loop (6d-ii, zero behavior change) so the same per-date unit powers both the local loop and `research/alpha/spark_ic.py`'s Spark version (6d-iii) — a `groupBy(rebalance_date).applyInPandas(...)` job using a real Spark-side broadcast range-join (not a closure — that hit a 128MB gRPC message cap on first attempt, see §12). **6d-iv (the actual benchmark run) is paused**: live execution fails reproducibly (twice, identically) with Databricks' own `ISOLATION_STARTUP_FAILURE.SANDBOX_STARTUP` (`exec format error` inside their managed UDF sandbox container) — a documented platform-side error class, no workaround found, genuinely external to this repo's code (error text says "contact Databricks support"). Separate `.venv-delta/` venv required throughout (`databricks-connect` force-downgrades numpy below this project's `>=2.0` floor and is mutually exclusive with bare `pyspark` in one env) — never installed into the main `.venv`. |
| Ops layer, analytics suite | designed only (DESIGN.md architecture Block 6 — Performance Analysis/attribution, NOT the same "6" as the build-phasing item above; see DESIGN.md's own two numbering systems) | |
| Python test suite | **106 passing, 1 skipped** — `.venv/bin/python -m pytest` (the 1 skip is `test_delta_store.py`, collection-skipped outside `.venv-delta/`) | |
| C++ test suite | **6 passing** — `ctest --test-dir engine/build --output-on-failure` | |

Full Python test suite currently: `106 passed, 1 skipped`. Baseline discipline: run it before and after every change set.

## 4. Repository layout

```
research/               Python research stack (only package with code so far)
  data/
    store.py            PITStore — the bitemporal core. Everything depends on it.
    delta_store.py       DeltaPITStore — Delta/Unity-Catalog mirror of PITStore (block 6b);
                        MERGE-based idempotency, no `part` concept. Requires .venv-delta/, see below
    port_to_delta.py     one-time local-lake -> Delta copy (block 6c), reused for both
                        yfinance_daily and universe_monthly; also requires .venv-delta/
    loaders/
      crsp_daily.py     CRSP/WRDS vendor adapter (scrub → audit → PIT append)
      yfinance_daily.py yfinance vendor adapter (interim while WRDS blocked)
      audit.py          shared AuditReport / audit_daily_bars (both loaders)
      __init__.py       exports CRSPDailyLoader, YFinanceDailyLoader, AuditReport
    __init__.py         exports PITStore only — delta_store.py/port_to_delta.py deliberately
                        NOT exported here, keeps this package importable without databricks-connect
  universe.py           monthly PIT universe snapshots (part 3)
  security_master.py    internal_id ↔ external identifier + PIT resolve (part 4, blocks 1-3)
  signals/              Phase 2: momentum.py/reversal.py/low_vol.py + SIGNAL_REGISTRY (__init__.py)
  alpha/                Phase 2: ic.py — forward returns, IC (Spearman), IC time series + summary
                        (`_ic_for_date` extracted block 6d-ii, shared by the local loop + Spark)
                        spark_ic.py — Spark version of build_ic_series (block 6d-iii), also
                        requires .venv-delta/, also not exported from alpha/__init__.py
  risk/                 Block 3: exposures/regression/factor_covariance/specific_variance/model.py
  portfolio/             Block 4 (Optimizer, DONE): beta.py/inputs.py/constraints.py/solve.py/
                        model.py (no CLI — mirrors research/risk/model.py exactly)
tests/                  pytest; offline-only (fake vendor connections) except
                        universe.py/security_master.py/signals+ic tests, which use real tmp_path stores.
                        test_delta_store.py/test_port_to_delta.py: gated on DATABRICKS_TOKEN
                        (or import-skipped entirely outside .venv-delta/, see below)
docs/
  DESIGN.md             CANONICAL architecture. Block-by-block, decisions locked by owner.
  STATE.md              Live session ledger: Now/Next/Constraints/Decisions/Done/Open items.
  METRICS.md            Measured performance numbers ONLY (command + date + hardware).
  SYSTEM_MAP.md         Living per-file/per-function diagram. Update in the same
                        session as any file/function change (owner requirement).
  guardrails/           Mandatory process checklists (PLAN/CODE/DEBUG/VERIFY/...).
                        CLAUDE.md routes to them on trigger events. Follow literally.
engine/                 C++ (CMake + Catch2 v3.9.1, C++20) — Block 5 hot path, started 2026-07-16
  include/broker/       IBrokerGateway.hpp (interface), OrderEvent.hpp (event/type shared by live+sim)
  src/broker/           BrokerSimulator.hpp/.cpp — mock broker, test-scriptable via inject_* methods
  src/journal/          EventJournal.hpp/.cpp — append-only CSV event log (skeleton; binary framing later)
  tests/                test_broker_simulator.cpp (6 Catch2 scenarios) + CMakeLists.txt (FetchContent)
  CMakeLists.txt        root build file; build/ is gitignored
common/ infra/          NOT YET CREATED — reserved by DESIGN.md repo-layout section
pyproject.toml          deps: polars>=1.42, wrds>=3.2, yfinance>=1.5, numpy>=2.0,
                        scikit-learn>=1.5, cvxpy>=1.5, pyarrow>=19 (block 6c, Polars->pandas
                        bridge); pytest config. `delta` extra: databricks-connect==16.1.*
                        (install into .venv-delta/ ONLY — see §10)
graphify-out/           generated code knowledge graph (query with `graphify query "..."`)
lake/                   default PITStore root. Datasets: yfinance_daily (4.82M rows asof-view,
                        6.28M raw batch history, 2011–2026 YTD × top-1500), universe_monthly
                        (185 snapshots), security_master (6,141 ticker-identity segments,
                        block 2 output). Mirrored (yfinance_daily + universe_monthly only) into
                        Delta at mfts.research.* on Databricks (block 6c/6d-i), backed by S3
                        bucket mfts-datalake-2026 (block 6a) — see status table above
```

Planned-but-absent directories (`research/attribution/`, `common/`, `infra/`, …) are named in DESIGN.md's repo-layout section; do not create them before their block's build phase.

## 5. The core abstraction — bitemporal PIT store

The entire research stack is built around one invariant: **look-ahead bias is prevented by construction, not by caller discipline.** This is DESIGN.md's stated #1 killer of fake backtests, and it is enforced structurally:

Every row in the lake has two time axes:
- `effective_date` — when the fact was true in the market (trade date, fiscal period end). Supplied by the loader.
- `knowledge_ts` — when *we* learned it (download time). **Stamped by the store; a caller supplying it is a ValueError.** Loaders physically cannot forge knowledge time.

Interface (`research/data/store.py`, ~100 lines, read it):

```python
store.append(dataset, df, knowledge_ts, part=None)  # write one load batch
store.asof(dataset, T, keys)   # LazyFrame: the world as known at time T
store.scan(dataset)            # raw lazy scan, no PIT filter — debugging only
```

- `append` validates (`effective_date` required as `pl.Date`; stamp columns forbidden), stamps `knowledge_ts` + `load_ts`, writes one parquet file named `k=<knowledge_ts>[_part=<part>].parquet`. **Idempotency by filename**: re-running the same load overwrites its own file — no dedup logic exists anywhere, none is needed. `part` (e.g. year) splits one logical load into several files under one knowledge_ts; re-running one part overwrites only that part.
- `asof` = filter `knowledge_ts <= T`, sort by `knowledge_ts`, `group_by(keys + effective_date).last()` — latest *known* revision of each row wins. Vendor restatements and yfinance's retroactive back-adjustment are both handled by this one mechanism: each new pull is a new batch under a new knowledge_ts; `asof` serves each backtest date the vintage it could actually have known.
- **`asof` is the only legitimate research read path.** Any future code reading the lake via `scan()` or raw `scan_parquet` in research logic is a design violation.

Why parquet files per batch instead of a database: append-only immutable batches make idempotency, PIT vintages, and audit trivially correct; Polars lazy scans give predicate pushdown (knowledge_ts is constant per file → whole files pruned from footer stats alone); and the layout ports directly to Delta-on-S3 in the infra phase.

## 6. The loader contract (DESIGN.md Block 1d)

Every data vendor — bars today; fundamentals, short interest, sentiment later — passes the same pipeline:

```
pull (vendor API) → transform (vendor names → internal schema)
                  → audit (dups hard-fail; anomalies flagged, never dropped)
                  → PASS: store.append(...)   FAIL: lake/_quarantine/, never enters PIT data
```

Reference implementation: `CRSPDailyLoader` (`research/data/loaders/crsp_daily.py`). Key properties to replicate in every new loader:

- **Connection injected** in the constructor → tests use an offline fake (`FakeConn` in `tests/test_crsp_loader.py`), no network in the suite.
- **Schema verification against the live source** (`verify_schema()`) before any pull — column names are asserted, never assumed.
- Internal schema: `security_id`, `effective_date` (+ data columns). Vendor identifier stays vendor-native (CRSP: permno as int; yfinance: ticker as string) and datasets are **never mixed** — `crsp_daily` and `yfinance_daily` stay parallel. `security_master.resolve_securities()` (part 4, blocks 1-3) can now map ticker→internal_id point-in-time, but cross-vendor reconciliation still waits on block 4 (CRSP permno/CUSIP, blocked on WRDS).
- Audit failures **quarantine the batch** (`lake/_quarantine/`), report, and continue; anomalous *rows* (nulls, |ret| > 200%) are counted and kept, never silently dropped.
- CLI entry (`python -m research.data.loaders.crsp_daily --start 2011`) prints per-year audit reports + rows/s for METRICS.md.

Adding a vendor = implement this contract, nothing else. PIT correctness, idempotency, and revision handling are inherited from the store.

## 7. Data flow end-to-end (current + near-term)

```
WRDS/CRSP ──raw_sql──► CRSPDailyLoader ──append(part=year)──► lake/crsp_daily/
yfinance  ──(2b)─────► YFinanceLoader  ──append(part=year)──► lake/yfinance_daily/
NASDAQ symbol files ──► (2b: listed-universe filter)                │
                                                                    ▼
                        research reads: store.asof(dataset, sim_date, keys)
                                                                    │
                              universe builder (part 3) ──► signals ──► backtester
```

Backtest access pattern (important): **panel pulls, not point lookups.** One `asof` per rebalance date returning the full cross-section; per-stock-per-day queries are malpractice against columnar storage. Measured baseline: full-lake `asof` ≈ 1.06 s over 3.9M rows (see §11).

## 8. Coding conventions

Observed throughout; follow them:

- **Polars for tables, NumPy for matrices** (DESIGN 1c). All transforms are column expressions; **no Python loops over stocks or dates** — the backtester's day loop will be the sole sanctioned exception.
- **Lazy by default**: store returns `LazyFrame`s; callers compose and `.collect()` once.
- **Timestamps are naive UTC** everywhere: `dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)` — matches the store's stamp idiom. Never compare naive and aware datetimes.
- **Explicit None checks** (`if part is not None`), never truthiness on values that can be 0/""/False.
- Docstrings explain *why* and semantics (read `store.py`'s module docstring — that's house style); comments state constraints code can't show, nothing else.
- Module constants for vendor specifics (`SRC_COLUMNS`, `COMMON_STOCK_WHERE`) with provenance comments.
- Dataclasses for structured results (`AuditReport` with `ok` property).
- Tests: plain pytest, `tmp_path` store fixture, small canned frames, one behavior per test, offline always.
- **Process conventions are binding** (see §9). CLAUDE.md + docs/guardrails/ are literal procedure, not advice; they compensate for known agent failure modes.

## 9. Development process (as important as the code)

The owner runs a strict protocol — violating it damages trust regardless of code quality:

1. **Explain-before-build.** Every "part" (small unit of a system) is explained to Ethan in nitty-gritty detail — each block of code and what it does — *before* implementation. He approves, then code happens. This is a learning project; skipping the explanation defeats its purpose. (Verbatim constraints in docs/STATE.md `## Constraints`.)
2. **docs/STATE.md is the ledger.** Update Now/Next/Done (with evidence lines) as work progresses; append user constraints verbatim the turn they're stated; record decisions with rationale.
3. **docs/METRICS.md takes measured numbers only** — command + date + hardware, baselines before optimizations. No estimates ever.
4. **docs/SYSTEM_MAP.md updated in the same session** as any file/function change.
5. **Guardrails kit** (docs/guardrails/): event-triggered checklists (PLAN before multi-file work, CODE before edits, DEBUG on failures, VERIFY before claiming done). CLAUDE.md's routing table says when; follow it literally, cite checklist IDs.
6. **graphify**: run `graphify query "<question>"` before raw file exploration; `graphify update .` after code changes (repo hooks enforce this).
7. Verification vocabulary: claims of done/passing require fresh command output in-turn; otherwise `EDITED-UNVERIFIED` / `UNVERIFIED — to confirm, run: <cmd>`.

## 10. Dependencies and rationale

| Dep | Version | Why |
|---|---|---|
| polars | ≥1.42 (1.42.1 installed) | Columnar + lazy + parallel; pushdown makes the PIT store fast with zero index infrastructure; LazyFrame plans mirror Spark plans → cheap port in the infra phase (DESIGN 1c "engine-agnostic") |
| wrds | ≥3.2 (3.5.0 installed) | Official WRDS Postgres client for CRSP. Pulls pandas → converted to Polars once at the boundary |
| pytest | ≥9 (9.1.1) | Test runner. `testpaths = ["tests"]` |
| yfinance | ≥1.5 (1.5.1 installed) | Interim free bars vendor while WRDS is season-blocked |
| numpy | ≥2.0 (2.2.6 installed) | Block 3's matrix algebra (DESIGN 1c: "Polars for tables, NumPy for matrices") — was already present transitively via polars/pandas, now declared directly for its first direct use |
| scikit-learn | ≥1.5 (1.7.2 installed) | `LedoitWolf` shrinkage for the factor covariance matrix — correctness risk of hand-rolling the 2004 paper's optimal-shrinkage formula judged higher than the cost of one standard dependency (2026-07-17 decision) |
| cvxpy | ≥1.5 (1.7.5 installed) | Block 4's QP modeling layer (bundles OSQP/Clarabel/SCS solvers) — chosen over hand-built OSQP matrices for constraint-iteration ergonomics; solve is once-daily so latency is non-critical (2026-07-20 decision) |
| pyarrow | ≥19 (25.0.0 installed) | Block 6c: Polars' own parquet I/O is native Rust and doesn't need it, but `.to_pandas()` (the bridge from a local Polars frame to a Spark DataFrame) does. Confirmed no numpy/pandas conflict before installing (2026-07-25 decision) |
| databricks-connect | ==16.1.* (16.1.7 installed) | Block 6b: Spark Connect client for Databricks Free Edition serverless. **Installed into a SEPARATE `.venv-delta/`, never the main `.venv`** — force-downgrades numpy to <2.0 (violates this project's own `numpy>=2.0` floor) and is mutually exclusive with a bare `pyspark` install in the same environment (Databricks' own docs: installing both breaks Spark-session init). Same split-toolchain pattern as the C++/Homebrew-LLVM requirement below (2026-07-25 decision) |

Python 3.10 venv at `.venv/`; test command `.venv/bin/python -m pytest`. No uv, no lockfile (known gap, §12). Separate `.venv-delta/` (Python 3.10, `databricks-connect` + `polars`) for all block 6 Databricks/Delta/Spark work — see above. kdb+ (live ticks) still designed, not installed.

## 11. Performance model

Measured (docs/METRICS.md, Apple M4, 16 GB; synthetic 1,000 names × 15y = 3.9M rows):

- parquet+zstd compression **8.1×** (105.7 MB → 13.0 MB on disk)
- append **46.7M rows/s**; full-lake scan **106.5M rows/s**
- full-lake `asof` **1.06 s** — recorded as *the* baseline for a future optimization entry
- 1 security × 1 year `asof`: 14.6 ms

Real-lake confirmation (2026-07-14, `yfinance_daily`, 4.82M rows, 17 year-partitioned files): a single ticker/single-date point lookup runs **~10-13 ms steady-state**, a full 3-column scan+collect of the same dataset runs **1,698 ms** — ~130-150× slower. The gap comes from two stacked pushdowns: year-partitioned file layout (only 1 of 17 files can contain a given date) plus Parquet row-group stats + column projection within that file. Not O(1) — still bounded by O(files) footer checks + O(rows in the surviving partition), not O(total lake rows) and not a hash lookup — but sublinear enough that "brute force + pushdown" continues to hold on real, not just synthetic, data.

Design consequences: at this scale, brute force + pushdown wins; no premature indexing. The agreed escalation ladder if real-data metrics degrade (in order, all behind `asof()`'s unchanged signature): sort-on-write within batch files → tighter row-group pruning; hive-partition by effective-year; materialized latest-revision snapshots; Delta data-skipping/Z-order once on S3. **Do not implement any rung without a measured trigger recorded in METRICS.md.**

## 12. Known limitations, technical debt, inconsistencies

Ordered by severity. None are hidden in the code — all are stated here or in STATE.md.

1. **FIXED 2026-07-13 (commit a5aca9a)** — `.gitignore` unanchored `data/` had hidden `research/data/` from git; Ethan's commit 1ce8420 silently omitted store.py + crsp_daily.py. Now `/data/` + `/lake/` anchored, source tracked.
2. **METRICS.md cites `bench_store.py` — the script is not in the repo.** Numbers are therefore not reproducible from the current tree. Recreate the benchmark script and commit it alongside the numbers.
3. **CIZ column names unverified.** `SRC_COLUMNS` / `COMMON_STOCK_WHERE` in `crsp_daily.py` come from CRSP documentation, not a live connection (WRDS blocked until fall). `verify_schema()` gates every pull, so failure mode is loud, but expect possible renames on first real run.
4. **FIXED 2026-07-13** — loader-test year time bomb: both loader test files now use `YEAR = dt.date.today().year`.
5. **yfinance backfill is survivorship-biased** and has no delisting returns — documented interim state, replaced wholesale by CRSP in fall. No `market_cap` column (would embed look-ahead); current shares outstanding live in separate dataset `yfinance_shares_current` (`--shares` flag), mcap filtering deferred to CRSP.
6. **FIXED 2026-07-13** — `AuditReport` + `audit_daily_bars` extracted to `loaders/audit.py`, shared by both loaders.
7. **No lockfile / no CI.** Deps are floor-pinned in pyproject only; suite runs locally only. Acceptable at this stage, worth adding before the codebase grows contributors.
8. **Uncommitted work.** `docs/DESIGN.md`/`docs/STATE.md` carry uncommitted modifications; `research/`, `tests/`, `pyproject.toml`, docs are untracked (partly *because of* item 1). Commit discipline starts after the gitignore fix.
9. **WRDS seasonal access** (Duke): academic year only. Discovered 2026-07-13. CRSP loader is code-complete and idles until ~late Aug 2026.
10. **FIXED 2026-07-15** — `yfinance_daily` volume dtype mismatch (found 2026-07-14). Real cause was narrower than first suspected: only the 2026 gap-fill part (`k=2026-07-14T19-06-00..._part=2026.parquet`) had `volume` as `Int64`; all other on-disk parts were already `Float64`. Loader's `_transform` now casts volume to `Float64` (`research/data/loaders/yfinance_daily.py`); the one bad file was cast in place (lossless, no re-fetch). Regression test `test_transform_pins_volume_dtype_regardless_of_source` added. Full-column `store.asof("yfinance_daily", ...).collect()` now works.
11. **Security master block 2's gap heuristic has no ground truth (expected, documented).** Real run found 2 tickers (MKC, QLYS) with a >90-day trading gap; both are confirmed **vendor fetch failures** (grep of the phase 2 backfill log shows `"possibly delisted; no price data found"` for exactly those ticker/year pairs), not genuine ticker reassignment — same company both sides of the gap. The heuristic can't tell the difference from trading data alone; real disambiguation needs CUSIP from CRSP (block 4). Not a bug — the module docstring states this limitation up front.
12. **Spark Connect has no `sparkContext`/RDD-broadcast API at all** (confirmed 2026-07-27 by inspecting `pyspark.sql.connect.session.SparkSession` directly, not assumed) — architectural, not a missing permission: Spark Connect is a thin client-server protocol with no driver-JVM co-location. `research/alpha/spark_ic.py`'s first design (closing an `applyInPandas` function over the full driver-collected bars/universe frames) hit a **128MB gRPC message-size cap** as a direct consequence — the cloudpickled closure came out to 462MB, since `applyInPandas` ships its function as one unchunked blob (unlike `spark.createDataFrame`, which streams/batches large local data fine — proven at 6.28M rows in block 6c). Fixed with a real Spark-side `F.broadcast` range-join instead (see docs/STATE.md block 6d-iii). Anyone porting more research code to Spark should assume the same ceiling applies to any UDF closure, not just this one.
13. **Databricks Free Edition serverless hits `ISOLATION_STARTUP_FAILURE.SANDBOX_STARTUP` on every `applyInPandas` attempt so far** (`exec format error` inside Databricks' own managed UDF-isolation container) — reproduced identically twice (2026-07-28, hours apart, different container IDs each time). Community reports describe this error class as generally intermittent, but no documented workaround was found, and it's a container-*startup* failure (fails before any of our code or data runs), so a smaller-scale attempt wouldn't route around it either. Genuinely external — the error text itself says "Please contact Databricks support." **Block 6d-iv PAUSED** as of 2026-07-28; 6c's live-verified data port (6.28M + 183K rows) stands as the block's resume story regardless of whether this ever resolves.
14. **`pyproject.toml` has no `[tool.setuptools.packages.find]` config.** A fresh `pip install -e .` in a new environment now fails with a flat-layout multi-package discovery error (`lake/`, `engine/`, `research/` all found as top-level packages) — surfaced 2026-07-25 when a `setuptools` upgrade (58.1.0→83.0.0, pulled in transiently while installing `databricks-connect`, since reverted in the main `.venv`) enforced a newer discovery guard the original install predates. The existing `.venv`'s editable install still works; only a fresh one elsewhere would hit this. Not fixed — low priority until the project needs CI or a second contributor (see item 7).

## 13. Non-obvious implementation details & pitfalls

- **Polars raises `ComputeError`, not `FileNotFoundError`, when a dataset directory doesn't exist** (`scan_parquet` on an empty glob, at `.collect()` time). Already bit us once; tests assert directory absence instead of exception type.
- **`knowledge_ts` is constant per batch file** (single `pl.lit`). This is why file-level pruning works (min=max in footer stats) and why `asof`'s sort is a cheap merge of pre-sorted runs, not a shuffle. Don't break this property by batching multiple knowledge_ts values into one file.
- **`asof` output order is unspecified.** Its internal sort serves revision-dedup only. Consumers must sort explicitly if they need order.
- **`part` values are path components** — `append` validates them (alphanumeric/`-`/`_` only) to block traversal. Keep that check if refactoring.
- **CRSP conventions**: `dlyret` (CIZ) already includes dividends *and* the delisting return on the final day — do not add a delisting merge. `shrout` is in **thousands** (market_cap multiplies by 1000). Legacy SIZ tables (`crsp.dsf`) use negative prices for bid/ask midpoints — irrelevant unless someone switches off CIZ.
- **pandas exists only at the WRDS boundary** (`raw_sql` returns pandas; `pl.from_pandas` immediately). Don't let it leak further.
- **Sandbox/hook quirk**: repo hooks require `graphify query` before raw greps/reads of source; batch tool calls accordingly or they get rejected.

## 14. Testing strategy

- **Offline always.** Vendor connections are constructor-injected; tests pass fakes returning canned pandas frames. No network, no credentials, no live-data flakiness.
- **PIT correctness is tested as behavior**, not implementation: `test_asof_point_in_time` writes a value + a revision under different knowledge_ts and asserts three vintages (before/mid/after). Any store refactor must keep that test green untouched.
- Idempotency, schema rejection, quarantine-not-store, flag-don't-drop each have a dedicated test.
- Fresh `tmp_path` store per test — no shared state.
- Run: `.venv/bin/python -m pytest` (104 passing). Narrow first during debugging (`pytest tests/test_x.py::test_y -x`), full suite as the gate. `test_universe.py`/`test_security_master.py` don't fake a vendor (nothing to fake) but still use a fresh `tmp_path` `PITStore` — no network either way.
- Gap: no property-based tests, no benchmarks in CI; live-pull integration is manual by design (credentials).

## 15. How to add things

**A new data vendor** (the common case):
1. Explain the design to the owner first (§9.1) — blocks, functions, failure handling. Wait for approval.
2. Copy the structure of `crsp_daily.py`: injected connection, `SRC_COLUMNS` mapping, `verify_schema()`, `load_<unit>()`, `_transform`, `_audit` (use shared audit module once extracted), `_quarantine`, CLI `main()`.
3. New dataset name, vendor-native `security_id`; never merge into another vendor's dataset.
4. Offline tests with a fake connection: happy path into store, idempotent re-run, quarantine path, vendor-specific quirks.
5. Update docs/SYSTEM_MAP.md + STATE.md same session; record ingest metrics in METRICS.md after the real run.

**A downstream research component** (universe, signals, risk): read inputs exclusively via `store.asof(...)` with an explicit simulation timestamp; walk-forward semantics (each simulated day sees only what was knowable) come free if you never touch `scan()`.

## 16. Roadmap & recommended next tasks

Build phasing (DESIGN.md, owner-approved order): data layer → 2–3 classic signals + IC → risk model → optimizer → backtester → Spark/Databricks port → C++ engine → analytics suite → alt-data/kdb+.

Immediate queue, in order:

1. ~~Fix `.gitignore`~~ **DONE 2026-07-13** (commit a5aca9a).
2. ~~Build part 2b~~ **DONE 2026-07-13**; ~~full backfill~~ **DONE 2026-07-14** — two-phase run, `lake/yfinance_daily` = 4.82M rows, 2011–2026 YTD × top-1500, METRICS.md recorded.
3. ~~Part 3: universe builder~~ **DONE 2026-07-14** — `research/universe.py`, real run wrote 185 monthly PIT snapshots to `lake/universe_monthly`, METRICS.md recorded.
4. **Part 4: security master, blocks 1-3 of 4** **DONE 2026-07-14** — `research/security_master.py`: block 1 schema + PITStore fit; block 2 `build_ticker_segments` (trading-gap heuristic) extracted 6,141 identity segments, `lake/security_master` populated; block 3 `resolve_securities`/`resolve_security` PIT lookup. **Next**: block 4 (CRSP permno/CUSIP hookup, blocked on WRDS) — the only remaining piece of part 4.
5. ~~Fix the `volume` dtype bug~~ **DONE 2026-07-15** — real cause was the single 2026 gap-fill parquet part (`k=2026-07-14T19-06-00..._part=2026.parquet`) written as Int64; loader's `_transform` now casts volume to Float64, the one bad file was cast in place, regression test added. `.venv/bin/python -m pytest -q` -> 46 passed.
6. ~~Broker simulator skeleton (C++ engine, out-of-phasing-order design/scope pass)~~ **DONE 2026-07-16** — `engine/` built and tested (see status table above). This jumped ahead of DESIGN.md's build-phasing order (C++ engine is step 7, after signals/risk/optimizer/backtester) as an explicit design/scope exercise, not a phasing change — remaining Block 5 pieces still wait their turn.
7. ~~Phase 2: signals + IC measurement~~ **DONE 2026-07-16/17** — `research/signals/` (momentum/reversal/low_vol + registry) + `research/alpha/ic.py`, real run over the full lake recorded in docs/METRICS.md (§ Signal/alpha pipeline).
8. ~~Block 3: Risk Model~~ **DONE 2026-07-19** — sector/industry loader (2026-07-17) + `research/risk/` (exposures, cross-sectional regression, EWMA+Ledoit-Wolf+Newey-West factor covariance, specific variance, Σ assembly). Real run: 985 securities, 13 factors, 179.5s (docs/METRICS.md). Two real bugs found+fixed against the real lake, one red herring (benign Apple Accelerate BLAS warnings) ruled out — full chain in docs/METRICS.md.
9. ~~Block 4: Optimizer~~ **DONE 2026-07-20/21/22/23** — `research/portfolio/` (beta.py, inputs.py, constraints.py, solve.py, model.py); real numeric tests (constraint-boundary, zero-alpha exact solve, λ-monotonicity, end-to-end dollar-neutral check). Block 4d (`build_target_portfolio`) chains inputs→solve, mirrors `research/risk/model.py`'s `build_risk_model` exactly, no CLI.
10. ~~Block 5: Backtester~~ **DONE 2026-07-23/24** — `research/backtest/costs.py` (`trade_cost`: spread + sqrt impact + fees, borrow deferred), `research/backtest/simulate.py` (`run_backtest`/`BacktestStep`: walk-forward day-loop, `TargetPortfolio` widened with `w_prev`/`adv`, `HELD_OUT_START` guard), `research/backtest/result.py` (`summarize_backtest`/`BacktestResult`: equity curve/cost/turnover series). `.venv/bin/python -m pytest -q` -> "104 passed".
11. **Build-phasing item 6: Spark/Databricks/Delta-on-S3 port** — scoped 2026-07-24/25 into 6a-6e (see docs/STATE.md for full detail). ~~6a: AWS + Databricks provisioning~~ **DONE 2026-07-25** — S3 bucket, IAM role, Unity Catalog external location/catalog/schema (`mfts.research`). ~~6b: Delta-backed store~~ **DONE 2026-07-25**, live-verified — `research/data/delta_store.py`. ~~6c: local lake -> Delta port~~ **DONE 2026-07-26** — `research/data/port_to_delta.py`, `yfinance_daily` ported (6,282,939 rows, 103.3s). ~~6d-i: universe_monthly port~~ **DONE 2026-07-27** (183,464 rows, 19.2s). ~~6d-ii: `_ic_for_date` extraction~~ **DONE 2026-07-27**, zero behavior change. ~~6d-iii: Spark IC benchmark harness~~ **DONE 2026-07-27** — `research/alpha/spark_ic.py`, redesigned mid-build from a closure to a Spark-side broadcast range-join after hitting a real 128MB gRPC message-size cap (§12 item 12). **6d-iv (the actual benchmark run) PAUSED 2026-07-28** — Databricks-side `ISOLATION_STARTUP_FAILURE.SANDBOX_STARTUP`, reproduced identically twice, no workaround found, genuinely external to this repo (§12 item 13). **6e (benchmark comparison vs. 824.2s local baseline) waits on 6d-iv** — may never resolve if this is a persistent Free Edition limitation; 6c's live data port already stands as Block 6's resume story independent of this.
12. **Fall (WRDS returns)**: run `crsp_daily` live — `verify_schema()` first, full backfill, METRICS entry, then reconcile vs yfinance (DESIGN 1a cross-vendor checks) via security master block 4.

Item 4 in §12 (test year bomb) — **FIXED**, see status table above; both loader test files use `dt.date.today().year`.

---

*If something here can't be verified against the tree, trust the tree and update this file. Keep it current the way STATE.md is kept current — a stale handoff is worse than none.*
