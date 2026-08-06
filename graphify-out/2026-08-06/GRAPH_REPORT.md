# Graph Report - multifactor-trading-system  (2026-08-06)

## Corpus Check
- 105 files · ~67,667 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 921 nodes · 1795 edges · 39 communities (38 shown, 1 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 25 edges (avg confidence: 0.61)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9264fdff`
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
- Trade

## God Nodes (most connected - your core abstractions)
1. `PITStore` - 87 edges
2. `AlpacaGateway` - 27 edges
3. `YFinanceDailyLoader` - 25 edges
4. `OrderEvent` - 23 edges
5. `score_backtest()` - 23 edges
6. `MarketDataHandler` - 22 edges
7. `BacktestStep` - 21 edges
8. `BrokerSimulator` - 20 edges
9. `summarize_backtest()` - 20 edges
10. `CRSPDailyLoader` - 20 edges

## Surprising Connections (you probably didn't know these)
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_beta.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_capacity.py → research/data/store.py
- `FakeConn` --uses--> `PITStore`  [INFERRED]
  tests/test_crsp_loader.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_crsp_loader.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_decompose.py → research/data/store.py

## Import Cycles
- None detected.

## Communities (39 total, 1 thin omitted)

### Community 0 - "Multifactor Trading System — Design"
Cohesion: 0.10
Nodes (19): Analytics suite (per-factor scoreboard), Backtester (validates Blocks 1–4 before any live loop), Block 1: Data + Signals, Block 1 mini-systems (per-vendor pipeline; every data source, especially each alternative dataset, passes through all of these), Block 2: Alpha Forecast, Block 3: Risk Model (parallel to alpha), Block 4: Portfolio Construction (Optimizer), Block 5: Implementation + Trading System (C++ hot path) (+11 more)

### Community 1 - "STATE"
Cohesion: 0.17
Nodes (11): Constraints, Decisions, Done, Facts, Failed attempts, Goal, Next, Now (+3 more)

### Community 2 - "test_store.py"
Cohesion: 0.13
Nodes (14): DeltaPITStore, DataFrame, datetime, Delta-backed point-in-time store — Unity Catalog mirror of PITStore.  Same bitem, The world as known at ``knowledge_ts`` — same semantics as         PITStore.asof, A Unity Catalog schema (``catalog.schema``) with point-in-time reads., MERGE one load batch. Idempotent: same (keys, effective_date,         knowledge_, Every batch in a dataset (no PIT filtering). (+6 more)

### Community 3 - "model.py"
Cohesion: 0.07
Nodes (46): build_factor_covariance(), _ewma_scaled_centered(), _ewma_weights(), ndarray, Factor covariance matrix F (Block 3 risk model).  DESIGN.md: "Factor covariance, n weights, oldest first, most recent = 1.0; normalized so mean = 1., EWMA + Ledoit-Wolf shrunk + Newey-West adjusted factor covariance.      ``factor, build_factor_return_history() (+38 more)

### Community 6 - "test_crsp_loader.py"
Cohesion: 0.33
Nodes (8): OrderId, OrderState, is_terminal(), OrderGateway::cancel_order(), OrderGateway::OrderGateway(), OrderGateway::pump(), OrderGateway::state(), OrderGateway::submit_order()

### Community 7 - "METRICS"
Cohesion: 0.15
Nodes (12): Data layer — PITStore (point-in-time parquet store), Data loaders — yfinance daily bars (phase 1: universe scan), Data loaders — yfinance daily bars (phase 2: 15.5-year backfill, top-1500), Data loaders — yfinance sector/industry snapshot, Infra — Block 6c: local lake -> Delta/Databricks port, METRICS, Pending sections (filled as systems are built), PIT store — real-lake point lookup vs full scan (+4 more)

### Community 8 - "AuditReport"
Cohesion: 0.20
Nodes (14): main(), port_dataset(), One-time port of a local PITStore dataset into Delta (Block 6c).  Copies every `, Copy every batch of ``dataset`` from local_store into delta_store.      Returns, PITStore, A directory-per-dataset parquet lake with point-in-time reads., store(), bars() (+6 more)

### Community 9 - "YFinanceDailyLoader"
Cohesion: 0.06
Nodes (51): audit_daily_bars(), AuditReport, DataFrame, Shared audit for daily-bars loaders (DESIGN.md Block 1d).  Every vendor chunk pa, Audit one yearly chunk of daily bars keyed (security_id, effective_date).      H, CRSP daily-bars loader (WRDS, CRSP 2.0 / "CIZ" format).  Pulls daily bars for al, fetch_listed_tickers(), main() (+43 more)

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
Cohesion: 0.07
Nodes (50): build_exposure_matrix(), DataFrame, date, LazyFrame, Factor exposure matrix B (Block 3 risk model).  Per rebalance date: one row per, Exposure matrix B for one rebalance date.      ``sectors`` is the already-asof'd, _zscore(), Signal registry — every signal follows the same contract.  Each ``compute_*`` fu (+42 more)

### Community 16 - "test_ic.py"
Cohesion: 0.12
Nodes (36): build_ic_series(), compute_forward_returns(), compute_ic(), _empty_forward_returns(), _ic_for_date(), ic_summary(), IcSummary, main() (+28 more)

### Community 17 - "build_exposure_matrix"
Cohesion: 0.17
Nodes (17): CRSPDailyLoader, main(), DataFrame, datetime, scrub -> audit -> PIT store, per DESIGN.md Block 1d contract.      ``conn`` is a, Assert expected CIZ columns exist on the live table., Pull one calendar year, audit it, append or quarantine it., FakeConn (+9 more)

### Community 18 - "build_optimizer_inputs"
Cohesion: 0.06
Nodes (55): Problem, compute_market_beta(), _empty_beta(), DataFrame, date, LazyFrame, Per-stock market beta (Block 4b input): rolling single-factor beta.  Needed for, Trailing single-factor beta per security, as of ``rebuild_date``.      ``securit (+47 more)

### Community 19 - "CRSPDailyLoader"
Cohesion: 0.26
Nodes (12): json, export_target_portfolio(), Path, Writes a TargetPortfolio to common/target_portfolio.json -- the file contract be, Writes ``target.weights * book_notional`` per symbol to ``path`` as JSON.      Z, datetime, Block 4d: end-to-end optimizer orchestration (DESIGN.md Block 4).  Chains build_, TargetPortfolio (+4 more)

### Community 20 - "trade_cost"
Cohesion: 0.06
Nodes (75): capacity_analysis(), CapacityPoint, date, Capacity analysis (DESIGN.md analytics suite): "at what AUM does modeled impact, Sharpe ratio and cumulative net return at each AUM level -- the     capacity cur, BookScorecard, _hit_rate(), _max_drawdown() (+67 more)

### Community 21 - "compute_market_beta"
Cohesion: 0.20
Nodes (16): AttributionResult, decompose_backtest(), _empty_result(), datetime, Attribution (DESIGN.md Block 6): decompose realized backtest returns into factor, Per rebalance date: how much of that date's target weights came from     factor, populated_store(), DataFrame (+8 more)

### Community 22 - "BrokerSimulator"
Cohesion: 0.06
Nodes (47): deque, EventType, OrderId, string, OrderEvent, id, price, qty (+39 more)

### Community 23 - "IBrokerGateway"
Cohesion: 0.14
Nodes (13): IBrokerGateway, cancel_order, poll_events, submit_order, OrderId, OrderState, unordered_map, OrderGateway (+5 more)

### Community 24 - "BrokerSimulator.cpp"
Cohesion: 0.11
Nodes (14): ExecutionScheduler, book_notional_, high_water_mark_, max_drawdown_pct_, run_once, string, KillSwitch, is_tripped (+6 more)

### Community 25 - "OrderGateway.cpp"
Cohesion: 0.12
Nodes (17): string, unordered_map, PositionKeeper, on_fill, position, positions_, string, RiskChecker (+9 more)

### Community 26 - "EventJournal"
Cohesion: 0.24
Nodes (9): string, string, vector, ParsedTargetPortfolio, positions, status, TargetPosition, symbol (+1 more)

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
Cohesion: 0.25
Nodes (13): build_target_portfolio(), DataFrame, date, Target weights for one rebalance date, or ``None`` if inputs can't be built., populated_store(), DataFrame, date, ret_bars() (+5 more)

### Community 34 - "ExecutionScheduler"
Cohesion: 0.21
Nodes (7): DataFrame, datetime, LazyFrame, Path, Write one load batch. Idempotent: same knowledge_ts overwrites.          The bat, Lazy scan of every batch in a dataset (no PIT filtering)., The world as we knew it at ``knowledge_ts``.          Drops rows learned after t

### Community 35 - "FakeSparkDataFrame"
Cohesion: 0.22
Nodes (3): FakeSparkColumn, FakeSparkDataFrame, Stands in for a real Spark DataFrame: delegates to the underlying     pandas fra

### Community 36 - "test_store.py"
Cohesion: 0.39
Nodes (8): bars(), DataFrame, store(), test_append_idempotent(), test_append_parts_coexist_and_overwrite(), test_append_rejects_bad_schema(), test_asof_point_in_time(), test_round_trip()

### Community 37 - "MarketDataHandler.cpp"
Cohesion: 0.53
Nodes (5): optional, string, MarketDataHandler::latest_quote(), MarketDataHandler::latest_trade(), MarketDataHandler::on_message()

### Community 38 - "Trade"
Cohesion: 0.40
Nodes (4): AlpacaMarketDataStream::AlpacaMarketDataStream(), AlpacaMarketDataStream::connect(), string, vector

## Knowledge Gaps
- **154 isolated node(s):** `symbol`, `qty`, `limit_price`, `is_buy`, `submit_order` (+149 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PITStore` connect `AuditReport` to `wait_for_event`, `ExecutionScheduler`, `model.py`, `FakeSparkDataFrame`, `test_store.py`, `YFinanceDailyLoader`, `.load_year`, `test_security_master.py`, `test_signals.py`, `test_ic.py`, `build_exposure_matrix`, `build_optimizer_inputs`, `CRSPDailyLoader`, `trade_cost`, `compute_market_beta`?**
  _High betweenness centrality (0.571) - this node is a cross-community bridge._
- **Why does `AlpacaGateway` connect `AlpacaMarketDataStream.cpp` to `BrokerSimulator`, `IBrokerGateway`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Why does `MarketDataHandler` connect `Trade` to `MarketDataHandler.cpp`, `Trade`, `BrokerSimulator.cpp`, `EventJournal`, `Order`, `MarketDataHandler.cpp`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `PITStore` (e.g. with `CRSPDailyLoader` and `YFinanceClient`) actually correct?**
  _`PITStore` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `YFinanceDailyLoader` (e.g. with `AuditReport` and `PITStore`) actually correct?**
  _`YFinanceDailyLoader` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `symbol`, `qty`, `limit_price` to the rest of the system?**
  _258 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Multifactor Trading System — Design` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._