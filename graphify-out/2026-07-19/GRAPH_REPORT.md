# Graph Report - multifactor-trading-system  (2026-07-17)

## Corpus Check
- 37 files · ~28,058 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 405 nodes · 765 edges · 16 communities (15 shown, 1 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 16 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ad4ec1f5`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Multifactor Trading System — Design
- STATE
- test_store.py
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

## God Nodes (most connected - your core abstractions)
1. `PITStore` - 45 edges
2. `YFinanceDailyLoader` - 25 edges
3. `BrokerSimulator` - 20 edges
4. `CRSPDailyLoader` - 20 edges
5. `OrderEvent` - 18 edges
6. `Multifactor Trading System — Design` - 18 edges
7. `FakeClient` - 17 edges
8. `HANDOFF — Multifactor Equity Trading System` - 17 edges
9. `AuditReport` - 13 edges
10. `Files & functions` - 13 edges

## Surprising Connections (you probably didn't know these)
- `FakeConn` --uses--> `PITStore`  [INFERRED]
  tests/test_crsp_loader.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_ic.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_signals.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_store.py → research/data/store.py
- `FakeClient` --uses--> `PITStore`  [INFERRED]
  tests/test_yfinance_loader.py → research/data/store.py

## Import Cycles
- None detected.

## Communities (16 total, 1 thin omitted)

### Community 0 - "Multifactor Trading System — Design"
Cohesion: 0.10
Nodes (19): Analytics suite (per-factor scoreboard), Backtester (validates Blocks 1–4 before any live loop), Block 1: Data + Signals, Block 1 mini-systems (per-vendor pipeline; every data source, especially each alternative dataset, passes through all of these), Block 2: Alpha Forecast, Block 3: Risk Model (parallel to alpha), Block 4: Portfolio Construction (Optimizer), Block 5: Implementation + Trading System (C++ hot path) (+11 more)

### Community 1 - "STATE"
Cohesion: 0.17
Nodes (11): Constraints, Decisions, Done, Facts, Failed attempts, Goal, Next, Now (+3 more)

### Community 2 - "test_store.py"
Cohesion: 0.39
Nodes (8): bars(), DataFrame, store(), test_append_idempotent(), test_append_parts_coexist_and_overwrite(), test_append_rejects_bad_schema(), test_asof_point_in_time(), test_round_trip()

### Community 6 - "test_crsp_loader.py"
Cohesion: 0.11
Nodes (24): audit_daily_bars(), AuditReport, DataFrame, Shared audit for daily-bars loaders (DESIGN.md Block 1d).  Every vendor chunk pa, Audit one yearly chunk of daily bars keyed (security_id, effective_date).      H, CRSPDailyLoader, main(), DataFrame (+16 more)

### Community 7 - "METRICS"
Cohesion: 0.18
Nodes (10): Data layer — PITStore (point-in-time parquet store), Data loaders — yfinance daily bars (phase 1: universe scan), Data loaders — yfinance daily bars (phase 2: 15.5-year backfill, top-1500), Data loaders — yfinance sector/industry snapshot, METRICS, Pending sections (filled as systems are built), PIT store — real-lake point lookup vs full scan, Security master — block 2 (ticker segment extraction) (+2 more)

### Community 8 - "AuditReport"
Cohesion: 0.05
Nodes (57): deque, string, IBrokerGateway, cancel_order, poll_events, submit_order, Order, is_buy (+49 more)

### Community 9 - "YFinanceDailyLoader"
Cohesion: 0.07
Nodes (42): fetch_listed_tickers(), main(), DataFrame, datetime, _rate_limited_errors(), (sector, industry) — Yahoo's own taxonomy, not literal GICS codes.          Unli, scrub -> audit -> PIT store, per DESIGN.md Block 1d contract.      ``client`` ex, Pull one calendar year for all tickers, audit, append or quarantine.          Do (+34 more)

### Community 10 - "HANDOFF — Multifactor Equity Trading System"
Cohesion: 0.11
Nodes (17): 10. Dependencies and rationale, 11. Performance model, 12. Known limitations, technical debt, inconsistencies, 13. Non-obvious implementation details & pitfalls, 14. Testing strategy, 15. How to add things, 16. Roadmap & recommended next tasks, 1. Project purpose (+9 more)

### Community 11 - ".load_year"
Cohesion: 0.17
Nodes (25): build_snapshot(), build_universe(), _empty_snapshot(), main(), month_end_trading_days(), DataFrame, date, datetime (+17 more)

### Community 12 - "Files & functions"
Cohesion: 0.11
Nodes (18): Barrel files, C++ engine (Block 5 — broker simulator skeleton, started 2026-07-16), Config, Data layer (Phase 1 — current), engine/ — **built (broker simulator skeleton, 6 Catch2 tests)**, Files & functions, Not yet started (DESIGN.md blocks), research/alpha/ic.py — **built (Phase 2, 8 tests)** (+10 more)

### Community 13 - "test_security_master.py"
Cohesion: 0.08
Nodes (44): Path, PITStore, DataFrame, datetime, LazyFrame, A directory-per-dataset parquet lake with point-in-time reads., Write one load batch. Idempotent: same knowledge_ts overwrites.          The bat, Lazy scan of every batch in a dataset (no PIT filtering). (+36 more)

### Community 15 - "test_signals.py"
Cohesion: 0.09
Nodes (34): Signal registry — every signal follows the same contract.  Each ``compute_*`` fu, compute_low_vol(), _empty_signal(), DataFrame, date, LazyFrame, Low-volatility signal (Phase 2 signals + IC measurement).  Trailing ``window_day, Trailing return-volatility per security, as of ``rebuild_date``.      ``bars`` m (+26 more)

### Community 16 - "test_ic.py"
Cohesion: 0.16
Nodes (29): build_ic_series(), compute_forward_returns(), compute_ic(), _empty_forward_returns(), ic_summary(), IcSummary, main(), DataFrame (+21 more)

## Knowledge Gaps
- **90 isolated node(s):** `symbol`, `qty`, `limit_price`, `is_buy`, `submit_order` (+85 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PITStore` connect `test_security_master.py` to `test_store.py`, `test_crsp_loader.py`, `YFinanceDailyLoader`, `.load_year`, `test_signals.py`, `test_ic.py`?**
  _High betweenness centrality (0.329) - this node is a cross-community bridge._
- **Why does `YFinanceDailyLoader` connect `YFinanceDailyLoader` to `test_security_master.py`, `test_crsp_loader.py`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Why does `CRSPDailyLoader` connect `test_crsp_loader.py` to `test_security_master.py`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `PITStore` (e.g. with `CRSPDailyLoader` and `YFinanceClient`) actually correct?**
  _`PITStore` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `YFinanceDailyLoader` (e.g. with `AuditReport` and `PITStore`) actually correct?**
  _`YFinanceDailyLoader` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `CRSPDailyLoader` (e.g. with `AuditReport` and `PITStore`) actually correct?**
  _`CRSPDailyLoader` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `symbol`, `qty`, `limit_price` to the rest of the system?**
  _140 weakly-connected nodes found - possible documentation gaps or missing edges._