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
| Portfolio style | Long-short, dollar-neutral + sector-neutral (pure alpha, no market exposure) |
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

**Cost reality (free-budget flag)**
- Databricks Free Edition: serverless, limited compute — enough to demo notebooks + workflows; full workspaces are paid.
- kdb+ Personal Edition: free for non-commercial use (registration required).
- AWS free tier: 12 months of limited EC2/S3; small monthly cost likely once data history grows.

## Block 3: Risk Model (parallel to alpha)

- Same factor structure as the alpha side: stock return = Σ (exposure × factor return) + specific return.
- **Factor covariance, not stock covariance**: Σ = B·F·Bᵀ + D where B = N×K exposure matrix, F = K×K factor covariance, D = diagonal specific variance. With N=1,000 stocks and K≈20 factors: estimate ~210 factor covariances instead of ~500,000 stock covariances — this is what makes trading thousands of names tractable.
- **Systematic vs specific risk kept separate**: systematic = factor exposures (mostly hedged out by neutrality constraints), specific = idiosyncratic (diversified across names; where the alpha actually lives in a neutral book).
- Factor set: market, sectors (GICS-ish), style factors (value, momentum, size, vol, quality) — Barra-style.
- **Time scaling**: variance grows linearly with horizon; risk (σ) grows with √t. Annualize as σ_annual = σ_daily × √252. All risk numbers reported at a consistent horizon.

## Block 4: Portfolio Construction (Optimizer)

- Objective: maximize `αᵀw − λ·wᵀΣw − TC(w − w_prev)` — expected return minus risk penalty minus trading cost.
- Constraints: dollar-neutral (Σw = 0), sector-neutral (sector exposures = 0), position limits per name, turnover cap, gross/net leverage limits, factor exposure bounds.
- Output: **target holdings** — how much of each name to hold. Handed to the C++ layer.
- Tooling (research side): cvxpy or OSQP for the convex QP. Runs once daily; latency non-critical here.

## Block 5: Implementation + Trading System (C++ hot path)

- Goal: **subtract as little value as possible** between target portfolio and real portfolio.
- Cost components to model and measure: commission, per-share broker fees, bid-ask spread (half-spread per crossing), **market impact** (square-root impact model as starting point), **opportunity cost** (alpha decay while waiting to fill), timing/delay cost.
- **Implementation shortfall measurement**: run a zero-cost hypothetical paper portfolio in parallel with the real (Alpaca paper) portfolio; the difference = total implementation cost, decomposed into the components above.
- C++ components (low-latency discipline throughout): market data handler (Alpaca websocket → internal book), order gateway (order state machine: new/ack/fill/cancel/reject), position keeper, pre-trade risk checks (fat-finger, position limits, buying power), execution scheduler (works the daily target list — slice orders, limit vs market decisions).
- Latency engineering as resume story: lock-free SPSC queues between threads, pinned threads, pre-allocated memory (no malloc on hot path), nanosecond timestamping at each hop, internal tick-to-order latency histograms. Free data means the *feed* isn't fast, but the *system* is measured and engineered like a fast one.

## Block 6: Performance Analysis

- Attribution: how much P&L came from intended factor bets vs constraints/noise vs specific returns. Decompose realized returns through the risk model (B·f + specific).
- Skill vs luck: IC time series per signal, t-stats, rolling IRs; distinguish statistically real edge from noise.
- **Feedback loop → Block 1**: edges decay; attribution tells us which signals are dying (IC decay) and which are working, feeding signal retirement/re-weighting decisions.

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

1. Data layer + universe construction (point-in-time store, security master) — everything depends on it
2. 2–3 classic signals + IC measurement (proves the research loop)
3. Risk model (factor exposures, F, D)
4. Optimizer (cvxpy QP with all constraints)
5. Backtester with cost model (validates 1–4 before any live loop)
6. C++ engine + Alpaca paper integration
7. Attribution + shortfall measurement + feedback loop
8. Exotic/alt-data signals + alpha research engine refinements

## Open items

- HTCondor role: confirm research-grid vs live-loop at block-5 deep dive.
- Alt-data source selection: decided during alpha research.
- Alpha combination weights: alpha research engine topic.
- Deep dives pending for blocks 3–6.
