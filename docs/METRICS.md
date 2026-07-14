# METRICS

Resume-grade measured metrics for the multifactor trading system.

**Rules for this file**
1. Only *measured* numbers — every entry carries the command, date, and hardware. No estimates, no "should be".
2. Baselines recorded before optimizations, so speedup claims have a denominator.
3. Resume-ready phrasing included per entry, but the raw numbers are the source of truth.

**Hardware (all entries unless noted)**: Apple M4, 10 cores, 16 GB RAM, macOS (Darwin 24.6.0), Python 3.10.2, polars 1.42.1.

---

## Data layer — PITStore (point-in-time parquet store)

**Measured 2026-07-09** — `bench_store.py`: synthetic production-scale load, 1,000 securities × 15 years daily bars (3,915,000 rows, 4 columns + 2 stamp columns).

| Metric | Value |
|---|---|
| Dataset | 3,915,000 rows (1,000 securities × 3,915 days) |
| Storage: raw in-memory | 105.7 MB |
| Storage: parquet on disk (zstd) | 13.0 MB |
| **Compression ratio** | **8.1×** |
| **Ingest (append) throughput** | **46.7M rows/s** (0.084 s for 3.9M rows) |
| **Full-lake lazy scan + collect** | **106.5M rows/s** (0.037 s) |
| Point-in-time (`asof`) query, full lake | 1.06 s (3.7M rows/s) — baseline, pre-optimization |
| Point-in-time query, 1 security × 1 year | 14.6 ms (261 rows) |

Notes:
- `asof` full-lake at 1.06 s is the recorded **baseline** for a future speedup entry (date-partitioning + pushdown planned in part 2+).
- 15 years × 1,000 names of daily bars fits in 13 MB — quantifies the "local-first, distribute second" design decision in DESIGN.md.

Resume phrasing:
- "Built a bitemporal (point-in-time) market-data store in Python/Polars sustaining 46M rows/s ingest and 100M+ rows/s scans over a 15-year, 1,000-name equity dataset, with 8× on-disk compression."

---

## Pending sections (filled as systems are built)

- **Universe builder**: build time for full 15y monthly PIT snapshots.
- **Signal/alpha pipeline**: signals/day throughput, full-history recompute wall time, Spark vs local speedup.
- **Backtester**: simulated days/s, full 15y walk-forward wall time.
- **Optimizer**: solve time per rebalance (1,000-name QP with all constraints).
- **C++ engine**: tick-to-order latency histogram (p50/p99/p99.9 ns), queue hop latency, orders/s throughput, journal write latency, recovery-replay time.
- **Data loaders**: rows/day ingested, audit-check overhead.
