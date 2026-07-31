# Graph Report - multifactor-trading-system  (2026-07-30)

## Corpus Check
- 77 files · ~53,140 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 711 nodes · 1366 edges · 30 communities (29 shown, 1 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 20 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fa53baaa`
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
- CRSPDailyLoader
- trade_cost
- compute_market_beta
- BrokerSimulator
- IBrokerGateway
- BrokerSimulator.cpp
- OrderGateway.cpp
- EventJournal
- Order

## God Nodes (most connected - your core abstractions)
1. `PITStore` - 75 edges
2. `YFinanceDailyLoader` - 25 edges
3. `BrokerSimulator` - 20 edges
4. `CRSPDailyLoader` - 20 edges
5. `OrderEvent` - 19 edges
6. `Files & functions` - 19 edges
7. `Multifactor Trading System — Design` - 18 edges
8. `run_backtest()` - 17 edges
9. `build_optimizer_inputs()` - 17 edges
10. `build_exposure_matrix()` - 17 edges

## Surprising Connections (you probably didn't know these)
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_beta.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_exposures.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_ic.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_model.py → research/data/store.py
- `FakeDeltaStore` --uses--> `PITStore`  [INFERRED]
  tests/test_port_to_delta.py → research/data/store.py

## Import Cycles
- None detected.

## Communities (30 total, 1 thin omitted)

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
Cohesion: 0.06
Nodes (61): build_exposure_matrix(), DataFrame, date, LazyFrame, Exposure matrix B for one rebalance date.      ``sectors`` is the already-asof'd, _zscore(), build_factor_covariance(), _ewma_scaled_centered() (+53 more)

### Community 6 - "test_crsp_loader.py"
Cohesion: 0.12
Nodes (14): main(), port_dataset(), One-time port of a local PITStore dataset into Delta (Block 6c).  Copies every `, Copy every batch of ``dataset`` from local_store into delta_store.      Returns, bars(), FakeDeltaStore, FakeSpark, FakeSparkColumn (+6 more)

### Community 7 - "METRICS"
Cohesion: 0.15
Nodes (12): Data layer — PITStore (point-in-time parquet store), Data loaders — yfinance daily bars (phase 1: universe scan), Data loaders — yfinance daily bars (phase 2: 15.5-year backfill, top-1500), Data loaders — yfinance sector/industry snapshot, Infra — Block 6c: local lake -> Delta/Databricks port, METRICS, Pending sections (filled as systems are built), PIT store — real-lake point lookup vs full scan (+4 more)

### Community 8 - "AuditReport"
Cohesion: 0.14
Nodes (15): string, EventType, OrderId, string, OrderEvent, id, price, qty (+7 more)

### Community 9 - "YFinanceDailyLoader"
Cohesion: 0.07
Nodes (43): fetch_listed_tickers(), main(), DataFrame, datetime, _rate_limited_errors(), (sector, industry) — Yahoo's own taxonomy, not literal GICS codes.          Unli, scrub -> audit -> PIT store, per DESIGN.md Block 1d contract.      ``client`` ex, Pull one calendar year for all tickers, audit, append or quarantine.          Do (+35 more)

### Community 10 - "HANDOFF — Multifactor Equity Trading System"
Cohesion: 0.11
Nodes (17): 10. Dependencies and rationale, 11. Performance model, 12. Known limitations, technical debt, inconsistencies, 13. Non-obvious implementation details & pitfalls, 14. Testing strategy, 15. How to add things, 16. Roadmap & recommended next tasks, 1. Project purpose (+9 more)

### Community 11 - ".load_year"
Cohesion: 0.16
Nodes (26): build_snapshot(), build_universe(), _empty_snapshot(), main(), month_end_trading_days(), DataFrame, date, datetime (+18 more)

### Community 12 - "Files & functions"
Cohesion: 0.08
Nodes (25): Barrel files, C++ engine (Block 5 — broker simulator skeleton, started 2026-07-16), Config, Data layer (Phase 1 — current), engine/ — **built (broker simulator + order gateway + position keeper, 25 Catch2 tests)**, Files & functions, Not yet started (DESIGN.md blocks), research/alpha/ic.py — **built (Phase 2, 8 tests)** (+17 more)

### Community 13 - "test_security_master.py"
Cohesion: 0.14
Nodes (32): build_ticker_segments(), empty_master(), main(), DataFrame, date, datetime, LazyFrame, Security master (part 4, block 1): schema + PITStore fit.  Problem this exists t (+24 more)

### Community 15 - "test_signals.py"
Cohesion: 0.09
Nodes (35): Factor exposure matrix B (Block 3 risk model).  Per rebalance date: one row per, Signal registry — every signal follows the same contract.  Each ``compute_*`` fu, compute_low_vol(), _empty_signal(), DataFrame, date, LazyFrame, Low-volatility signal (Phase 2 signals + IC measurement).  Trailing ``window_day (+27 more)

### Community 16 - "test_ic.py"
Cohesion: 0.15
Nodes (31): build_ic_series(), compute_forward_returns(), compute_ic(), _empty_forward_returns(), _ic_for_date(), ic_summary(), IcSummary, main() (+23 more)

### Community 17 - "build_exposure_matrix"
Cohesion: 0.10
Nodes (20): build_ic_series_spark(), main(), DataFrame, datetime, Spark benchmark for the historical alpha run (Block 6d).  Re-executes the SAME p, Same result as build_ic_series (long format: rebalance_date/signal/ic     rows i, DeltaPITStore, DataFrame (+12 more)

### Community 18 - "build_optimizer_inputs"
Cohesion: 0.07
Nodes (55): Problem, build_constraints(), Constraint, Variable, Block 4b: optimizer constraints (DESIGN.md Block 4).  Builds the cvxpy constrain, Constraint list for ``w`` (shape ``(N,)``, aligned to ``inputs.security_ids``)., build_optimizer_inputs(), OptimizerInputs (+47 more)

### Community 19 - "CRSPDailyLoader"
Cohesion: 0.08
Nodes (34): Path, audit_daily_bars(), AuditReport, DataFrame, Shared audit for daily-bars loaders (DESIGN.md Block 1d).  Every vendor chunk pa, Audit one yearly chunk of daily bars keyed (security_id, effective_date).      H, CRSPDailyLoader, main() (+26 more)

### Community 20 - "trade_cost"
Cohesion: 0.09
Nodes (40): ndarray, Block 5a: research-side trading cost model (DESIGN.md Block 5's cost components,, Per-security $ trading cost for one rebalance's ``delta_w = w - w_prev``.      `, trade_cost(), BacktestResult, Block 5c: backtest result/equity-curve summary.  Pure aggregation over BacktestS, Equity curve + cost/turnover series over ``steps``.      Only steps with a ``per, summarize_backtest() (+32 more)

### Community 21 - "compute_market_beta"
Cohesion: 0.20
Nodes (16): compute_market_beta(), _empty_beta(), DataFrame, date, LazyFrame, Per-stock market beta (Block 4b input): rolling single-factor beta.  Needed for, Trailing single-factor beta per security, as of ``rebuild_date``.      ``securit, DataFrame (+8 more)

### Community 22 - "BrokerSimulator"
Cohesion: 0.24
Nodes (9): deque, BrokerSimulator, journal_, next_id_, orders_, pending_events_, EventJournal, OrderId (+1 more)

### Community 23 - "IBrokerGateway"
Cohesion: 0.14
Nodes (13): IBrokerGateway, cancel_order, poll_events, submit_order, OrderId, OrderState, unordered_map, OrderGateway (+5 more)

### Community 24 - "BrokerSimulator.cpp"
Cohesion: 0.38
Nodes (11): cancel_order, enqueue, inject_ack, inject_cancel_ack, inject_fill, inject_reject, submit_order, EventType (+3 more)

### Community 25 - "OrderGateway.cpp"
Cohesion: 0.10
Nodes (21): string, unordered_map, Position, avg_price, qty, realized_pnl, PositionKeeper, on_fill (+13 more)

### Community 26 - "EventJournal"
Cohesion: 0.22
Nodes (8): BrokerSimulator::BrokerSimulator(), string, EventJournal, append, EventJournal::EventJournal(), out_, EventJournal, ofstream

### Community 27 - "Order"
Cohesion: 0.20
Nodes (10): Order, is_buy, limit_price, qty, symbol, SimOrderState, order, qty_remaining (+2 more)

## Knowledge Gaps
- **110 isolated node(s):** `symbol`, `qty`, `limit_price`, `is_buy`, `submit_order` (+105 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PITStore` connect `CRSPDailyLoader` to `test_store.py`, `model.py`, `test_crsp_loader.py`, `YFinanceDailyLoader`, `.load_year`, `test_security_master.py`, `test_signals.py`, `test_ic.py`, `build_optimizer_inputs`, `trade_cost`, `compute_market_beta`?**
  _High betweenness centrality (0.433) - this node is a cross-community bridge._
- **Why does `DeltaPITStore` connect `build_exposure_matrix` to `test_crsp_loader.py`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Why does `build_risk_model()` connect `model.py` to `build_optimizer_inputs`, `CRSPDailyLoader`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `PITStore` (e.g. with `CRSPDailyLoader` and `YFinanceClient`) actually correct?**
  _`PITStore` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `YFinanceDailyLoader` (e.g. with `AuditReport` and `PITStore`) actually correct?**
  _`YFinanceDailyLoader` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `CRSPDailyLoader` (e.g. with `AuditReport` and `PITStore`) actually correct?**
  _`CRSPDailyLoader` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `symbol`, `qty`, `limit_price` to the rest of the system?**
  _206 weakly-connected nodes found - possible documentation gaps or missing edges._