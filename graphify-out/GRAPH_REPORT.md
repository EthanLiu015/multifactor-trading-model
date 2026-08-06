# Graph Report - multifactor-trading-system  (2026-08-06)

## Corpus Check
- 108 files · ~69,030 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 942 nodes · 1828 edges · 43 communities (41 shown, 2 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 25 edges (avg confidence: 0.61)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9c8d8e0b`
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
- score_backtest
- IBrokerGateway
- test_result.py
- KillSwitch.cpp

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
- `test_summarize_backtest_empty_steps_gives_empty_result()` --calls--> `summarize_backtest()`  [EXTRACTED]
  tests/test_result.py → research/backtest/result.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_beta.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_capacity.py → research/data/store.py
- `FakeConn` --uses--> `PITStore`  [INFERRED]
  tests/test_crsp_loader.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_crsp_loader.py → research/data/store.py

## Import Cycles
- None detected.

## Communities (43 total, 2 thin omitted)

### Community 0 - "Multifactor Trading System — Design"
Cohesion: 0.10
Nodes (19): Analytics suite (per-factor scoreboard), Backtester (validates Blocks 1–4 before any live loop), Block 1: Data + Signals, Block 1 mini-systems (per-vendor pipeline; every data source, especially each alternative dataset, passes through all of these), Block 2: Alpha Forecast, Block 3: Risk Model (parallel to alpha), Block 4: Portfolio Construction (Optimizer), Block 5: Implementation + Trading System (C++ hot path) (+11 more)

### Community 1 - "STATE"
Cohesion: 0.17
Nodes (11): Constraints, Decisions, Done, Facts, Failed attempts, Goal, Next, Now (+3 more)

### Community 2 - "test_store.py"
Cohesion: 0.10
Nodes (20): build_ic_series_spark(), main(), DataFrame, datetime, Spark benchmark for the historical alpha run (Block 6d).  Re-executes the SAME p, Same result as build_ic_series (long format: rebalance_date/signal/ic     rows i, DeltaPITStore, DataFrame (+12 more)

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
Cohesion: 0.15
Nodes (12): ComplianceChecker, check, max_order_shares_, reset, restricted_symbols_, seen_this_batch_, ComplianceResult, passed (+4 more)

### Community 9 - "YFinanceDailyLoader"
Cohesion: 0.06
Nodes (50): audit_daily_bars(), AuditReport, DataFrame, Shared audit for daily-bars loaders (DESIGN.md Block 1d).  Every vendor chunk pa, Audit one yearly chunk of daily bars keyed (security_id, effective_date).      H, CRSP daily-bars loader (WRDS, CRSP 2.0 / "CIZ" format).  Pulls daily bars for al, fetch_listed_tickers(), main() (+42 more)

### Community 10 - "HANDOFF — Multifactor Equity Trading System"
Cohesion: 0.11
Nodes (17): 10. Dependencies and rationale, 11. Performance model, 12. Known limitations, technical debt, inconsistencies, 13. Non-obvious implementation details & pitfalls, 14. Testing strategy, 15. How to add things, 16. Roadmap & recommended next tasks, 1. Project purpose (+9 more)

### Community 11 - ".load_year"
Cohesion: 0.16
Nodes (26): build_snapshot(), build_universe(), _empty_snapshot(), main(), month_end_trading_days(), DataFrame, date, datetime (+18 more)

### Community 12 - "Files & functions"
Cohesion: 0.07
Nodes (26): Barrel files, C++ engine (Block 5 — broker simulator skeleton, started 2026-07-16), Config, Data layer (Phase 1 — current), engine/ — **built (broker simulator + order gateway + position keeper + risk checker + market data handler + live AlpacaGateway + execution scheduler + kill switch + compliance checker, 76 Catch2 tests, live end-to-end verified)**, Files & functions, Not yet started (DESIGN.md blocks), research/alpha/ic.py — **built (Phase 2, 8 tests)** (+18 more)

### Community 13 - "test_security_master.py"
Cohesion: 0.05
Nodes (58): main(), port_dataset(), One-time port of a local PITStore dataset into Delta (Block 6c).  Copies every `, Copy every batch of ``dataset`` from local_store into delta_store.      Returns, PITStore, DataFrame, datetime, LazyFrame (+50 more)

### Community 15 - "test_signals.py"
Cohesion: 0.10
Nodes (33): Signal registry — every signal follows the same contract.  Each ``compute_*`` fu, compute_low_vol(), _empty_signal(), DataFrame, date, LazyFrame, Low-volatility signal (Phase 2 signals + IC measurement).  Trailing ``window_day, Trailing return-volatility per security, as of ``rebuild_date``.      ``bars`` m (+25 more)

### Community 16 - "test_ic.py"
Cohesion: 0.16
Nodes (30): build_ic_series(), compute_forward_returns(), compute_ic(), _empty_forward_returns(), _ic_for_date(), ic_summary(), IcSummary, main() (+22 more)

### Community 17 - "build_exposure_matrix"
Cohesion: 0.17
Nodes (17): CRSPDailyLoader, main(), DataFrame, datetime, scrub -> audit -> PIT store, per DESIGN.md Block 1d contract.      ``conn`` is a, Assert expected CIZ columns exist on the live table., Pull one calendar year, audit it, append or quarantine it., FakeConn (+9 more)

### Community 18 - "build_optimizer_inputs"
Cohesion: 0.06
Nodes (55): Problem, compute_market_beta(), _empty_beta(), DataFrame, date, LazyFrame, Per-stock market beta (Block 4b input): rolling single-factor beta.  Needed for, Trailing single-factor beta per security, as of ``rebuild_date``.      ``securit (+47 more)

### Community 19 - "CRSPDailyLoader"
Cohesion: 0.14
Nodes (24): export_target_portfolio(), Path, Writes a TargetPortfolio to common/target_portfolio.json -- the file contract be, Writes ``target.weights * book_notional`` per symbol to ``path`` as JSON.      Z, build_target_portfolio(), DataFrame, date, datetime (+16 more)

### Community 20 - "trade_cost"
Cohesion: 0.15
Nodes (22): _empty_holding_returns(), _holding_period_return(), DataFrame, date, datetime, LazyFrame, Block 5b: walk-forward day-loop orchestrator (DESIGN.md's Backtester).  The sole, Walk-forward backtest over ``[start_date, end_date]``.      ``cost_kwargs`` forw (+14 more)

### Community 21 - "compute_market_beta"
Cohesion: 0.21
Nodes (17): AttributionResult, decompose_backtest(), _empty_result(), datetime, Attribution (DESIGN.md Block 6): decompose realized backtest returns into factor, Per rebalance date: how much of that date's target weights came from     factor, BacktestStep, populated_store() (+9 more)

### Community 22 - "BrokerSimulator"
Cohesion: 0.06
Nodes (47): deque, EventType, OrderId, string, OrderEvent, id, price, qty (+39 more)

### Community 23 - "IBrokerGateway"
Cohesion: 0.22
Nodes (9): OrderId, OrderState, unordered_map, OrderGateway, cancel_order, pump, state, states_ (+1 more)

### Community 24 - "BrokerSimulator.cpp"
Cohesion: 0.25
Nodes (7): string, KillSwitch, is_tripped, rearm, reason_, trip, tripped_

### Community 25 - "OrderGateway.cpp"
Cohesion: 0.12
Nodes (17): string, unordered_map, PositionKeeper, on_fill, position, positions_, string, RiskChecker (+9 more)

### Community 26 - "EventJournal"
Cohesion: 0.20
Nodes (9): string, string, vector, ParsedTargetPortfolio, positions, status, TargetPosition, symbol (+1 more)

### Community 27 - "Order"
Cohesion: 0.43
Nodes (7): compute_book_value(), compute_target_orders(), string, vector, ExecutionScheduler::ExecutionScheduler(), ExecutionScheduler::run_once(), parse_target_portfolio()

### Community 29 - "Quote"
Cohesion: 0.29
Nodes (7): Position, avg_price, qty, realized_pnl, string, PositionKeeper::on_fill(), PositionKeeper::position()

### Community 30 - "AlpacaMarketDataStream.cpp"
Cohesion: 0.06
Nodes (40): AlpacaGateway, alpaca_order_id_, AlpacaGateway::AlpacaGateway(), api_key_, api_secret_, base_url_, cancel_order, connect (+32 more)

### Community 31 - "MarketDataHandler.cpp"
Cohesion: 0.20
Nodes (10): AlpacaMarketDataStream, api_key_, api_secret_, connect, disconnect, symbols_, ws_, string (+2 more)

### Community 32 - "Trade"
Cohesion: 0.16
Nodes (12): unordered_map, MarketDataHandler, latest_quote, latest_trade, on_message, quotes_, trades_, string (+4 more)

### Community 33 - "wait_for_event"
Cohesion: 0.21
Nodes (13): capacity_analysis(), CapacityPoint, date, Capacity analysis (DESIGN.md analytics suite): "at what AUM does modeled impact, Sharpe ratio and cumulative net return at each AUM level -- the     capacity cur, populated_store(), DataFrame, date (+5 more)

### Community 34 - "ExecutionScheduler"
Cohesion: 0.21
Nodes (10): ndarray, Block 5a: research-side trading cost model (DESIGN.md Block 5's cost components,, Per-security $ trading cost for one rebalance's ``delta_w = w - w_prev``.      `, trade_cost(), BacktestResult, Block 5c: backtest result/equity-curve summary.  Pure aggregation over BacktestS, Square-root impact: the cost RATE (bps) grows as sqrt(size), not the     total $, test_impact_rate_scales_sublinearly_with_trade_size() (+2 more)

### Community 35 - "FakeSparkDataFrame"
Cohesion: 0.40
Nodes (13): Equity curve + cost/turnover series over ``steps``.      Only steps with a ``per, summarize_backtest(), date, _step(), store(), test_gross_and_net_exposure_stay_aligned_when_a_step_is_excluded(), test_hit_rate_matches_hand_computation(), test_max_drawdown_matches_hand_computation() (+5 more)

### Community 36 - "test_store.py"
Cohesion: 0.39
Nodes (8): bars(), DataFrame, store(), test_append_idempotent(), test_append_parts_coexist_and_overwrite(), test_append_rejects_bad_schema(), test_asof_point_in_time(), test_round_trip()

### Community 37 - "MarketDataHandler.cpp"
Cohesion: 0.15
Nodes (16): string, Quote, ask_price, ask_size, bid_price, bid_size, timestamp, Trade (+8 more)

### Community 38 - "Trade"
Cohesion: 0.20
Nodes (10): Order, is_buy, limit_price, qty, symbol, ComplianceChecker::check(), ComplianceChecker::ComplianceChecker(), string (+2 more)

### Community 39 - "score_backtest"
Cohesion: 0.29
Nodes (11): BookScorecard, _hit_rate(), _max_drawdown(), datetime, LazyFrame, ndarray, Book-level scorecard (DESIGN.md's analytics suite: Sharpe, IR, gross/net exposur, Book-level metrics from a completed backtest.      ``steps`` is the same list pa (+3 more)

### Community 40 - "IBrokerGateway"
Cohesion: 0.20
Nodes (9): IBrokerGateway, cancel_order, poll_events, submit_order, ExecutionScheduler, book_notional_, high_water_mark_, max_drawdown_pct_ (+1 more)

### Community 41 - "test_result.py"
Cohesion: 0.60
Nodes (5): date, _step(), test_net_return_below_gross_return_when_cost_positive(), test_summarize_backtest_empty_steps_gives_empty_result(), test_summarize_backtest_equity_curve_matches_hand_computation()

## Knowledge Gaps
- **161 isolated node(s):** `symbol`, `qty`, `limit_price`, `is_buy`, `submit_order` (+156 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PITStore` connect `test_security_master.py` to `wait_for_event`, `model.py`, `FakeSparkDataFrame`, `test_store.py`, `score_backtest`, `YFinanceDailyLoader`, `.load_year`, `test_signals.py`, `test_ic.py`, `build_exposure_matrix`, `build_optimizer_inputs`, `CRSPDailyLoader`, `trade_cost`, `compute_market_beta`?**
  _High betweenness centrality (0.566) - this node is a cross-community bridge._
- **Why does `ExecutionScheduler::ExecutionScheduler()` connect `Order` to `Trade`, `IBrokerGateway`, `AuditReport`, `BrokerSimulator.cpp`, `OrderGateway.cpp`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Why does `AlpacaGateway` connect `AlpacaMarketDataStream.cpp` to `IBrokerGateway`, `BrokerSimulator`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `PITStore` (e.g. with `CRSPDailyLoader` and `YFinanceClient`) actually correct?**
  _`PITStore` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `YFinanceDailyLoader` (e.g. with `AuditReport` and `PITStore`) actually correct?**
  _`YFinanceDailyLoader` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `symbol`, `qty`, `limit_price` to the rest of the system?**
  _265 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Multifactor Trading System — Design` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._