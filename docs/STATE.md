# STATE

## Goal
Build multifactor equity trading system (Grinold & Kahn framework) — learn quant-shop internals + resume piece. Currently design-capture phase.

## Now
Integrating infrastructure layer (Databricks/Spark/Delta/S3/KDB) + alpha production notes into plan and docs/DESIGN.md.

## Next
1. Await Ethan's deep dives on remaining blocks (risk model, optimizer, trading system, performance analysis)
2. Only after all block dives: begin implementation per build phasing in docs/DESIGN.md

## Constraints
- "You can write plans, but do not start coding yet" (2026-07-08)
- "I will tell you more stuff, do not code anything yet" (2026-07-08)
- "Everything should be written down and remembered" (2026-07-08)
- "do not code anything yet" (repeated with infra message, 2026-07-08)

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

## Facts
- Approved plan file: /Users/ethan/.claude/plans/i-want-to-build-gleaming-ladybug.md
- Canonical architecture doc: docs/DESIGN.md (this repo)
- Repo fresh: one commit, no source code yet
- Memory dir: ~/.claude/projects/-Users-ethan-Documents-Duke-Year-2-Projects-multifactor-trading-system/memory/

## Done
- Six-block architecture plan approved by Ethan (2026-07-08) — RESULT: plan file saved, decisions locked (see Decisions)

## Open items
- HTCondor role ambiguous: Ethan says "run KDB in parallel with HTCondor for live trading model"; HTCondor is batch/HPC scheduler — likely better fit for research grid (backtest sweeps). Confirm intent at block-5 deep dive.
- Alt-data source selection deferred to alpha research phase
- Alpha combination weights (blend of alphas) deferred to alpha research engine

## Failed attempts
(none)
