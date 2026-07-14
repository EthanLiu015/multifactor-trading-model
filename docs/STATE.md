# STATE

## Goal
Build multifactor equity trading system (Grinold & Kahn framework) — learn quant-shop internals + resume piece. Currently design-capture phase.

## Now
Phase 1, part 2b BUILT (2026-07-13 session 2): shared loaders/audit.py + yfinance_daily.py loader; 20/20 tests pass. Live 1-year smoke run done (see Done). Full backfill 2011→today NOT run — Ethan's call: `.venv/bin/python -m research.data.loaders.yfinance_daily --start 2011` (add `--shares` for slow shares snapshot).

## Next
1. Ethan runs full yfinance backfill 2011→today; record rows/s + lake size in docs/METRICS.md
2. Part 3: universe builder (60d median ADV, price filter, monthly PIT snapshots) — explain-first per protocol
3. Part 4: security master + matching engine skeleton
4. BLOCKED until fall semester (~late Aug 2026): live CRSP pull — Duke WRDS seasonal access. Loader code done + tested, runs when access returns.

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
- DECISION: yfinance = interim bars vendor (dataset `yfinance_daily`, keyed by ticker, backfill 2011→today) while WRDS season-blocked; replaced wholesale by CRSP in fall; never merged with crsp_daily before security master (approved spec 2026-07-13)
- DECISION: shares outstanding stored as separate one-row-per-ticker dataset `yfinance_shares_current` (effective_date = fetch date), optional `--shares` CLI flag — embedding current snapshot in 15y of bars would forge history; mcap deferred to CRSP (Claude assumption 2026-07-13, spec detail lost with prior conversation — Ethan to confirm)
- DECISION: Engine event-journaled from day one (crash recovery + trade blotter); broker simulator for deterministic engine tests; shadow deployment for new models; stress/crowding monitors; financing costs + live corporate-action handling added (2026-07-09)

## Facts
- Python: system 3.10.2 at /Library/Frameworks/Python.framework/Versions/3.10/bin/python3; repo venv at .venv/ (polars 1.42.1, pytest 9.1.1, yfinance 1.5.1, pandas 2.2.3); no uv installed
- Test command: .venv/bin/python -m pytest (20 passing)
- Framework Python has no CA bundle: urllib needs ssl context with certifi.where() (fixed in yfinance_daily.fetch_listed_tickers)
- Approved plan file: /Users/ethan/.claude/plans/i-want-to-build-gleaming-ladybug.md
- Canonical architecture doc: docs/DESIGN.md (this repo)
- Gitignore bug fixed 2026-07-13 (commit a5aca9a): unanchored `data/` was hiding research/data/ from git — Ethan's commit 1ce8420 omitted store.py + crsp_daily.py despite naming them; now tracked, `/lake/` + `/data/` ignored
- Memory dir: ~/.claude/projects/-Users-ethan-Documents-Duke-Year-2-Projects-multifactor-trading-system/memory/

## Done
- Six-block architecture plan approved by Ethan (2026-07-08) — RESULT: plan file saved, decisions locked (see Decisions)
- All 11 Claude design suggestions accepted + folded into docs/DESIGN.md (2026-07-08) — RESULT: DESIGN.md now has Backtester block, Ops layer, phasing local-first→distributed; open item added: free borrow-rate data source
- Phase 1 part 1 (2026-07-09) — RESULT: PITStore append/scan/asof in research/data/store.py; `.venv/bin/python -m pytest tests/test_store.py` -> "4 passed in 0.22s"; PIT correctness proven by test_asof_point_in_time
- Phase 1 part 2 code (2026-07-13) — RESULT: PITStore gained `part=` (chunked idempotent appends); CRSPDailyLoader (crsp.dsf_v2/CIZ, delisting in dlyret, scrub→audit→quarantine→PIT append) + CLI main; wrds 3.5.0 pinned; `.venv/bin/python -m pytest` -> "11 passed in 0.64s". CIZ column names UNVERIFIED until live verify_schema() run.
- Gitignore fix + first real source commit (2026-07-13 session 2) — RESULT: commit a5aca9a tracks research/data/ (4 files); unanchored `data/` had hidden them from Ethan's commit 1ce8420
- Part 2b: shared audit.py + yfinance loader (2026-07-13 session 2) — RESULT: AuditReport/audit_daily_bars extracted (crsp_daily now thin wrapper); YFinanceDailyLoader (chunked download, grid-artifact scrub, ret from Adj Close, fetch-failure flagging, shares snapshot dataset, NASDAQ symbol-file universe fetch, CLI); yfinance 1.5 pinned; `.venv/bin/python -m pytest` -> "20 passed"; crsp test YEAR-2026 time bomb defused (dt.date.today().year); SSL cert bug in symbol-file fetch fixed (certifi context)
- Live smoke: 1-year yfinance pull to scratchpad lake (2026-07-13 session 2) — RESULT: `python -m research.data.loaders.yfinance_daily --start 2024 --end 2024` -> 253,505 rows / 252 days / 69.8s, exit 0; pipeline verified end-to-end BUT Yahoo rate-limited 6,056/7,093 tickers (fetch_failures flagged, audit ok)

## Open items
- Yahoo rate limits block bulk backfill: smoke pull got only ~1,000/7,093 tickers (YFRateLimitError per chunk; yfinance fetches per-ticker, so 7k tickers × 15y ≈ 100k+ requests). Mitigation options to decide with Ethan: paced multi-hour run with retry/backoff, requests-cache session, smaller curated universe first, or accept partial + re-run top-ups (idempotent by knowledge_ts design)
- Ethan to confirm shares-outstanding-as-separate-dataset assumption (see Decisions 2026-07-13)
- WRDS approved BUT Duke student access restricted to academic year — no access summer 2026; CRSP pulls resume fall semester (discovered 2026-07-13). CRSP stays the primary bars source; loader ready.
- HTCondor role ambiguous: Ethan says "run KDB in parallel with HTCondor for live trading model"; HTCondor is batch/HPC scheduler — likely better fit for research grid (backtest sweeps). Confirm intent at block-5 deep dive.
- Alt-data source selection deferred to alpha research phase
- Alpha combination weights (blend of alphas) deferred to alpha research engine

## Failed attempts
(none)
