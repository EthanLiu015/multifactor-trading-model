# Graph Report - multifactor-trading-system  (2026-08-05)

## Corpus Check
- 101 files · ~64,200 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 882 nodes · 1672 edges · 38 communities (37 shown, 1 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 25 edges (avg confidence: 0.61)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `678f2d28`
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
- wait_for_event
- ExecutionScheduler
- FakeSparkDataFrame
- test_store.py
- MarketDataHandler.cpp

## God Nodes (most connected - your core abstractions)
1. `PITStore` - 79 edges
2. `AlpacaGateway` - 27 edges
3. `YFinanceDailyLoader` - 25 edges
4. `OrderEvent` - 23 edges
5. `MarketDataHandler` - 22 edges
6. `BrokerSimulator` - 20 edges
7. `CRSPDailyLoader` - 20 edges
8. `Files & functions` - 20 edges
9. `PositionKeeper` - 19 edges
10. `Multifactor Trading System — Design` - 18 edges

## Surprising Connections (you probably didn't know these)
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_beta.py → research/data/store.py
- `FakeConn` --uses--> `PITStore`  [INFERRED]
  tests/test_crsp_loader.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_decompose.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_exposures.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_model.py → research/data/store.py

## Import Cycles
- None detected.

## Communities (38 total, 1 thin omitted)

### Community 0 - "Multifactor Trading System — Design"
Cohesion: 0.10
Nodes (19): Analytics suite (per-factor scoreboard), Backtester (validates Blocks 1–4 before any live loop), Block 1: Data + Signals, Block 1 mini-systems (per-vendor pipeline; every data source, especially each alternative dataset, passes through all of these), Block 2: Alpha Forecast, Block 3: Risk Model (parallel to alpha), Block 4: Portfolio Construction (Optimizer), Block 5: Implementation + Trading System (C++ hot path) (+11 more)

### Community 1 - "STATE"
Cohesion: 0.17
Nodes (11): Constraints, Decisions, Done, Facts, Failed attempts, Goal, Next, Now (+3 more)

### Community 2 - "test_store.py"
Cohesion: 0.22
Nodes (11): main(), port_dataset(), One-time port of a local PITStore dataset into Delta (Block 6c).  Copies every `, Copy every batch of ``dataset`` from local_store into delta_store.      Returns, bars(), FakeDeltaStore, FakeSpark, DataFrame (+3 more)

### Community 3 - "model.py"
Cohesion: 0.05
Nodes (62): build_exposure_matrix(), DataFrame, date, LazyFrame, Factor exposure matrix B (Block 3 risk model).  Per rebalance date: one row per, Exposure matrix B for one rebalance date.      ``sectors`` is the already-asof'd, _zscore(), build_factor_covariance() (+54 more)

### Community 6 - "test_crsp_loader.py"
Cohesion: 0.33
Nodes (8): OrderId, OrderState, is_terminal(), OrderGateway::cancel_order(), OrderGateway::OrderGateway(), OrderGateway::pump(), OrderGateway::state(), OrderGateway::submit_order()

### Community 7 - "METRICS"
Cohesion: 0.15
Nodes (12): Data layer — PITStore (point-in-time parquet store), Data loaders — yfinance daily bars (phase 1: universe scan), Data loaders — yfinance daily bars (phase 2: 15.5-year backfill, top-1500), Data loaders — yfinance sector/industry snapshot, Infra — Block 6c: local lake -> Delta/Databricks port, METRICS, Pending sections (filled as systems are built), PIT store — real-lake point lookup vs full scan (+4 more)

### Community 8 - "AuditReport"
Cohesion: 0.36
Nodes (11): CRSPDailyLoader, scrub -> audit -> PIT store, per DESIGN.md Block 1d contract.      ``conn`` is a, FakeConn, frame(), row(), test_duplicate_rows_quarantined_not_stored(), test_happy_path_lands_in_store(), test_nulls_and_outliers_flagged_not_dropped() (+3 more)

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
Cohesion: 0.07
Nodes (26): Barrel files, C++ engine (Block 5 — broker simulator skeleton, started 2026-07-16), Config, Data layer (Phase 1 — current), engine/ — **built (broker simulator + order gateway + position keeper + risk checker + market data handler + live AlpacaGateway + execution scheduler + kill switch, 66 Catch2 tests, live end-to-end verified)**, Files & functions, Not yet started (DESIGN.md blocks), research/alpha/ic.py — **built (Phase 2, 8 tests)** (+18 more)

### Community 13 - "test_security_master.py"
Cohesion: 0.14
Nodes (32): build_ticker_segments(), empty_master(), main(), DataFrame, date, datetime, LazyFrame, Security master (part 4, block 1): schema + PITStore fit.  Problem this exists t (+24 more)

### Community 15 - "test_signals.py"
Cohesion: 0.10
Nodes (33): Signal registry — every signal follows the same contract.  Each ``compute_*`` fu, compute_low_vol(), _empty_signal(), DataFrame, date, LazyFrame, Low-volatility signal (Phase 2 signals + IC measurement).  Trailing ``window_day, Trailing return-volatility per security, as of ``rebuild_date``.      ``bars`` m (+25 more)

### Community 16 - "test_ic.py"
Cohesion: 0.16
Nodes (30): build_ic_series(), compute_forward_returns(), compute_ic(), _empty_forward_returns(), _ic_for_date(), ic_summary(), IcSummary, main() (+22 more)

### Community 17 - "build_exposure_matrix"
Cohesion: 0.10
Nodes (20): build_ic_series_spark(), main(), DataFrame, datetime, Spark benchmark for the historical alpha run (Block 6d).  Re-executes the SAME p, Same result as build_ic_series (long format: rebalance_date/signal/ic     rows i, DeltaPITStore, DataFrame (+12 more)

### Community 18 - "build_optimizer_inputs"
Cohesion: 0.05
Nodes (70): Problem, compute_market_beta(), _empty_beta(), DataFrame, date, LazyFrame, Per-stock market beta (Block 4b input): rolling single-factor beta.  Needed for, Trailing single-factor beta per security, as of ``rebuild_date``.      ``securit (+62 more)

### Community 19 - "CRSPDailyLoader"
Cohesion: 0.19
Nodes (14): AlpacaMarketDataStream::AlpacaMarketDataStream(), AlpacaMarketDataStream::connect(), string, vector, json, export_target_portfolio(), Path, Writes a TargetPortfolio to common/target_portfolio.json -- the file contract be (+6 more)

### Community 20 - "trade_cost"
Cohesion: 0.06
Nodes (56): AttributionResult, decompose_backtest(), _empty_result(), datetime, Attribution (DESIGN.md Block 6): decompose realized backtest returns into factor, Per rebalance date: how much of that date's target weights came from     factor, ndarray, Block 5a: research-side trading cost model (DESIGN.md Block 5's cost components, (+48 more)

### Community 21 - "compute_market_beta"
Cohesion: 0.12
Nodes (14): PITStore, DataFrame, datetime, LazyFrame, Path, Point-in-time (bitemporal) parquet store.  Every dataset in the lake carries two, A directory-per-dataset parquet lake with point-in-time reads., Write one load batch. Idempotent: same knowledge_ts overwrites.          The bat (+6 more)

### Community 22 - "BrokerSimulator"
Cohesion: 0.06
Nodes (47): deque, EventType, OrderId, string, OrderEvent, id, price, qty (+39 more)

### Community 23 - "IBrokerGateway"
Cohesion: 0.22
Nodes (9): OrderId, OrderState, unordered_map, OrderGateway, cancel_order, pump, state, states_ (+1 more)

### Community 24 - "BrokerSimulator.cpp"
Cohesion: 0.15
Nodes (9): string, KillSwitch, is_tripped, rearm, reason_, trip, tripped_, string (+1 more)

### Community 25 - "OrderGateway.cpp"
Cohesion: 0.12
Nodes (17): string, unordered_map, PositionKeeper, on_fill, position, positions_, string, RiskChecker (+9 more)

### Community 26 - "EventJournal"
Cohesion: 0.33
Nodes (7): string, ParsedTargetPortfolio, positions, status, TargetPosition, symbol, target_notional

### Community 27 - "Order"
Cohesion: 0.23
Nodes (12): Order, is_buy, limit_price, qty, symbol, compute_book_value(), compute_target_orders(), string (+4 more)

### Community 29 - "Quote"
Cohesion: 0.25
Nodes (7): Position, avg_price, qty, realized_pnl, string, PositionKeeper::on_fill(), PositionKeeper::position()

### Community 30 - "AlpacaMarketDataStream.cpp"
Cohesion: 0.08
Nodes (35): AlpacaGateway, alpaca_order_id_, AlpacaGateway::AlpacaGateway(), api_key_, api_secret_, base_url_, cancel_order, connect (+27 more)

### Community 31 - "MarketDataHandler.cpp"
Cohesion: 0.20
Nodes (10): AlpacaMarketDataStream, api_key_, api_secret_, connect, disconnect, symbols_, ws_, string (+2 more)

### Community 32 - "Trade"
Cohesion: 0.09
Nodes (23): string, unordered_map, MarketDataHandler, latest_quote, latest_trade, on_message, quotes_, trades_ (+15 more)

### Community 33 - "wait_for_event"
Cohesion: 0.27
Nodes (5): main(), DataFrame, datetime, Assert expected CIZ columns exist on the live table., Pull one calendar year, audit it, append or quarantine it.

### Community 34 - "ExecutionScheduler"
Cohesion: 0.16
Nodes (11): string, IBrokerGateway, cancel_order, poll_events, submit_order, ExecutionScheduler, book_notional_, high_water_mark_ (+3 more)

### Community 35 - "FakeSparkDataFrame"
Cohesion: 0.22
Nodes (3): FakeSparkColumn, FakeSparkDataFrame, Stands in for a real Spark DataFrame: delegates to the underlying     pandas fra

### Community 36 - "test_store.py"
Cohesion: 0.39
Nodes (8): bars(), DataFrame, store(), test_append_idempotent(), test_append_parts_coexist_and_overwrite(), test_append_rejects_bad_schema(), test_asof_point_in_time(), test_round_trip()

### Community 37 - "MarketDataHandler.cpp"
Cohesion: 0.53
Nodes (5): optional, string, MarketDataHandler::latest_quote(), MarketDataHandler::latest_trade(), MarketDataHandler::on_message()

## Knowledge Gaps
- **154 isolated node(s):** `symbol`, `qty`, `limit_price`, `is_buy`, `submit_order` (+149 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PITStore` connect `compute_market_beta` to `wait_for_event`, `test_store.py`, `model.py`, `FakeSparkDataFrame`, `test_store.py`, `AuditReport`, `YFinanceDailyLoader`, `.load_year`, `test_security_master.py`, `test_signals.py`, `test_ic.py`, `build_optimizer_inputs`, `trade_cost`?**
  _High betweenness centrality (0.554) - this node is a cross-community bridge._
- **Why does `AlpacaGateway` connect `AlpacaMarketDataStream.cpp` to `ExecutionScheduler`, `BrokerSimulator`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Why does `MarketDataHandler` connect `Trade` to `ExecutionScheduler`, `MarketDataHandler.cpp`, `CRSPDailyLoader`, `Order`, `MarketDataHandler.cpp`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `PITStore` (e.g. with `CRSPDailyLoader` and `YFinanceClient`) actually correct?**
  _`PITStore` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `YFinanceDailyLoader` (e.g. with `AuditReport` and `PITStore`) actually correct?**
  _`YFinanceDailyLoader` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `symbol`, `qty`, `limit_price` to the rest of the system?**
  _254 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Multifactor Trading System — Design` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._