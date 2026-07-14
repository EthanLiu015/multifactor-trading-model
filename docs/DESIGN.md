# Multifactor Trading System — Design

> Canonical architecture document. Follows the Grinold & Kahn active-management framework, laid out block-by-block by Ethan with Claude suggestions marked where accepted. Status: **design-capture phase — no code yet.** Each block gets a deeper dive before implementation.

## Purpose

Build a multifactor equity trading system that replicates what a quant firm's internal trading system looks like, end to end, to (a) learn how such a system works and (b) serve as a strong resume/recruiting artifact. Low-latency engineering discipline throughout, like a real quant stack.

## Locked decisions

| Decision | Choice |
|---|---|
| Stack | C++ hot path (execution/trading system) + Python research stack (signals, alpha, risk, optimizer) |
| Execution target | Paper trading via Alpaca API (live websocket data, real order lifecycle, zero money risk) |
| Asset class | US equities |
| Data budget | Free only (Alpaca free tier, yfinance, SEC EDGAR, etc.) |
| Portfolio style | Long-short: dollar-neutral + **beta-neutral** + sector-neutral (pure alpha, no market exposure) |
| Rebalance cadence | Daily — signals + optimizer after close, C++ layer works orders next session |
| Batch infra | Databricks notebooks/Workflows + Apache Spark + Delta Lake; AWS S3/EC2/ECR |
| Storage split | Parquet+Delta data lake on S3 (research/batch) · kdb+ (live trading time-series) |

## System overview

```
┌─────────────────┐
│ 1. Data+Signals │◄─────────────────────────────┐
└───────┬─────────┘                              │
        │                                        │ feedback loop
        ▼                                        │ (edges decay)
┌─────────────────┐    ┌──────────────┐          │
│ 2. Alpha        │    │ 3. Risk model│          │
│    Forecast     │    │ (parallel)   │          │
└───────┬─────────┘    └──────┬───────┘          │
        │                     │                  │
        ▼                     ▼                  │
┌─────────────────────────────────┐              │
│ 4. Portfolio construction       │              │
│    (optimizer)                  │              │
└───────┬─────────────────────────┘              │
        │  target holdings                       │
        ▼                                        │
┌─────────────────────────────────┐              │
│ 5. Implementation + trading     │  ← C++ hot path
│    (subtract as little value    │              │
│     as possible)                │              │
└───────┬─────────────────────────┘              │
        │  fills, costs                          │
        ▼                                        │
┌─────────────────────────────────┐              │
│ 6. Performance analysis         │──────────────┘
│    (skill vs luck, attribution) │
└─────────────────────────────────┘

Ties everything together: IR = IC × √breadth (fundamental law of active management)
```

## Block 1: Data + Signals

- **Traditional data**: prices/volumes (Alpaca, yfinance), fundamentals (SEC EDGAR XBRL — free, point-in-time by filing date), corporate actions.
- **Alternative data** (exotic signals): free sources — EDGAR filing text/sentiment, insider transactions (Form 4), Google Trends, Reddit/news sentiment, short interest (FINRA), earnings call transcripts. Exact set chosen later, during alpha research.
- **Signals**: each signal = one measurable view on a stock. Classic factors (value, momentum, quality, low-vol, size, reversal) + exotic ones from alt data.
- **Universe**: top ~1,000 US equities by 60-day median dollar volume; filters: price > $5, market cap > $2B (roughly Russell-1000-like); rebuilt monthly; **point-in-time membership** to kill survivorship bias. Universe snapshots stored so backtests only see stocks that were in the universe on that date. ~1,000 names gives breadth for the fundamental law while staying tractable on free data.
- Key discipline: every signal stored with the timestamp of *when it was knowable* (filing date, not period date) — look-ahead bias is the #1 killer of fake backtests.
- **Delisting returns**: return data must include delisted stocks' final returns (bankruptcy = −100%; acquisition = deal price). PIT membership alone doesn't fix survivorship — it also hides in the returns themselves, and matters most for the short book.

### Block 1 mini-systems (per-vendor pipeline; every data source, especially each alternative dataset, passes through all of these)

**1a. Data scrubbing + vendor reconciliation**
- Outlier detection with cross-checks against a second source (a price spike in vendor A validated against vendor B before acceptance; unconfirmed outliers flagged, not silently dropped).
- Gap filling with explicit policy per field type (forward-fill prices vs. NaN-preserve fundamentals); every filled value marked as imputed.
- Format normalization: currencies, units (thousands vs. millions in filings), date conventions, split/dividend adjustment consistency.
- Vendor reconciliation: vendors describe the same company differently — reconcile across SEDOL, CUSIP, ISIN, ticker, FIGI into one internal view per security so all downstream data is consistent.

