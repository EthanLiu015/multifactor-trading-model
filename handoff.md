# HANDOFF — Multifactor Equity Trading System

> Primary-context document for any agent or developer continuing this project.
> Written 2026-07-13. Ground truth hierarchy when documents disagree:
> **code + tests > docs/STATE.md > docs/DESIGN.md > this file > everything else.**
> Read docs/STATE.md first in every new session — it is the live state ledger.

---

## 1. Project purpose

Build a multifactor equity trading system that replicates a quant firm's internal stack end-to-end — data lake → signals → alpha → risk model → optimizer → C++ execution → attribution — following the **Grinold & Kahn active-management framework**.

Dual goals, both first-class:

1. **Learning** — the owner (Ethan, Duke sophomore targeting quant recruiting) is using the build to learn how each subsystem of a real quant stack works. This drives the *process* (see §9: explain-before-build) as much as the code.
2. **Resume artifact** — every subsystem is engineered and *measured* like production (docs/METRICS.md holds resume-grade numbers with commands and hardware). "Built on CRSP via WRDS", "bitemporal store", "lock-free C++ hot path" are deliberate recruiting signals.

The unifying theory: **IR = IC × √breadth** (fundamental law of active management). Every block's job is stated in those terms — signals raise IC, universe/cadence raise breadth, optimizer + execution protect the transfer coefficient.

## 2. Long-term vision (from docs/DESIGN.md — the canonical architecture doc)

Six blocks plus cross-cutting layers:

```
┌─────────────────┐
│ 1. Data+Signals │◄─────────────────────────────┐
└───────┬─────────┘                              │
        ▼                                        │ feedback loop
┌─────────────────┐    ┌──────────────┐          │ (edges decay)
│ 2. Alpha        │    │ 3. Risk model│          │
│    Forecast     │    │ (parallel)   │          │
└───────┬─────────┘    └──────┬───────┘          │
        ▼                     ▼                  │
┌─────────────────────────────────┐              │
│ 4. Portfolio construction (QP)  │              │
└───────┬─────────────────────────┘              │
        │  target holdings                       │
        ▼                                        │
┌─────────────────────────────────┐              │
│ 5. Implementation + trading     │ ← C++ hot path
└───────┬─────────────────────────┘              │
        ▼                                        │
┌─────────────────────────────────┐              │
│ 6. Performance analysis         │──────────────┘
└─────────────────────────────────┘
```

Locked decisions (do not relitigate; full table in DESIGN.md):

| Decision | Choice |
|---|---|
| Stack | C++ hot path (execution) + Python research stack |
| Execution | Alpaca paper trading (live data, real order lifecycle, zero risk) |
| Universe | Top ~1,000 US equities by 60d median dollar volume, point-in-time membership |
| Portfolio | Long-short, dollar-neutral + **beta-neutral** + sector-neutral |
| Cadence | Daily rebalance |
| Batch infra (later) | Databricks + Spark + Delta Lake on S3; kdb+ for live ticks |
| Data budget | Free sources only (+ WRDS/CRSP via university access) |
| PIT mechanism | Explicit bitemporal columns primary; Delta time-travel is audit layer only |
| Risk control | No per-name stop losses; book-level protection (drawdown kill switch) |

**Phasing rule — local-first, distribute second**: ~1,000 names × 15y daily ≈ a few GB; fits in Polars on a laptop (measured: 13 MB parquet). The distributed stack is a learning/resume showcase, ported *after* the vertical slice works locally. Never let infra gate alpha work.

## 3. Current implementation status (2026-07-13)

Honest inventory. **Built** means tested code in the repo; nothing else is.

| Component | Status | Evidence |
|---|---|---|
| PITStore (bitemporal parquet store) | **BUILT** | `research/data/store.py`, 5 tests |
| CRSP daily-bars loader (WRDS, CIZ format) | **BUILT, live-pull blocked** | `research/data/loaders/crsp_daily.py`, 6 offline tests. Duke WRDS access is academic-year only — no live pull until ~late Aug 2026. CIZ column names are **UNVERIFIED** against the live table (`verify_schema()` gates every pull) |
| yfinance interim loader + shared `audit.py` | **APPROVED SPEC, not built** | Spec in conversation + docs/SYSTEM_MAP.md. Backfill window decided: 2011→today, daily bars |
| Universe builder (part 3) | designed only (DESIGN.md Block 1) | |
| Security master + matching (part 4) | designed only | |
| Signals/alpha/risk/optimizer/backtester | designed only (DESIGN.md Blocks 2–4 + Backtester) | |
| C++ engine, ops layer, analytics suite | designed only (Blocks 5–6) | |
| Test suite | **11 passing** — `.venv/bin/python -m pytest` | |

