# Graph Report - multifactor-trading-system  (2026-08-02)

## Corpus Check
- 86 files · ~56,261 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 772 nodes · 1457 edges · 33 communities (32 shown, 1 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 22 edges (avg confidence: 0.58)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `97abb800`
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
- Quote
- AlpacaMarketDataStream.cpp
- MarketDataHandler.cpp
- Trade

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
- `FakeConn` --uses--> `PITStore`  [INFERRED]
  tests/test_crsp_loader.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_crsp_loader.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_exposures.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_ic.py → research/data/store.py

## Import Cycles
- None detected.

## Communities (33 total, 1 thin omitted)

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
Cohesion: 0.39
Nodes (7): OrderId, OrderState, is_terminal(), OrderGateway::cancel_order(), OrderGateway::pump(), OrderGateway::state(), OrderGateway::submit_order()

### Community 7 - "METRICS"
Cohesion: 0.15
Nodes (12): Data layer — PITStore (point-in-time parquet store), Data loaders — yfinance daily bars (phase 1: universe scan), Data loaders — yfinance daily bars (phase 2: 15.5-year backfill, top-1500), Data loaders — yfinance sector/industry snapshot, Infra — Block 6c: local lake -> Delta/Databricks port, METRICS, Pending sections (filled as systems are built), PIT store — real-lake point lookup vs full scan (+4 more)

### Community 8 - "AuditReport"
Cohesion: 0.24
Nodes (9): MarketDataHandler, latest_quote, latest_trade, on_message, quotes_, trades_, string, load_dotenv() (+1 more)

### Community 9 - "YFinanceDailyLoader"
Cohesion: 0.05
Nodes (54): Path, fetch_listed_tickers(), main(), DataFrame, datetime, _rate_limited_errors(), yfinance daily-bars loader (interim free vendor, part 2b).  Fills the lake while, (sector, industry) — Yahoo's own taxonomy, not literal GICS codes.          Unli (+46 more)

### Community 10 - "HANDOFF — Multifactor Equity Trading System"
Cohesion: 0.11
Nodes (17): 10. Dependencies and rationale, 11. Performance model, 12. Known limitations, technical debt, inconsistencies, 13. Non-obvious implementation details & pitfalls, 14. Testing strategy, 15. How to add things, 16. Roadmap & recommended next tasks, 1. Project purpose (+9 more)

### Community 11 - ".load_year"
Cohesion: 0.16
Nodes (26): build_snapshot(), build_universe(), _empty_snapshot(), main(), month_end_trading_days(), DataFrame, date, datetime (+18 more)

### Community 12 - "Files & functions"
Cohesion: 0.08
Nodes (25): Barrel files, C++ engine (Block 5 — broker simulator skeleton, started 2026-07-16), Config, Data layer (Phase 1 — current), engine/ — **built (broker simulator + order gateway + position keeper + risk checker + market data handler, 38 Catch2 tests)**, Files & functions, Not yet started (DESIGN.md blocks), research/alpha/ic.py — **built (Phase 2, 8 tests)** (+17 more)

### Community 13 - "test_security_master.py"
Cohesion: 0.14
Nodes (32): build_ticker_segments(), empty_master(), main(), DataFrame, date, datetime, LazyFrame, Security master (part 4, block 1): schema + PITStore fit.  Problem this exists t (+24 more)

### Community 15 - "test_signals.py"
Cohesion: 0.09
Nodes (34): Signal registry — every signal follows the same contract.  Each ``compute_*`` fu, compute_low_vol(), _empty_signal(), DataFrame, date, LazyFrame, Low-volatility signal (Phase 2 signals + IC measurement).  Trailing ``window_day, Trailing return-volatility per security, as of ``rebuild_date``.      ``bars`` m (+26 more)

### Community 16 - "test_ic.py"
Cohesion: 0.15
Nodes (31): build_ic_series(), compute_forward_returns(), compute_ic(), _empty_forward_returns(), _ic_for_date(), ic_summary(), IcSummary, main() (+23 more)

### Community 17 - "build_exposure_matrix"
Cohesion: 0.06
Nodes (34): build_ic_series_spark(), main(), DataFrame, datetime, Spark benchmark for the historical alpha run (Block 6d).  Re-executes the SAME p, Same result as build_ic_series (long format: rebalance_date/signal/ic     rows i, DeltaPITStore, DataFrame (+26 more)

### Community 18 - "build_optimizer_inputs"
Cohesion: 0.07
Nodes (55): Problem, build_constraints(), Constraint, Variable, Block 4b: optimizer constraints (DESIGN.md Block 4).  Builds the cvxpy constrain, Constraint list for ``w`` (shape ``(N,)``, aligned to ``inputs.security_ids``)., build_optimizer_inputs(), OptimizerInputs (+47 more)

### Community 19 - "CRSPDailyLoader"
Cohesion: 0.12
Nodes (23): audit_daily_bars(), AuditReport, DataFrame, Shared audit for daily-bars loaders (DESIGN.md Block 1d).  Every vendor chunk pa, Audit one yearly chunk of daily bars keyed (security_id, effective_date).      H, CRSPDailyLoader, main(), DataFrame (+15 more)

### Community 20 - "trade_cost"
Cohesion: 0.09
Nodes (40): ndarray, Block 5a: research-side trading cost model (DESIGN.md Block 5's cost components,, Per-security $ trading cost for one rebalance's ``delta_w = w - w_prev``.      `, trade_cost(), BacktestResult, Block 5c: backtest result/equity-curve summary.  Pure aggregation over BacktestS, Equity curve + cost/turnover series over ``steps``.      Only steps with a ``per, summarize_backtest() (+32 more)

### Community 21 - "compute_market_beta"
Cohesion: 0.20
Nodes (16): compute_market_beta(), _empty_beta(), DataFrame, date, LazyFrame, Per-stock market beta (Block 4b input): rolling single-factor beta.  Needed for, Trailing single-factor beta per security, as of ``rebuild_date``.      ``securit, DataFrame (+8 more)

### Community 22 - "BrokerSimulator"
Cohesion: 0.06
Nodes (52): deque, Order, is_buy, limit_price, qty, symbol, EventType, OrderId (+44 more)

### Community 23 - "IBrokerGateway"
Cohesion: 0.22
Nodes (9): OrderId, OrderState, unordered_map, OrderGateway, cancel_order, pump, state, states_ (+1 more)

### Community 24 - "BrokerSimulator.cpp"
Cohesion: 0.22
Nodes (9): AlpacaMarketDataStream, api_key_, api_secret_, connect, disconnect, symbols_, ws_, string (+1 more)

### Community 25 - "OrderGateway.cpp"
Cohesion: 0.09
Nodes (24): string, unordered_map, Position, avg_price, qty, realized_pnl, PositionKeeper, on_fill (+16 more)

### Community 26 - "EventJournal"
Cohesion: 0.33
Nodes (5): IBrokerGateway, cancel_order, poll_events, submit_order, OrderGateway::OrderGateway()

### Community 27 - "Order"
Cohesion: 0.32
Nodes (3): string, vector, unordered_map

### Community 29 - "Quote"
Cohesion: 0.33
Nodes (6): Quote, ask_price, ask_size, bid_price, bid_size, timestamp

### Community 30 - "AlpacaMarketDataStream.cpp"
Cohesion: 0.40
Nodes (4): AlpacaMarketDataStream::AlpacaMarketDataStream(), AlpacaMarketDataStream::connect(), string, vector

### Community 31 - "MarketDataHandler.cpp"
Cohesion: 0.53
Nodes (5): string, MarketDataHandler::latest_quote(), MarketDataHandler::latest_trade(), MarketDataHandler::on_message(), optional

### Community 32 - "Trade"
Cohesion: 0.40
Nodes (5): string, Trade, price, size, timestamp

## Knowledge Gaps
- **132 isolated node(s):** `symbol`, `qty`, `limit_price`, `is_buy`, `submit_order` (+127 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PITStore` connect `YFinanceDailyLoader` to `test_store.py`, `model.py`, `.load_year`, `test_security_master.py`, `test_signals.py`, `test_ic.py`, `build_exposure_matrix`, `build_optimizer_inputs`, `CRSPDailyLoader`, `trade_cost`, `compute_market_beta`?**
  _High betweenness centrality (0.367) - this node is a cross-community bridge._
- **Why does `build_risk_model()` connect `model.py` to `YFinanceDailyLoader`, `build_optimizer_inputs`?**
  _High betweenness centrality (0.026) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `PITStore` (e.g. with `CRSPDailyLoader` and `YFinanceClient`) actually correct?**
  _`PITStore` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `YFinanceDailyLoader` (e.g. with `AuditReport` and `PITStore`) actually correct?**
  _`YFinanceDailyLoader` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `CRSPDailyLoader` (e.g. with `AuditReport` and `PITStore`) actually correct?**
  _`CRSPDailyLoader` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `symbol`, `qty`, `limit_price` to the rest of the system?**
  _228 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Multifactor Trading System — Design` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._