**1b. Security master + security matching engine**
- Internal **security master**: one permanent internal security ID per instrument, mapped to all external identifiers (CUSIP, SEDOL, ISIN, ticker, FIGI, exchange codes) with validity date ranges.
- **Security matching engine** for alternative data: alt-data identifiers (company names, domains, brands, ad-hoc vendor IDs) matched to the standardized industry identifiers in the security master.
- **Point-in-time matching** is the key concept: tickers get reused, companies rename, merge, and re-CUSIP — a match is only valid over a date range, and the engine must resolve an identifier *as of the observation date*, never with today's mapping (look-ahead bias otherwise).
- Match quality tiers (exact ID > exact name > fuzzy name) with confidence scores; low-confidence matches quarantined for review rather than silently ingested.

**1c. Processing layer**
- Alt datasets can be huge — columnar, vectorized processing: **Polars** as the default local engine, NumPy for numeric kernels, **Spark** for datasets beyond single-machine scale (see Infrastructure layer). Pipeline API stays engine-agnostic so work moves between Polars and Spark cleanly.
- Transformations expressed as lazy pipelines (Polars LazyFrame / Spark plans) so full-history rebuilds stay fast.

**1d. Data loader (per vendor)**
- Scheduled pull from each vendor at its natural cadence (daily/weekly/monthly per source), then transform + aggregate (preprocessing), then write to the internal database.
- **Data auditing flag**: each load runs audit checks — row counts vs. expectations, schema drift, stale data (vendor re-sent old file), distribution shift vs. history, coverage vs. universe — and flags discrepancies in upstream vendor data instead of silently ingesting. Failed audits quarantine the batch; loads are idempotent (re-runnable without duplication).
- Every batch stamped with load timestamp + vendor file version → bitemporal store (what we knew, and when we knew it), which is what makes point-in-time queries possible downstream.
- Vendor-specific adapters differ per source, but every source must satisfy the same contract: **scrub → match → audit → point-in-time store**. New alt-data sources onboard by implementing this contract.

## Block 2: Alpha Forecast

- Grinold's rule of thumb: **α = σ × IC × z** — volatility × genuine predictive skill (information coefficient) × how strongly the signal is firing for that specific stock (z-score).
- Multifactor = many alphas running at once, each an independent, calculable edge. Combination weights (how to blend alphas) = later research topic via the alpha research engine.
- Alpha research engine (later): IC measurement per signal (rank correlation of signal vs forward returns), IC decay curves, signal orthogonalization (correlated signals ≠ independent bets — effective breadth shrinks).
- **Alpha ⊥ risk factors (orthogonality rule)**: alpha must forecast *residual* return. Any alpha component aligned with a risk-model factor gets hedged out by the optimizer — you pay the risk penalty on the very bet you wanted. Orthogonalize each alpha against the risk factors (regress out, keep residual), or deliberately exclude a factor from one side and document it.
- **Backtest-overfitting defense**: hold out the final 2–3 years of history, untouched until the design is frozen. Signal registry: write the hypothesis *before* testing it; track the number of hypotheses tested per signal family (deflated-Sharpe logic — 100 tries makes one lucky Sharpe inevitable).
- **Research meets production here.** Research methodologies defined and built out later; production-ready live-model code is optimized for speed via distributed computing (Spark) and NumPy vectorization — no Python loops over stocks or dates.
- Production alpha pipeline runs over **5–15 years of historical data** (historical forecasts) across the point-in-time universe.

## Infrastructure layer (serves Data+Signals, Alpha Forecast, and historical forecast runs)

