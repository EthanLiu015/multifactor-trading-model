# Graph Report - multifactor-trading-system  (2026-07-13)

## Corpus Check
- 9 files · ~5,342 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 60 nodes · 76 edges · 8 communities (6 shown, 2 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `21524802`
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

## God Nodes (most connected - your core abstractions)
1. `Multifactor Trading System — Design` - 18 edges
2. `FakeConn` - 10 edges
3. `STATE` - 10 edges
4. `frame()` - 7 edges
5. `bars()` - 7 edges
6. `row()` - 6 edges
7. `test_happy_path_lands_in_store()` - 4 edges
8. `test_rerun_same_year_is_idempotent()` - 4 edges
9. `test_duplicate_rows_quarantined_not_stored()` - 4 edges
10. `test_short_past_year_fails_audit()` - 4 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Import Cycles
- None detected.

## Communities (8 total, 2 thin omitted)

### Community 0 - "Multifactor Trading System — Design"
Cohesion: 0.11
Nodes (17): Analytics suite (per-factor scoreboard), Backtester (validates Blocks 1–4 before any live loop), Block 2: Alpha Forecast, Block 3: Risk Model (parallel to alpha), Block 4: Portfolio Construction (Optimizer), Block 5: Implementation + Trading System (C++ hot path), Block 6: Performance Analysis, Build phasing (each block detailed by Ethan before its implementation) (+9 more)

### Community 1 - "STATE"
Cohesion: 0.18
Nodes (10): Constraints, Decisions, Done, Facts, Failed attempts, Goal, Next, Now (+2 more)

### Community 2 - "test_store.py"
Cohesion: 0.39
Nodes (7): DataFrame, bars(), test_append_idempotent(), test_append_parts_coexist_and_overwrite(), test_append_rejects_bad_schema(), test_asof_point_in_time(), test_round_trip()

### Community 6 - "test_crsp_loader.py"
Cohesion: 0.33
Nodes (9): FakeConn, frame(), row(), test_duplicate_rows_quarantined_not_stored(), test_happy_path_lands_in_store(), test_nulls_and_outliers_flagged_not_dropped(), test_rerun_same_year_is_idempotent(), test_short_past_year_fails_audit() (+1 more)

### Community 7 - "METRICS"
Cohesion: 0.50
Nodes (3): Data layer — PITStore (point-in-time parquet store), METRICS, Pending sections (filled as systems are built)

## Knowledge Gaps
- **29 isolated node(s):** `multifactor-trading-system`, `Purpose`, `Locked decisions`, `System overview`, `Block 1 mini-systems (per-vendor pipeline; every data source, especially each alternative dataset, passes through all of these)` (+24 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Multifactor Trading System — Design` connect `Multifactor Trading System — Design` to `Block 1: Data + Signals`?**
  _High betweenness centrality (0.099) - this node is a cross-community bridge._
- **What connects `multifactor-trading-system`, `Purpose`, `Locked decisions` to the rest of the system?**
  _29 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Multifactor Trading System — Design` be split into smaller, more focused modules?**
  _Cohesion score 0.1111111111111111 - nodes in this community are weakly interconnected._