Full test suite currently: `11 passed`. Baseline discipline: run it before and after every change set.

## 4. Repository layout

```
research/               Python research stack (only package with code so far)
  data/
    store.py            PITStore — the bitemporal core. Everything depends on it.
    loaders/
      crsp_daily.py     CRSP/WRDS vendor adapter (scrub → audit → PIT append)
      __init__.py       exports CRSPDailyLoader
    __init__.py         exports PITStore
tests/                  pytest; offline-only (fake vendor connections)
docs/
  DESIGN.md             CANONICAL architecture. Block-by-block, decisions locked by owner.
  STATE.md              Live session ledger: Now/Next/Constraints/Decisions/Done/Open items.
  METRICS.md            Measured performance numbers ONLY (command + date + hardware).
  SYSTEM_MAP.md         Living per-file/per-function diagram. Update in the same
                        session as any file/function change (owner requirement).
  guardrails/           Mandatory process checklists (PLAN/CODE/DEBUG/VERIFY/...).
                        CLAUDE.md routes to them on trigger events. Follow literally.
engine/ common/ infra/  NOT YET CREATED — reserved by DESIGN.md repo-layout section
pyproject.toml          deps: polars>=1.42, wrds>=3.2; pytest config
graphify-out/           generated code knowledge graph (query with `graphify query "..."`)
lake/                   NOT YET CREATED — default PITStore root once a backfill runs
```

Planned-but-absent directories (`research/signals/`, `research/risk/`, `engine/`, …) are named in DESIGN.md's repo-layout section; do not create them before their block's build phase.

## 5. The core abstraction — bitemporal PIT store

The entire research stack is built around one invariant: **look-ahead bias is prevented by construction, not by caller discipline.** This is DESIGN.md's stated #1 killer of fake backtests, and it is enforced structurally:

Every row in the lake has two time axes:
- `effective_date` — when the fact was true in the market (trade date, fiscal period end). Supplied by the loader.
- `knowledge_ts` — when *we* learned it (download time). **Stamped by the store; a caller supplying it is a ValueError.** Loaders physically cannot forge knowledge time.

Interface (`research/data/store.py`, ~100 lines, read it):

```python
store.append(dataset, df, knowledge_ts, part=None)  # write one load batch
store.asof(dataset, T, keys)   # LazyFrame: the world as known at time T
store.scan(dataset)            # raw lazy scan, no PIT filter — debugging only
```

- `append` validates (`effective_date` required as `pl.Date`; stamp columns forbidden), stamps `knowledge_ts` + `load_ts`, writes one parquet file named `k=<knowledge_ts>[_part=<part>].parquet`. **Idempotency by filename**: re-running the same load overwrites its own file — no dedup logic exists anywhere, none is needed. `part` (e.g. year) splits one logical load into several files under one knowledge_ts; re-running one part overwrites only that part.
- `asof` = filter `knowledge_ts <= T`, sort by `knowledge_ts`, `group_by(keys + effective_date).last()` — latest *known* revision of each row wins. Vendor restatements and yfinance's retroactive back-adjustment are both handled by this one mechanism: each new pull is a new batch under a new knowledge_ts; `asof` serves each backtest date the vintage it could actually have known.
- **`asof` is the only legitimate research read path.** Any future code reading the lake via `scan()` or raw `scan_parquet` in research logic is a design violation.

Why parquet files per batch instead of a database: append-only immutable batches make idempotency, PIT vintages, and audit trivially correct; Polars lazy scans give predicate pushdown (knowledge_ts is constant per file → whole files pruned from footer stats alone); and the layout ports directly to Delta-on-S3 in the infra phase.

## 6. The loader contract (DESIGN.md Block 1d)

Every data vendor — bars today; fundamentals, short interest, sentiment later — passes the same pipeline:

```
pull (vendor API) → transform (vendor names → internal schema)
                  → audit (dups hard-fail; anomalies flagged, never dropped)
                  → PASS: store.append(...)   FAIL: lake/_quarantine/, never enters PIT data
```

Reference implementation: `CRSPDailyLoader` (`research/data/loaders/crsp_daily.py`). Key properties to replicate in every new loader:

