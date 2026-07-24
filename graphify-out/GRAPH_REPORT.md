# Graph Report - multifactor-trading-system  (2026-07-23)

## Corpus Check
- 64 files · ~41,981 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 600 nodes · 1179 edges · 20 communities (19 shown, 1 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 16 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fc05ed30`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Multifactor Trading System — Design
- STATE
- test_store.py
- model.py
- multifactor-trading-system
- test_crsp_loader.py
- METRICS
- AuditReport
- YFinanceDailyLoader
- HANDOFF — Multifactor Equity Trading System
- .load_year
- Files & functions
- test_security_master.py
- test_signals.py
- test_ic.py
- build_exposure_matrix
- build_optimizer_inputs
- trade_cost

## God Nodes (most connected - your core abstractions)
1. `PITStore` - 66 edges
2. `YFinanceDailyLoader` - 25 edges
3. `BrokerSimulator` - 20 edges
4. `CRSPDailyLoader` - 20 edges
5. `OrderEvent` - 18 edges
6. `Multifactor Trading System — Design` - 18 edges
7. `build_optimizer_inputs()` - 17 edges
8. `build_exposure_matrix()` - 17 edges
9. `FakeClient` - 17 edges
10. `HANDOFF — Multifactor Equity Trading System` - 17 edges

## Surprising Connections (you probably didn't know these)
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_beta.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_exposures.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_model.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_portfolio_inputs.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_risk_model.py → research/data/store.py

## Import Cycles
- None detected.

## Communities (20 total, 1 thin omitted)

### Community 0 - "Multifactor Trading System — Design"
Cohesion: 0.10
Nodes (19): Analytics suite (per-factor scoreboard), Backtester (validates Blocks 1–4 before any live loop), Block 1: Data + Signals, Block 1 mini-systems (per-vendor pipeline; every data source, especially each alternative dataset, passes through all of these), Block 2: Alpha Forecast, Block 3: Risk Model (parallel to alpha), Block 4: Portfolio Construction (Optimizer), Block 5: Implementation + Trading System (C++ hot path) (+11 more)

### Community 1 - "STATE"
Cohesion: 0.17
Nodes (11): Constraints, Decisions, Done, Facts, Failed attempts, Goal, Next, Now (+3 more)

### Community 2 - "test_store.py"
Cohesion: 0.39
Nodes (8): bars(), DataFrame, store(), test_append_idempotent(), test_append_parts_coexist_and_overwrite(), test_append_rejects_bad_schema(), test_asof_point_in_time(), test_round_trip()

### Community 3 - "model.py"
Cohesion: 0.05
Nodes (62): build_exposure_matrix(), DataFrame, date, LazyFrame, Factor exposure matrix B (Block 3 risk model).  Per rebalance date: one row per, Exposure matrix B for one rebalance date.      ``sectors`` is the already-asof'd, _zscore(), build_factor_covariance() (+54 more)

### Community 6 - "test_crsp_loader.py"
Cohesion: 0.09
Nodes (30): Path, CRSPDailyLoader, main(), DataFrame, datetime, scrub -> audit -> PIT store, per DESIGN.md Block 1d contract.      ``conn`` is a, Assert expected CIZ columns exist on the live table., Pull one calendar year, audit it, append or quarantine it. (+22 more)

### Community 7 - "METRICS"
Cohesion: 0.17
Nodes (11): Data layer — PITStore (point-in-time parquet store), Data loaders — yfinance daily bars (phase 1: universe scan), Data loaders — yfinance daily bars (phase 2: 15.5-year backfill, top-1500), Data loaders — yfinance sector/industry snapshot, METRICS, Pending sections (filled as systems are built), PIT store — real-lake point lookup vs full scan, Risk model — Block 3 (Barra-style factor risk, full scope with sectors) (+3 more)

### Community 8 - "AuditReport"
Cohesion: 0.05
Nodes (57): deque, string, IBrokerGateway, cancel_order, poll_events, submit_order, Order, is_buy (+49 more)

### Community 9 - "YFinanceDailyLoader"
Cohesion: 0.06
Nodes (49): audit_daily_bars(), AuditReport, DataFrame, Shared audit for daily-bars loaders (DESIGN.md Block 1d).  Every vendor chunk pa, Audit one yearly chunk of daily bars keyed (security_id, effective_date).      H, CRSP daily-bars loader (WRDS, CRSP 2.0 / "CIZ" format).  Pulls daily bars for al, fetch_listed_tickers(), main() (+41 more)

### Community 10 - "HANDOFF — Multifactor Equity Trading System"
Cohesion: 0.11
Nodes (17): 10. Dependencies and rationale, 11. Performance model, 12. Known limitations, technical debt, inconsistencies, 13. Non-obvious implementation details & pitfalls, 14. Testing strategy, 15. How to add things, 16. Roadmap & recommended next tasks, 1. Project purpose (+9 more)

### Community 11 - ".load_year"
Cohesion: 0.16
Nodes (26): build_snapshot(), build_universe(), _empty_snapshot(), main(), month_end_trading_days(), DataFrame, date, datetime (+18 more)

### Community 12 - "Files & functions"
Cohesion: 0.09
Nodes (22): Barrel files, C++ engine (Block 5 — broker simulator skeleton, started 2026-07-16), Config, Data layer (Phase 1 — current), engine/ — **built (broker simulator skeleton, 6 Catch2 tests)**, Files & functions, Not yet started (DESIGN.md blocks), research/alpha/ic.py — **built (Phase 2, 8 tests)** (+14 more)

### Community 13 - "test_security_master.py"
Cohesion: 0.14
Nodes (32): build_ticker_segments(), empty_master(), main(), DataFrame, date, datetime, LazyFrame, Security master (part 4, block 1): schema + PITStore fit.  Problem this exists t (+24 more)

### Community 15 - "test_signals.py"
Cohesion: 0.10
Nodes (33): Signal registry — every signal follows the same contract.  Each ``compute_*`` fu, compute_low_vol(), _empty_signal(), DataFrame, date, LazyFrame, Low-volatility signal (Phase 2 signals + IC measurement).  Trailing ``window_day, Trailing return-volatility per security, as of ``rebuild_date``.      ``bars`` m (+25 more)

### Community 16 - "test_ic.py"
Cohesion: 0.17
Nodes (28): build_ic_series(), compute_forward_returns(), compute_ic(), _empty_forward_returns(), ic_summary(), IcSummary, main(), DataFrame (+20 more)

### Community 17 - "build_exposure_matrix"
Cohesion: 0.20
Nodes (16): compute_market_beta(), _empty_beta(), DataFrame, date, LazyFrame, Per-stock market beta (Block 4b input): rolling single-factor beta.  Needed for, Trailing single-factor beta per security, as of ``rebuild_date``.      ``securit, DataFrame (+8 more)

### Community 18 - "build_optimizer_inputs"
Cohesion: 0.07
Nodes (55): Problem, build_constraints(), Constraint, Variable, Block 4b: optimizer constraints (DESIGN.md Block 4).  Builds the cvxpy constrain, Constraint list for ``w`` (shape ``(N,)``, aligned to ``inputs.security_ids``)., build_optimizer_inputs(), OptimizerInputs (+47 more)

### Community 20 - "trade_cost"
Cohesion: 0.11
Nodes (29): ndarray, Block 5a: research-side trading cost model (DESIGN.md Block 5's cost components,, Per-security $ trading cost for one rebalance's ``delta_w = w - w_prev``.      `, trade_cost(), BacktestStep, _empty_holding_returns(), _holding_period_return(), DataFrame (+21 more)

## Knowledge Gaps
- **95 isolated node(s):** `symbol`, `qty`, `limit_price`, `is_buy`, `submit_order` (+90 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PITStore` connect `test_crsp_loader.py` to `test_store.py`, `model.py`, `YFinanceDailyLoader`, `.load_year`, `test_security_master.py`, `test_signals.py`, `test_ic.py`, `build_exposure_matrix`, `build_optimizer_inputs`, `trade_cost`?**
  _High betweenness centrality (0.442) - this node is a cross-community bridge._
- **Why does `build_risk_model()` connect `model.py` to `build_optimizer_inputs`, `test_crsp_loader.py`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Why does `YFinanceDailyLoader` connect `YFinanceDailyLoader` to `test_crsp_loader.py`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `PITStore` (e.g. with `CRSPDailyLoader` and `YFinanceClient`) actually correct?**
  _`PITStore` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `YFinanceDailyLoader` (e.g. with `AuditReport` and `PITStore`) actually correct?**
  _`YFinanceDailyLoader` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `CRSPDailyLoader` (e.g. with `AuditReport` and `PITStore`) actually correct?**
  _`CRSPDailyLoader` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `symbol`, `qty`, `limit_price` to the rest of the system?**
  _178 weakly-connected nodes found - possible documentation gaps or missing edges._