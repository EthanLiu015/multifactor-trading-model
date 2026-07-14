# Graph Report - multifactor-trading-system  (2026-07-14)

## Corpus Check
- 18 files · ~14,185 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 184 nodes · 325 edges · 13 communities (12 shown, 1 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 12 edges (avg confidence: 0.53)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7134f952`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Multifactor Trading System — Design
- STATE
- test_store.py
- Block 1: Data + Signals
- multifactor-trading-system
- test_crsp_loader.py
- METRICS
- AuditReport
- YFinanceDailyLoader
- HANDOFF — Multifactor Equity Trading System
- .load_year
- Files & functions

## God Nodes (most connected - your core abstractions)
1. `PITStore` - 27 edges
2. `YFinanceDailyLoader` - 22 edges
3. `CRSPDailyLoader` - 20 edges
4. `Multifactor Trading System — Design` - 18 edges
5. `HANDOFF — Multifactor Equity Trading System` - 17 edges
6. `FakeClient` - 14 edges
7. `AuditReport` - 13 edges
8. `FakeConn` - 12 edges
9. `YFinanceClient` - 11 edges
10. `STATE` - 10 edges

## Surprising Connections (you probably didn't know these)
- `FakeClient` --uses--> `YFinanceClient`  [INFERRED]
  tests/test_yfinance_loader.py → research/data/loaders/yfinance_daily.py
- `FakeConn` --uses--> `PITStore`  [INFERRED]
  tests/test_crsp_loader.py → research/data/store.py
- `store()` --calls--> `PITStore`  [EXTRACTED]
  tests/test_store.py → research/data/store.py
- `FakeClient` --uses--> `PITStore`  [INFERRED]
  tests/test_yfinance_loader.py → research/data/store.py
- `FakeConn` --uses--> `CRSPDailyLoader`  [INFERRED]
  tests/test_crsp_loader.py → research/data/loaders/crsp_daily.py

## Import Cycles
- None detected.

## Communities (13 total, 1 thin omitted)

### Community 0 - "Multifactor Trading System — Design"
Cohesion: 0.10
Nodes (19): Analytics suite (per-factor scoreboard), Backtester (validates Blocks 1–4 before any live loop), Block 1: Data + Signals, Block 1 mini-systems (per-vendor pipeline; every data source, especially each alternative dataset, passes through all of these), Block 2: Alpha Forecast, Block 3: Risk Model (parallel to alpha), Block 4: Portfolio Construction (Optimizer), Block 5: Implementation + Trading System (C++ hot path) (+11 more)

### Community 1 - "STATE"
Cohesion: 0.18
Nodes (10): Constraints, Decisions, Done, Facts, Failed attempts, Goal, Next, Now (+2 more)

### Community 2 - "test_store.py"
Cohesion: 0.26
Nodes (11): Top ``top_n`` tickers by median daily dollar volume in ``year``.      Fetch tria, select_liquid_tickers(), bars(), DataFrame, store(), test_append_idempotent(), test_append_parts_coexist_and_overwrite(), test_append_rejects_bad_schema() (+3 more)

### Community 3 - "Block 1: Data + Signals"
Cohesion: 0.14
Nodes (12): LazyFrame, Path, PITStore, DataFrame, datetime, Point-in-time (bitemporal) parquet store.  Every dataset in the lake carries two, A directory-per-dataset parquet lake with point-in-time reads., Write one load batch. Idempotent: same knowledge_ts overwrites.          The bat (+4 more)

### Community 6 - "test_crsp_loader.py"
Cohesion: 0.27
Nodes (13): CRSPDailyLoader, main(), scrub -> audit -> PIT store, per DESIGN.md Block 1d contract.      ``conn`` is a, Assert expected CIZ columns exist on the live table., FakeConn, frame(), row(), test_duplicate_rows_quarantined_not_stored() (+5 more)

### Community 7 - "METRICS"
Cohesion: 0.50
Nodes (3): Data layer — PITStore (point-in-time parquet store), METRICS, Pending sections (filled as systems are built)

### Community 8 - "AuditReport"
Cohesion: 0.18
Nodes (10): audit_daily_bars(), AuditReport, DataFrame, Shared audit for daily-bars loaders (DESIGN.md Block 1d).  Every vendor chunk pa, Audit one yearly chunk of daily bars keyed (security_id, effective_date).      H, DataFrame, datetime, CRSP daily-bars loader (WRDS, CRSP 2.0 / "CIZ" format).  Pulls daily bars for al (+2 more)

### Community 9 - "YFinanceDailyLoader"
Cohesion: 0.17
Nodes (21): scrub -> audit -> PIT store, per DESIGN.md Block 1d contract.      ``client`` ex, One ticker per line; blank lines and '#' comments skipped., read_tickers_file(), YFinanceDailyLoader, FakeClient, _patched_client(), YFinanceClient with fake yf.download, shared._ERRORS, recorded sleeps., {ticker: {date: (close, adj_close, volume)}} -> yfinance wide frame. (+13 more)

### Community 10 - "HANDOFF — Multifactor Equity Trading System"
Cohesion: 0.11
Nodes (17): 10. Dependencies and rationale, 11. Performance model, 12. Known limitations, technical debt, inconsistencies, 13. Non-obvious implementation details & pitfalls, 14. Testing strategy, 15. How to add things, 16. Roadmap & recommended next tasks, 1. Project purpose (+9 more)

### Community 11 - ".load_year"
Cohesion: 0.12
Nodes (14): fetch_listed_tickers(), main(), DataFrame, datetime, _rate_limited_errors(), Pull one calendar year for all tickers, audit, append or quarantine.          Do, Wide yfinance frames -> long internal schema.          yfinance returns one colu, Snapshot current shares outstanding into its own dataset.          One row per t (+6 more)

### Community 12 - "Files & functions"
Cohesion: 0.17
Nodes (11): Barrel files, Config, Data layer (Phase 1 — current), Files & functions, Not yet started (DESIGN.md blocks), research/data/loaders/audit.py — **built (part 2b, shared by all loaders)**, research/data/loaders/crsp_daily.py — **built** (6 tests; live pull blocked until fall), research/data/loaders/yfinance_daily.py — **built (part 2b; interim vendor while WRDS blocked)** (+3 more)

## Knowledge Gaps
- **54 isolated node(s):** `multifactor-trading-system`, `Purpose`, `Locked decisions`, `System overview`, `Block 1 mini-systems (per-vendor pipeline; every data source, especially each alternative dataset, passes through all of these)` (+49 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PITStore` connect `Block 1: Data + Signals` to `test_store.py`, `test_crsp_loader.py`, `AuditReport`, `YFinanceDailyLoader`, `.load_year`?**
  _High betweenness centrality (0.195) - this node is a cross-community bridge._
- **Why does `YFinanceDailyLoader` connect `YFinanceDailyLoader` to `AuditReport`, `Block 1: Data + Signals`, `.load_year`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Why does `CRSPDailyLoader` connect `test_crsp_loader.py` to `AuditReport`, `Block 1: Data + Signals`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `PITStore` (e.g. with `CRSPDailyLoader` and `YFinanceClient`) actually correct?**
  _`PITStore` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `YFinanceDailyLoader` (e.g. with `AuditReport` and `PITStore`) actually correct?**
  _`YFinanceDailyLoader` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `CRSPDailyLoader` (e.g. with `AuditReport` and `PITStore`) actually correct?**
  _`CRSPDailyLoader` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `multifactor-trading-system`, `Shared audit for daily-bars loaders (DESIGN.md Block 1d).  Every vendor chunk pa`, `Audit one yearly chunk of daily bars keyed (security_id, effective_date).      H` to the rest of the system?**
  _77 weakly-connected nodes found - possible documentation gaps or missing edges._