- **Connection injected** in the constructor → tests use an offline fake (`FakeConn` in `tests/test_crsp_loader.py`), no network in the suite.
- **Schema verification against the live source** (`verify_schema()`) before any pull — column names are asserted, never assumed.
- Internal schema: `security_id`, `effective_date` (+ data columns). Vendor identifier stays vendor-native (CRSP: permno as int; yfinance: ticker as string) and datasets are **never mixed** — `crsp_daily` and `yfinance_daily` stay parallel until the security master (part 4) maps identifiers.
- Audit failures **quarantine the batch** (`lake/_quarantine/`), report, and continue; anomalous *rows* (nulls, |ret| > 200%) are counted and kept, never silently dropped.
- CLI entry (`python -m research.data.loaders.crsp_daily --start 2011`) prints per-year audit reports + rows/s for METRICS.md.

Adding a vendor = implement this contract, nothing else. PIT correctness, idempotency, and revision handling are inherited from the store.

## 7. Data flow end-to-end (current + near-term)

```
WRDS/CRSP ──raw_sql──► CRSPDailyLoader ──append(part=year)──► lake/crsp_daily/
yfinance  ──(2b)─────► YFinanceLoader  ──append(part=year)──► lake/yfinance_daily/
NASDAQ symbol files ──► (2b: listed-universe filter)                │
                                                                    ▼
                        research reads: store.asof(dataset, sim_date, keys)
                                                                    │
                              universe builder (part 3) ──► signals ──► backtester
```

Backtest access pattern (important): **panel pulls, not point lookups.** One `asof` per rebalance date returning the full cross-section; per-stock-per-day queries are malpractice against columnar storage. Measured baseline: full-lake `asof` ≈ 1.06 s over 3.9M rows (see §11).

## 8. Coding conventions

Observed throughout; follow them:

- **Polars for tables, NumPy for matrices** (DESIGN 1c). All transforms are column expressions; **no Python loops over stocks or dates** — the backtester's day loop will be the sole sanctioned exception.
- **Lazy by default**: store returns `LazyFrame`s; callers compose and `.collect()` once.
- **Timestamps are naive UTC** everywhere: `dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)` — matches the store's stamp idiom. Never compare naive and aware datetimes.
- **Explicit None checks** (`if part is not None`), never truthiness on values that can be 0/""/False.
- Docstrings explain *why* and semantics (read `store.py`'s module docstring — that's house style); comments state constraints code can't show, nothing else.
- Module constants for vendor specifics (`SRC_COLUMNS`, `COMMON_STOCK_WHERE`) with provenance comments.
- Dataclasses for structured results (`AuditReport` with `ok` property).
- Tests: plain pytest, `tmp_path` store fixture, small canned frames, one behavior per test, offline always.
- **Process conventions are binding** (see §9). CLAUDE.md + docs/guardrails/ are literal procedure, not advice; they compensate for known agent failure modes.

## 9. Development process (as important as the code)

The owner runs a strict protocol — violating it damages trust regardless of code quality:

1. **Explain-before-build.** Every "part" (small unit of a system) is explained to Ethan in nitty-gritty detail — each block of code and what it does — *before* implementation. He approves, then code happens. This is a learning project; skipping the explanation defeats its purpose. (Verbatim constraints in docs/STATE.md `## Constraints`.)
2. **docs/STATE.md is the ledger.** Update Now/Next/Done (with evidence lines) as work progresses; append user constraints verbatim the turn they're stated; record decisions with rationale.
3. **docs/METRICS.md takes measured numbers only** — command + date + hardware, baselines before optimizations. No estimates ever.
4. **docs/SYSTEM_MAP.md updated in the same session** as any file/function change.
5. **Guardrails kit** (docs/guardrails/): event-triggered checklists (PLAN before multi-file work, CODE before edits, DEBUG on failures, VERIFY before claiming done). CLAUDE.md's routing table says when; follow it literally, cite checklist IDs.
6. **graphify**: run `graphify query "<question>"` before raw file exploration; `graphify update .` after code changes (repo hooks enforce this).
7. Verification vocabulary: claims of done/passing require fresh command output in-turn; otherwise `EDITED-UNVERIFIED` / `UNVERIFIED — to confirm, run: <cmd>`.

## 10. Dependencies and rationale