**Compute + orchestration**
- **Databricks notebooks** for research; **Databricks Workflows** trigger scheduled runs (data loaders at each vendor's cadence, signal + alpha recompute daily after close).
- **Apache Spark** for distributed batch. Job anatomy: the **driver** holds the program and builds the execution plan; it feeds **executors**, which work partitions of the dataset simultaneously.
- Canonical job flow: partitioned parquet files in S3 → Spark reads them and spreads partitions across executors → for security matching, the security master is **broadcast** to every executor so the join happens locally with **no shuffle** → output partitioned by date → written to Delta Lake, ready for the trading factors to consume.
- Production alpha code inside Spark tasks: vectorized NumPy kernels (Arrow/pandas UDFs or mapInPandas) so per-partition work runs at C speed.
- **AWS services**: S3 (data lake), EC2 (compute hosts — kdb+ instance, C++ engine, self-managed Spark if needed), ECR (Docker images for jobs and the engine).

**Storage — two tiers**
- **Parquet data lake on S3 + Delta Lake**: Delta transaction logs give ACID guarantees; data partitioned by date for cheap daily appends. The cheap, massive warehouse for research and batch.
- Delta keeps a transaction log of every change → versioning supports the point-in-time requirement in security matching. Caveat (accepted into design): Delta time-travel retention (log + vacuum) defaults to ~30 days — for 5–15y PIT correctness the **primary** mechanism is explicit bitemporal columns (effective_date + knowledge_date) in the tables themselves; Delta versioning is the reproducibility/audit layer on top.
- **kdb+ (q)**: live trading + high-performance time-series engine — real-time ticks, live positions, intraday analytics. Runs in parallel with HTCondor.
- HTCondor note (open item): HTCondor is a batch/HPC scheduler — natural fit is the research compute grid (backtest parameter sweeps, historical alpha runs) rather than inside the live low-latency loop; live loop stays C++ + kdb+ on a dedicated EC2 box. Confirm intent at block-5 deep dive.

**Phasing rule: local-first, distribute second**
- ~1,000 names × 15y daily ≈ a few GB — fits comfortably in Polars on a laptop. The distributed stack is justified as learning + resume showcase, not by data size, so it must never gate alpha work.
- Order: build the vertical slice locally first (Polars + parquet on disk), prove the pipeline, then port loaders + historical alpha runs to Spark/Databricks/Delta-on-S3 as the showcase layer. The engine-agnostic pipeline API is what makes the port cheap.

**Cost reality (free-budget flag)**
- Databricks Free Edition: serverless, limited compute — enough to demo notebooks + workflows; full workspaces are paid.
- kdb+ Personal Edition: free for non-commercial use (registration required).
- AWS free tier: 12 months of limited EC2/S3; small monthly cost likely once data history grows.

## Block 3: Risk Model (parallel to alpha)

- Same factor structure as the alpha side: stock return = Σ (exposure × factor return) + specific return.
- **Factor covariance, not stock covariance**: Σ = B·F·Bᵀ + D where B = N×K exposure matrix, F = K×K factor covariance, D = diagonal specific variance. With N=1,000 stocks and K≈20 factors: estimate ~210 factor covariances instead of ~500,000 stock covariances — this is what makes trading thousands of names tractable.
- **Systematic vs specific risk kept separate**: systematic = factor exposures (mostly hedged out by neutrality constraints), specific = idiosyncratic (diversified across names; where the alpha actually lives in a neutral book).
- Factor set: market, sectors (GICS-ish), style factors (value, momentum, size, vol, quality) — Barra-style.
- **Estimation**: daily cross-sectional regression of returns on exposures B gives factor returns f_t; regression residuals give specific returns → specific variance D. Factor covariance F: exponentially-weighted (recent data counts more), **Ledoit-Wolf shrinkage** (K×K sample covariance is noisy), **Newey-West adjustment** for autocorrelation in factor returns.
- **Time scaling**: variance grows linearly with horizon; risk (σ) grows with √t. Annualize as σ_annual = σ_daily × √252. All risk numbers reported at a consistent horizon.
- **Stress testing / scenario analysis** (daily report): shock the current book against historical scenarios — Aug 2007 quant quake (crowded factor unwind, the canonical multifactor disaster), 2008, Mar 2020 — plus synthetic factor shocks (e.g., momentum −5σ). Expected loss per scenario published daily.
- **Crowding monitoring**: our factors are everyone's factors; crowded-factor unwinds are the multifactor tail risk. Proxies tracked: factor valuation spreads, pairwise correlation of top factor-exposed names, short-interest concentration in the short book.

## Block 4: Portfolio Construction (Optimizer)

- Objective: maximize `αᵀw − λ·wᵀΣw − TC(w − w_prev)` — expected return minus risk penalty minus trading cost.
- Constraints: dollar-neutral (Σw = 0), **beta-neutral (β·w = 0, predicted betas from the risk model)** — dollar-neutral alone is not market-neutral: high-beta longs vs low-beta shorts leaves net market exposure; beta neutrality is what makes measured returns real alpha — sector-neutral (sector exposures = 0), position limits per name, turnover cap, gross/net leverage limits, factor exposure bounds, **short-side borrow availability filter** (exclude hard-to-borrow names or cap their weight).
- **Position limits liquidity-relative**: cap per-name weight as % of ADV (e.g., position ≤ x days of median dollar volume), not just a fixed % of book — a fixed cap that's fine for AAPL is untradeable in name #997.
- **The optimizer is an error maximizer**: it loads up hardest on the names whose alphas are most overestimated. Defenses: shrink alphas toward zero before optimizing, cap per-name alpha magnitude, and treat optimizer output as suspect wherever a single name dominates the trade list.
- Output: **target holdings** — how much of each name to hold. Handed to the C++ layer.
- Tooling (research side): cvxpy or OSQP for the convex QP. Runs once daily; latency non-critical here.

## Backtester (validates Blocks 1–4 before any live loop)

- **Event-driven simulator replaying the full pipeline** — signals → alpha → optimizer → cost model → simulated fills — over point-in-time data, walk-forward (each simulated day sees only what was knowable that day). Distinct from historical alpha runs (which score signals in isolation); this tests the *system*.
- Cost model inside the simulator mirrors Block 5's: spread, impact (square-root), fees, borrow costs — so backtest P&L and paper-trading P&L are directly comparable.
- Walk-forward everywhere: risk model, alpha weights, and universe are all re-estimated using only trailing data at each step. No in-sample leakage.
- Output feeds Block 6 attribution identically to live data — same attribution code runs on backtest and paper portfolios.
- Held-out final 2–3 years (per Block 2's overfitting defense) only touched once, when design is frozen.

## Block 5: Implementation + Trading System (C++ hot path)

- Goal: **subtract as little value as possible** between target portfolio and real portfolio.
- Cost components to model and measure: commission, per-share broker fees, bid-ask spread (half-spread per crossing), **market impact** (square-root impact model as starting point), **opportunity cost** (alpha decay while waiting to fill), timing/delay cost, **short borrow costs** (stock-loan fees on the short book; hard-to-borrow names can eat an entire alpha — Alpaca paper won't model this, so the cost model must, fed by borrow-rate data where obtainable), **financing costs** (margin financing paid on longs, short rebate minus borrow fee received on shorts — the leverage cost line, separate from per-trade costs).
- **Execution urgency driven by alpha decay**: Block 2's IC decay curves set order aggressiveness — fast-decaying signal → cross the spread / aggressive slices; slow signal → patient limit orders. Direct pipe from research into the execution scheduler.
- **Implementation shortfall measurement**: run a zero-cost hypothetical paper portfolio in parallel with the real (Alpaca paper) portfolio; the difference = total implementation cost, decomposed into the components above.
- C++ components (low-latency discipline throughout): market data handler (Alpaca websocket → internal book), order gateway (order state machine: new/ack/fill/cancel/reject), position keeper, pre-trade risk checks (fat-finger, position limits, buying power), execution scheduler (works the daily target list — slice orders, limit vs market decisions).
- Latency engineering as resume story: lock-free SPSC queues between threads, pinned threads, pre-allocated memory (no malloc on hot path), nanosecond timestamping at each hop, internal tick-to-order latency histograms. Free data means the *feed* isn't fast, but the *system* is measured and engineered like a fast one.
- **Crash recovery via event journaling**: every order event (new/ack/fill/cancel/reject) appended to a durable journal *before* the engine acts on it; on restart, replay reconstructs positions + working orders exactly. Event-sourced from day one — near-impossible to retrofit. The journal doubles as the **trade blotter**: immutable, append-only, queryable audit trail of every order, amend, cancel, fill.
- **Broker simulator**: mock Alpaca API implementing the same interface as the live gateway — inject fills, partial fills, rejects, disconnects, out-of-order messages. Deterministic testing of the order state machine without a live market; every engine test runs against it in CI.
- **Corporate actions on live positions**: position keeper applies overnight CAs before the open — split: shares ×n, price ÷n, open orders cancelled/re-priced; symbol change: remap positions + working orders; dividend: cash adjustment (shorts pay dividends). Same CA feed as Block 1, second consumer.

## Block 6: Performance Analysis

- Attribution: how much P&L came from intended factor bets vs constraints/noise vs specific returns. Decompose realized returns through the risk model (B·f + specific).
- Skill vs luck: IC time series per signal, t-stats, rolling IRs; distinguish statistically real edge from noise.
- **Realized transfer coefficient**, tracked daily: corr(target portfolio from optimizer, portfolio actually held). Measures how much IR leaks through constraints + costs + partial fills. IR_realized ≈ TC × IC × √breadth.
- **Feedback loop → Block 1**: edges decay; attribution tells us which signals are dying (IC decay) and which are working, feeding signal retirement/re-weighting decisions.

## Analytics suite (per-factor scoreboard)

Measures each factor and the whole book. Distinct from Block 6 attribution (attribution explains *why*; the suite is the live scoreboard).

- **P&L system (books and records)**: real-time marked-to-market P&L — realized + unrealized — sliced per name, sector, factor, and total book. Official end-of-day P&L reconciles against broker records (any break → ops alert).
- **Per-factor metrics**, computed on each factor's paper portfolio and on its contribution to the live book: P&L series, **Sharpe ratio**, information ratio, IC time series + t-stats, max drawdown, turnover, hit rate, realized vs predicted volatility.
- **Book-level metrics**: Sharpe, IR vs zero-cost paper book (implementation shortfall), realized transfer coefficient, gross/net exposure, realized beta (should sit ~0 — the beta-neutrality check), factor exposures vs limits.
- **Capacity analysis**: per factor and whole book — at what AUM does modeled impact eat the alpha? Re-run quarterly; the number recruiters ask for.
- **Monitoring dashboard** (Grafana-style, reads the suite + engine telemetry): live exposures, P&L, latency histograms, feed health, loader audit status, working orders. The screen the "trading floor" stares at.
- Same metric code runs on backtest output and live data — one implementation, two feeds.

## Ops layer (cross-cutting, live system)

- **No per-name stop losses** (decision): risk control is upstream — risk model sizes positions, optimizer caps names, daily re-optimization trims losers. Per-name stops would fight the signals (sell mean-reversion names at the worst point) and cut realized IC. Book-level protection instead:
  - **Portfolio-level drawdown limit**: kill switch fires automatically at −X% book drawdown (X set at block-5 implementation).
  - **Per-name intraday loss alerts**: alert, human decides — never auto-liquidate a single name.
  - **Fat-finger price bounds** on every outgoing order (reject orders priced far off last trade).
- **Kill switch**: one command/flag halts all order flow immediately; engine refuses new orders until manually re-armed. Fired manually or by the drawdown limit above.
- **Daily reconciliation**: positions + cash vs broker (Alpaca) records every day; any break halts trading until explained.
- **Alerting**: feed drops, data-loader audit failures, order rejects, position-limit breaches, latency-histogram anomalies.
- **Pre-trade compliance checks** in the C++ gateway (beyond fat-finger/risk): restricted-list, max order size, duplicate-order suppression.
- **Model governance / shadow deployment**: a new alpha or model version runs in shadow — signals computed, target portfolio built, orders NOT sent — alongside production for weeks; capital allocated only after shadow results confirm. Models versioned; one-command rollback to the previous version.
- Real shops run whole ops desks; here one module — but it exists from day one of the live loop, not bolted on after the first incident.

## Cross-cutting: Fundamental Law of Active Management

- **IR = IC × √breadth**, breadth = number of *independent* bets per year.
- Design consequence everywhere: more names in universe ↑ breadth, daily cadence ↑ breadth, but correlated signals and slow-moving signals reduce *effective* independence. The alpha research engine must measure effective breadth, not naive count.
- IR is the top-level system KPI; every block's job stated in IR terms — signals: raise IC; universe/cadence: raise breadth; optimizer + execution: keep the transfer coefficient high (don't leak IR through constraints and costs).

## Repo layout (when coding starts)

```
research/          # Python: signals, alpha, risk model, optimizer, backtest
  data/            # ingestion + point-in-time store, loaders, security master
  signals/
  alpha/
  risk/
  portfolio/
  attribution/
engine/            # C++: feed handler, order gateway, position keeper, risk checks
common/            # shared schemas: target portfolio file/IPC format, symbol master
infra/             # Databricks workflows, Docker/ECR, AWS provisioning
docs/              # DESIGN.md (this doc), per-block deep dives
```

## Build phasing (each block detailed by Ethan before its implementation)

1. Data layer + universe construction (point-in-time store, security master, delisting returns) — **local Polars + parquet first**; everything depends on it
2. 2–3 classic signals + IC measurement (proves the research loop)
3. Risk model (factor exposures, F, D, shrinkage estimation)
4. Optimizer (cvxpy QP with all constraints, alpha shrinkage)
5. Backtester with cost model — event-driven, walk-forward (validates 1–4 before any live loop)
6. Port data loaders + historical alpha runs to Spark/Databricks/Delta-on-S3 (infra showcase layer)
7. C++ engine (event-journaled from day one) + broker simulator + Alpaca paper integration + ops layer (kill switch, reconciliation, alerts)
8. Analytics suite (P&L system, per-factor Sharpe/IC/drawdown, dashboard) + attribution + shortfall + realized transfer coefficient + feedback loop
9. Exotic/alt-data signals + alpha research engine refinements; kdb+ live tick store; stress/crowding monitors

## Open items

- HTCondor role: confirm research-grid vs live-loop before block-5 implementation.
- Alt-data source selection: decided during alpha research.
- Alpha combination weights: alpha research engine topic.
- Borrow-rate data source (free) for short-cost model: to find.
