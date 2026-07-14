# Graph Report - multifactor-trading-system  (2026-07-09)

## Corpus Check
- 7 files · ~4,581 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 41 nodes · 41 edges · 6 communities (4 shown, 2 thin omitted)
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

## God Nodes (most connected - your core abstractions)
1. `Multifactor Trading System — Design` - 18 edges
2. `STATE` - 10 edges
3. `bars()` - 6 edges
4. `test_append_rejects_bad_schema()` - 3 edges
5. `test_round_trip()` - 2 edges
6. `test_asof_point_in_time()` - 2 edges
7. `test_append_idempotent()` - 2 edges
8. `Block 1: Data + Signals` - 2 edges
9. `Purpose` - 1 edges
10. `Locked decisions` - 1 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Import Cycles
- None detected.

## Communities (6 total, 2 thin omitted)

### Community 0 - "Multifactor Trading System — Design"
Cohesion: 0.11
Nodes (17): Analytics suite (per-factor scoreboard), Backtester (validates Blocks 1–4 before any live loop), Block 2: Alpha Forecast, Block 3: Risk Model (parallel to alpha), Block 4: Portfolio Construction (Optimizer), Block 5: Implementation + Trading System (C++ hot path), Block 6: Performance Analysis, Build phasing (each block detailed by Ethan before its implementation) (+9 more)

### Community 1 - "STATE"
Cohesion: 0.18
Nodes (10): Constraints, Decisions, Done, Facts, Failed attempts, Goal, Next, Now (+2 more)

### Community 2 - "test_store.py"
Cohesion: 0.43
Nodes (6): DataFrame, bars(), test_append_idempotent(), test_append_rejects_bad_schema(), test_asof_point_in_time(), test_round_trip()

## Knowledge Gaps
- **27 isolated node(s):** `multifactor-trading-system`, `Purpose`, `Locked decisions`, `System overview`, `Block 1 mini-systems (per-vendor pipeline; every data source, especially each alternative dataset, passes through all of these)` (+22 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Multifactor Trading System — Design` connect `Multifactor Trading System — Design` to `Block 1: Data + Signals`?**
  _High betweenness centrality (0.218) - this node is a cross-community bridge._
- **Why does `Block 1: Data + Signals` connect `Block 1: Data + Signals` to `Multifactor Trading System — Design`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **What connects `multifactor-trading-system`, `Purpose`, `Locked decisions` to the rest of the system?**
  _27 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Multifactor Trading System — Design` be split into smaller, more focused modules?**
  _Cohesion score 0.1111111111111111 - nodes in this community are weakly interconnected._