| Dep | Version | Why |
|---|---|---|
| polars | ≥1.42 (1.42.1 installed) | Columnar + lazy + parallel; pushdown makes the PIT store fast with zero index infrastructure; LazyFrame plans mirror Spark plans → cheap port in the infra phase (DESIGN 1c "engine-agnostic") |
| wrds | ≥3.2 (3.5.0 installed) | Official WRDS Postgres client for CRSP. Pulls pandas → converted to Polars once at the boundary |
| pytest | ≥9 (9.1.1) | Test runner. `testpaths = ["tests"]` |
| yfinance | pending (part 2b) | Interim free bars vendor while WRDS is season-blocked |

Python 3.10 venv at `.venv/`; test command `.venv/bin/python -m pytest`. No uv, no lockfile (known gap, §12). Future (designed, not installed): cvxpy/OSQP (Block 4), Spark/Databricks/Delta (infra phase), kdb+ (live ticks).

## 11. Performance model

Measured (docs/METRICS.md, Apple M4, 16 GB; synthetic 1,000 names × 15y = 3.9M rows):

- parquet+zstd compression **8.1×** (105.7 MB → 13.0 MB on disk)
- append **46.7M rows/s**; full-lake scan **106.5M rows/s**
- full-lake `asof` **1.06 s** — recorded as *the* baseline for a future optimization entry
- 1 security × 1 year `asof`: 14.6 ms

