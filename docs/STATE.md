# STATE

## Goal
Build multifactor equity trading system (Grinold & Kahn framework) — learn quant-shop internals + resume piece. Currently design-capture phase.

## Now
Phase 1, part 2 code COMPLETE: CRSP daily-bars loader (research/data/loaders/crsp_daily.py), 11/11 tests pass. LIVE PULL NOT RUN — needs Ethan's one-time WRDS login (writes ~/.pgpass), then `python -m research.data.loaders.crsp_daily`. Schema verify + METRICS.md numbers happen at live pull.

## Next
1. BLOCKED until fall semester (~late Aug 2026): live CRSP pull — Duke WRDS access restricted during non-academic year (discovered 2026-07-13). Loader code done + tested, runs when access returns.
2. Interim data source decision pending (Ethan): yfinance free-stack loader vs wait for CRSP
2. Part 3: universe builder (60d median ADV, price/mcap filters, monthly PIT snapshots)
3. Part 4: security master + matching engine skeleton

## Constraints
- "You can write plans, but do not start coding yet" (2026-07-08)
- "I will tell you more stuff, do not code anything yet" (2026-07-08)
- "Everything should be written down and remembered" (2026-07-08)
- "do not code anything yet" (repeated with infra message, 2026-07-08)
- "I want you to tell me what you build specifically in small parts for each system before you do it. I want the nitty gritty details, detailing each block of code and what it does" (2026-07-09) — learning project: explain-before-build, per small part, every system
- "While building the system, please write in a Metrics.md file metrics for things like latency, storage size, speed up, throughput, and other metrics that will be featured on my resume" (2026-07-09) — docs/METRICS.md; measured numbers only, with command + date + hardware
- "I want you to build a diagram of all the systems in this project as you add them, with each file, and what the functions in the file do, with arrows and other signals so that I know what each file is for" (2026-07-13) — docs/SYSTEM_MAP.md; update in the same session as any file/function change

## Decisions
- DECISION: C++ hot path + Python research stack — real quant-shop split, strongest resume signal
- DECISION: Alpaca paper trading — live data + real order lifecycle, zero money risk
- DECISION: US equities, free data only — richest factor literature
- DECISION: Long-short dollar+sector neutral — pure alpha, what stat-arb pods run
- DECISION: Daily rebalance — max breadth on free data
- DECISION: Universe = top ~1,000 US equities by 60d median dollar volume, point-in-time membership
- DECISION: Infra = Databricks notebooks/Workflows + Spark + Delta Lake on S3; AWS EC2/ECR/S3 — Ethan's choice, industry-standard batch stack
- DECISION: Storage split = parquet+Delta data lake (research/batch) and kdb+ (live trading time-series) — cheap warehouse vs high-perf live engine
- DECISION: PIT mechanism = explicit bitemporal columns primary, Delta time travel as audit layer — Delta vacuum/retention defaults too short for 5–15y PIT (Claude suggestion, in DESIGN.md)
- DECISION: No per-name stop losses; book-level protection only (portfolio drawdown kill switch, intraday loss alerts, fat-finger bounds) — Ethan chose "what real shops have"; stops fight signals + cut realized IC (2026-07-09)
- DECISION: Beta-neutral constraint added (β·w = 0) alongside dollar/sector neutrality — dollar-neutral alone leaves market exposure; needed to measure real alpha (2026-07-09)
- DECISION: Analytics suite added (per-factor P&L, Sharpe, IC, drawdown, capacity + dashboard) — Ethan requested factor-level measurement (2026-07-09)
- DECISION: Engine event-journaled from day one (crash recovery + trade blotter); broker simulator for deterministic engine tests; shadow deployment for new models; stress/crowding monitors; financing costs + live corporate-action handling added (2026-07-09)

## Facts
- Python: system 3.10.2 at /Library/Frameworks/Python.framework/Versions/3.10/bin/python3; repo venv at .venv/ (polars 1.42.1, pytest 9.1.1); no uv installed
- Test command: .venv/bin/python -m pytest
- Approved plan file: /Users/ethan/.claude/plans/i-want-to-build-gleaming-ladybug.md
- Canonical architecture doc: docs/DESIGN.md (this repo)
- Repo fresh: one commit, no source code yet
- Memory dir: ~/.claude/projects/-Users-ethan-Documents-Duke-Year-2-Projects-multifactor-trading-system/memory/

## Done
- Six-block architecture plan approved by Ethan (2026-07-08) — RESULT: plan file saved, decisions locked (see Decisions)
- All 11 Claude design suggestions accepted + folded into docs/DESIGN.md (2026-07-08) — RESULT: DESIGN.md now has Backtester block, Ops layer, phasing local-first→distributed; open item added: free borrow-rate data source
- Phase 1 part 1 (2026-07-09) — RESULT: PITStore append/scan/asof in research/data/store.py; `.venv/bin/python -m pytest tests/test_store.py` -> "4 passed in 0.22s"; PIT correctness proven by test_asof_point_in_time
- Phase 1 part 2 code (2026-07-13) — RESULT: PITStore gained `part=` (chunked idempotent appends); CRSPDailyLoader (crsp.dsf_v2/CIZ, delisting in dlyret, scrub→audit→quarantine→PIT append) + CLI main; wrds 3.5.0 pinned; `.venv/bin/python -m pytest` -> "11 passed in 0.64s". CIZ column names UNVERIFIED until live verify_schema() run.

## Open items
- WRDS approved BUT Duke student access restricted to academic year — no access summer 2026; CRSP pulls resume fall semester (discovered 2026-07-13). CRSP stays the primary bars source; loader ready.
- HTCondor role ambiguous: Ethan says "run KDB in parallel with HTCondor for live trading model"; HTCondor is batch/HPC scheduler — likely better fit for research grid (backtest sweeps). Confirm intent at block-5 deep dive.
- Alt-data source selection deferred to alpha research phase
- Alpha combination weights (blend of alphas) deferred to alpha research engine

## Failed attempts
(none)