Design consequences: at this scale, brute force + pushdown wins; no premature indexing. The agreed escalation ladder if real-data metrics degrade (in order, all behind `asof()`'s unchanged signature): sort-on-write within batch files → tighter row-group pruning; hive-partition by effective-year; materialized latest-revision snapshots; Delta data-skipping/Z-order once on S3. **Do not implement any rung without a measured trigger recorded in METRICS.md.**

## 12. Known limitations, technical debt, inconsistencies

Ordered by severity. None are hidden in the code — all are stated here or in STATE.md.

1. **`.gitignore` swallows all source code (CRITICAL).** Line 5 is `data/` (unanchored) — it matches `research/data/`, so `git check-ignore` confirms **every source file built so far is ignored**; `git add research/` would silently skip the core package. The repo's two commits predate the code. Fix: change `data/` to `/data/` (or `/lake/`, since the lake is the actual thing to ignore — note `lake/` isn't ignored at all today). One line; needs owner's go-ahead.
2. **METRICS.md cites `bench_store.py` — the script is not in the repo.** Numbers are therefore not reproducible from the current tree. Recreate the benchmark script and commit it alongside the numbers.
3. **CIZ column names unverified.** `SRC_COLUMNS` / `COMMON_STOCK_WHERE` in `crsp_daily.py` come from CRSP documentation, not a live connection (WRDS blocked until fall). `verify_schema()` gates every pull, so failure mode is loud, but expect possible renames on first real run.
4. **Test time bomb**: `tests/test_crsp_loader.py` hardcodes `YEAR = 2026` to mean "current year" (audit's trading-day bounds skip the current year via `dt.date.today()`). In January 2027 these tests start failing — 2026 becomes a "complete past year" with 1 trading day. Fix when touched: `YEAR = dt.date.today().year`.
5. **yfinance backfill (once built) is survivorship-biased** and has no delisting returns — documented interim state, replaced wholesale by CRSP in fall. Its `market_cap` would embed look-ahead (only current shares outstanding exist); spec stores `shares_outstanding_current` and defers mcap filtering to CRSP.
6. **`AuditReport` not yet shared.** Lives in `crsp_daily.py`; part 2b's approved spec extracts it to `loaders/audit.py`. Until then, a second loader would duplicate it.
7. **No lockfile / no CI.** Deps are floor-pinned in pyproject only; suite runs locally only. Acceptable at this stage, worth adding before the codebase grows contributors.
8. **Uncommitted work.** `docs/DESIGN.md`/`docs/STATE.md` carry uncommitted modifications; `research/`, `tests/`, `pyproject.toml`, docs are untracked (partly *because of* item 1). Commit discipline starts after the gitignore fix.
9. **WRDS seasonal access** (Duke): academic year only. Discovered 2026-07-13. CRSP loader is code-complete and idles until ~late Aug 2026.

## 13. Non-obvious implementation details & pitfalls

- **Polars raises `ComputeError`, not `FileNotFoundError`, when a dataset directory doesn't exist** (`scan_parquet` on an empty glob, at `.collect()` time). Already bit us once; tests assert directory absence instead of exception type.
- **`knowledge_ts` is constant per batch file** (single `pl.lit`). This is why file-level pruning works (min=max in footer stats) and why `asof`'s sort is a cheap merge of pre-sorted runs, not a shuffle. Don't break this property by batching multiple knowledge_ts values into one file.
- **`asof` output order is unspecified.** Its internal sort serves revision-dedup only. Consumers must sort explicitly if they need order.
- **`part` values are path components** — `append` validates them (alphanumeric/`-`/`_` only) to block traversal. Keep that check if refactoring.
- **CRSP conventions**: `dlyret` (CIZ) already includes dividends *and* the delisting return on the final day — do not add a delisting merge. `shrout` is in **thousands** (market_cap multiplies by 1000). Legacy SIZ tables (`crsp.dsf`) use negative prices for bid/ask midpoints — irrelevant unless someone switches off CIZ.
- **pandas exists only at the WRDS boundary** (`raw_sql` returns pandas; `pl.from_pandas` immediately). Don't let it leak further.
- **Sandbox/hook quirk**: repo hooks require `graphify query` before raw greps/reads of source; batch tool calls accordingly or they get rejected.

## 14. Testing strategy

- **Offline always.** Vendor connections are constructor-injected; tests pass fakes returning canned pandas frames. No network, no credentials, no live-data flakiness.
- **PIT correctness is tested as behavior**, not implementation: `test_asof_point_in_time` writes a value + a revision under different knowledge_ts and asserts three vintages (before/mid/after). Any store refactor must keep that test green untouched.
- Idempotency, schema rejection, quarantine-not-store, flag-don't-drop each have a dedicated test.
- Fresh `tmp_path` store per test — no shared state.
- Run: `.venv/bin/python -m pytest` (11 passing). Narrow first during debugging (`pytest tests/test_x.py::test_y -x`), full suite as the gate.
- Gap: no property-based tests, no benchmarks in CI; live-pull integration is manual by design (credentials).

## 15. How to add things

**A new data vendor** (the common case):
1. Explain the design to the owner first (§9.1) — blocks, functions, failure handling. Wait for approval.
2. Copy the structure of `crsp_daily.py`: injected connection, `SRC_COLUMNS` mapping, `verify_schema()`, `load_<unit>()`, `_transform`, `_audit` (use shared audit module once extracted), `_quarantine`, CLI `main()`.
3. New dataset name, vendor-native `security_id`; never merge into another vendor's dataset.
4. Offline tests with a fake connection: happy path into store, idempotent re-run, quarantine path, vendor-specific quirks.
5. Update docs/SYSTEM_MAP.md + STATE.md same session; record ingest metrics in METRICS.md after the real run.

**A downstream research component** (universe, signals, risk): read inputs exclusively via `store.asof(...)` with an explicit simulation timestamp; walk-forward semantics (each simulated day sees only what was knowable) come free if you never touch `scan()`.

## 16. Roadmap & recommended next tasks

Build phasing (DESIGN.md, owner-approved order): data layer → 2–3 classic signals + IC → risk model → optimizer → backtester → Spark/Databricks port → C++ engine → analytics suite → alt-data/kdb+.

Immediate queue, in order:

1. **Fix `.gitignore` (§12.1) and make the first real commit of the source tree.** Highest value-to-effort ratio in the repo; everything else compounds on it.
2. **Build part 2b** (yfinance loader + shared `audit.py`) — spec already approved, backfill 2011→today. Unblocks everything data-dependent for the summer. Record first real METRICS.md loader numbers.
3. **Part 3: universe builder** — top ~1,000 by 60d median dollar volume, price > $5, monthly PIT snapshots stored as their own dataset (survivorship-safe membership). Needs part 2b's bars. Explain-first per protocol.
4. **Part 4: security master skeleton** — permanent internal IDs, ticker↔permno validity ranges; prerequisite for CRSP/yfinance reconciliation.
5. **Fall (WRDS returns)**: run `crsp_daily` live — `verify_schema()` first, full backfill, METRICS entry, then reconcile vs yfinance (DESIGN 1a cross-vendor checks).
6. Then phase 2 (signals + IC measurement) per DESIGN.md Block 2.

Item 4 in §12 (test year bomb) rides along with whichever task next touches the loader tests.

---

*If something here can't be verified against the tree, trust the tree and update this file. Keep it current the way STATE.md is kept current — a stale handoff is worse than none.*
