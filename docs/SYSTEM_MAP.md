# System Map

> Living diagram of every system, file, and function in the repo. **Update rule: every time a file is added, removed, or gains/loses a public function, this map is updated in the same session.** Requested by Ethan 2026-07-13.

Legend:
- **solid box / bold** — built + tested
- *dashed box / italic* — approved spec, not yet built
- `dotted / plain` — designed in DESIGN.md, not yet specced

## Data layer (Phase 1 — current)

```mermaid
flowchart LR
    subgraph VENDORS["external vendors"]
        WRDS[("WRDS / CRSP<br/>crsp.dsf_v2<br/>(blocked til fall)")]
        YF[("yfinance API")]
        ND[("NASDAQ trader<br/>symbol files")]
    end

    subgraph LOADERS["research/data/loaders/ — vendor adapters (scrub → audit → PIT append)"]
        CRSP["<b>crsp_daily.py</b><br/>CRSPDailyLoader"]
        YFL["<b>yfinance_daily.py</b><br/>YFinanceDailyLoader"]
        AUD["<b>audit.py</b><br/>AuditReport + audit_daily_bars"]
    end

    subgraph STORE["research/data/"]
        PIT["<b>store.py</b><br/>PITStore<br/>append / scan / asof"]
    end

    subgraph DISK["on disk"]
        LAKE[("lake/&lt;dataset&gt;/<br/>k=&lt;knowledge_ts&gt;_part=&lt;year&gt;.parquet")]
        QUAR[("lake/_quarantine/<br/>failed-audit batches")]
    end

    subgraph UNIVERSE["research/"]
        UNIV["<b>universe.py</b><br/>build_universe<br/>monthly PIT snapshots"]
    end

    subgraph SECMASTER["research/"]
        SECM["<b>security_master.py</b><br/>(block 1: schema only)"]
    end

    subgraph NEXT["downstream (planned)"]
        SIG["signals + IC<br/>(phase 2)"]
        BT["backtester"]
    end

    WRDS -- "raw_sql (pandas)" --> CRSP
    YF -- "chunked yf.download" --> YFL
    ND -- "fetch_listed_tickers()" --> YFL
    CRSP -- "audit pass:<br/>append(df, knowledge_ts, part)" --> PIT
    YFL -- same contract --> PIT
    CRSP -- "audit fail" --> QUAR
    YFL -- "audit fail" --> QUAR
    CRSP -- uses --> AUD
    YFL -- uses --> AUD
    PIT -- "write_parquet" --> LAKE
    LAKE -- "scan_parquet (lazy)" --> PIT
    PIT == "asof(dataset, T, keys)<br/>PIT panel, no look-ahead" ==> UNIV
    UNIV == "append(universe_monthly,<br/>part=year)" ==> PIT
    PIT ==> SIG
    UNIV -.-> BT
    SECM -. "ticker ↔ permno<br/>(block 2, not built)" .-> LOADERS
```

Data flows left → right: vendor → loader (scrub/audit) → PITStore → parquet lake. Research reads flow back out **only** through `asof()` — that single exit is what makes look-ahead bias structurally impossible.

## C++ engine (Block 5 — broker simulator skeleton, started 2026-07-16)

```mermaid
flowchart LR
    subgraph GW["engine/include/broker/ — shared interface"]
        IBG["<b>IBrokerGateway.hpp</b><br/>submit_order / cancel_order / poll_events"]
        OE["<b>OrderEvent.hpp</b><br/>OrderId, EventType, Order"]
    end

    subgraph SIM["engine/src/broker/ — test double"]
        BS["<b>BrokerSimulator.hpp/.cpp</b><br/>implements IBrokerGateway<br/>inject_ack/fill/reject/cancel_ack"]
    end

    subgraph JNL["engine/src/journal/"]
        EJ["<b>EventJournal.hpp/.cpp</b><br/>append-only CSV event log"]
    end

    subgraph LIVE["not yet built"]
        AG["AlpacaGateway<br/>(live, Block 5, later)"]
    end

    subgraph TESTS["engine/tests/"]
        T["test_broker_simulator.cpp<br/>6 Catch2 scenarios"]
    end

    IBG -.-> AG
    IBG ==> BS
    BS -- "enqueue(event)" --> EJ
    T ==> BS
    OE -.-> IBG
    OE -.-> BS
```

Order gateway state machine, position keeper, pre-trade risk checks, and market data handler (the rest of Block 5) are separate, not yet scoped. Building this jumped ahead of DESIGN.md's build-phasing order (C++ engine is step 7, after signals/risk/optimizer/backtester) as a deliberate design/scope exercise — the phasing order for the *remaining* build queue is unchanged.

**How a test actually drives it** (e.g. `test_broker_simulator.cpp`'s "submit then ack" case):

```mermaid
sequenceDiagram
    participant Test as test_broker_simulator.cpp
    participant Sim as BrokerSimulator
    participant Orders as orders_ (map)
    participant Queue as pending_events_ (deque)
    participant Journal as EventJournal (nullptr in this test)

    Test->>Sim: submit_order(Order{"AAPL",100,...})
    Sim->>Orders: orders_[1] = {order, status=New, qty_remaining=100}
    Sim-->>Test: return id=1

    Test->>Sim: inject_ack(1)
    Sim->>Orders: status = Acked
    Sim->>Sim: make_event(1, Ack, 0.0, 0.0)
    Sim->>Journal: append(event) — skipped, journal_ == nullptr
    Sim->>Queue: push_back(event)

    Test->>Sim: poll_events()
    Sim->>Queue: copy all events out, then clear()
    Sim-->>Test: return [Ack event, id=1]

    Test->>Test: REQUIRE(events.size()==1 && events[0].type==Ack)
```

Key thing this shows: `submit_order` never touches the queue — nothing "happens" until a test calls `inject_*`. And `enqueue()` always tries the journal *before* the queue, so a crash between "event journaled" and "caller saw it via poll_events()" is exactly the gap crash-recovery replay is built to close (not yet implemented — journal here is just an append-only CSV write).

## Signals + alpha (Block 2 — Phase 2, started 2026-07-16)

```mermaid
flowchart LR
    subgraph LAKE["lake/ (existing)"]
        BARS[("yfinance_daily<br/>4.82M rows")]
        UNIV[("universe_monthly<br/>185 PIT snapshots")]
    end

    subgraph SIGNALS["research/signals/ — backward-looking only"]
        MOM["<b>momentum.py</b><br/>12-1 month"]
        REV["<b>reversal.py</b><br/>trailing 21d"]
        LV["<b>low_vol.py</b><br/>trailing 252d stdev"]
        REG["<b>__init__.py</b><br/>SIGNAL_REGISTRY"]
    end

    subgraph ALPHA["research/alpha/ic.py — forward-looking (research-only)"]
        FWD["compute_forward_returns<br/>21d ahead, bounded window"]
        IC["compute_ic<br/>Spearman rank corr"]
        SERIES["build_ic_series<br/>one pass per rebalance date,<br/>fwd-returns shared across signals"]
        SUM["ic_summary<br/>mean IC, IC t-stat"]
    end

    BARS -- "asof(), backward only" --> MOM
    BARS -- "asof(), backward only" --> REV
    BARS -- "asof(), backward only" --> LV
    BARS -- "asof(), FORWARD (research only)" --> FWD
    UNIV -- "rebalance dates + membership" --> SERIES
    MOM -.-> REG
    REV -.-> REG
    LV -.-> REG
    REG ==> SERIES
    FWD ==> SERIES
    SERIES --> IC
    SERIES --> SUM
```

Real run over the full 2011-2026 lake (`python -m research.alpha.ic --start 2011 --end 2026`): momentum n=169 mean_ic=0.019 t=1.45, reversal n=180 mean_ic=0.0007 t=0.07, low_vol n=174 mean_ic=-0.0017 t=-0.10, 824.2s total — recorded in docs/METRICS.md. `n` differs per signal because each needs a different amount of trailing history before producing its first value (reversal 22d, low-vol 252d, momentum 273d).

## Risk model (Block 3 — full Barra-style scope, built 2026-07-19)

```mermaid
flowchart LR
    subgraph LAKE["lake/ (existing)"]
        BARS[("yfinance_daily")]
        UNIV[("universe_monthly")]
        SEC[("yfinance_sector_current<br/>11 sectors, 1497/1500 tickers")]
    end

    subgraph EXP["research/risk/exposures.py"]
        B["build_exposure_matrix<br/>market + 10 sector dummies<br/>(11th dropped: dummy-trap fix)<br/>+ z-scored momentum/low_vol"]
    end

    subgraph REG["research/risk/regression.py"]
        R["cross_sectional_regression<br/>OLS per date (numpy.linalg.lstsq)<br/>-> factor returns + specific returns"]
    end

    subgraph COV["research/risk/factor_covariance.py +<br/>specific_variance.py"]
        F["build_factor_covariance<br/>EWMA (63d half-life) + sklearn<br/>LedoitWolf shrinkage + Newey-West"]
        D["build_specific_variance<br/>Polars ewm_var per security"]
    end

    subgraph MODEL["research/risk/model.py"]
        M["build_risk_model<br/>RiskModel.sigma()<br/>= B·F·Bᵀ + diag(D)"]
    end

    BARS --> B
    SEC --> B
    UNIV -- "rebalance dates + membership" --> B
    B --> R
    BARS -- "same-day returns" --> R
    R -- "factor returns, stacked over dates" --> F
    R -- "specific returns, stacked over dates" --> D
    F --> M
    D --> M
    B -- "target date's B" --> M
```

Real run (`build_risk_model(store, "2026-07-14", lookback_years=3)`): 985 securities, 13 factors, 179.5s, shrinkage=0.302, Σ symmetric + explicitly confirmed finite — recorded in docs/METRICS.md. Two real bugs found+fixed against the real lake (null sector value crashing `sorted()`; null `ret` becoming NaN via `.to_numpy()` and corrupting `lstsq`), plus one red herring ruled out (spurious Apple Accelerate BLAS warnings, confirmed benign, documented in `RiskModel.sigma()`'s docstring) — full chain in docs/METRICS.md.

**Known simplification**: a different reference sector can be dropped on different dates (whichever is alphabetically first among sectors present that day), so the factor-column set can vary date to date. `build_factor_return_history` handles this by keeping only dates where the full common factor set is present (drop-incomplete, never fabricate) — see `research/risk/model.py`'s module docstring.

## Files & functions

### research/data/store.py — **built** (5 tests)
Bitemporal (point-in-time) parquet store. Two time axes: `effective_date` (when true in market, caller supplies) × `knowledge_ts` (when we learned it, store stamps).

| function | does |
|---|---|
| `PITStore.__init__(root)` | binds store to a lake directory |
| `_dataset_dir(dataset)` | root/dataset path helper |
| `append(dataset, df, knowledge_ts, part=None)` | validates schema (`effective_date` required as pl.Date; stamp columns forbidden), stamps `knowledge_ts`+`load_ts`, writes one parquet batch named by knowledge_ts (+part). Idempotent: re-run overwrites same file |
| `scan(dataset)` | lazy scan of all batches, **no** PIT filter — debug/inspection only |
| `asof(dataset, knowledge_ts, keys)` | the world as known at T: drop rows learned after T, keep latest known revision per (keys, effective_date). The only research read path |

### research/data/delta_store.py — **built** (4 tests, live-verified against `mfts.research` 2026-07-25)
Delta/Unity Catalog mirror of PITStore (Block 6b, infra showcase). Same bitemporal invariant, different mechanism: idempotency is a MERGE on `keys+effective_date+knowledge_ts` (Delta has no per-batch file to overwrite the way PITStore's `k=<ts>.parquet` naming does), and there is no `part` concept (no per-file storage unit to split). Targets `mfts.research.<dataset>` (Unity Catalog schema bound to the `mfts-datalake-2026` S3 external location via its managed location, block 6a). Requires the `delta` extra (`databricks-connect`) in a **separate** venv (`.venv-delta/`) — never the main `.venv`, which the dependency would silently downgrade below `numpy>=2.0`.

| function | does |
|---|---|
| `DeltaPITStore.__init__(spark, catalog, schema)` | binds store to a Unity Catalog schema |
| `append(dataset, df, knowledge_ts, keys)` | validates schema (same rules as PITStore.append), stamps `knowledge_ts`+`load_ts`, MERGEs into the table (insert on no match, overwrite on match) — first call for a dataset does a plain `saveAsTable` |
| `scan(dataset)` | all rows in a dataset, no PIT filter — debug/inspection only |
| `asof(dataset, knowledge_ts, keys)` | same semantics as PITStore.asof, via a `row_number()` window over `(keys, effective_date)` ordered by `knowledge_ts desc` instead of Polars' `group_by().last()` |

### research/data/port_to_delta.py — **built** (2 tests, live-verified 2026-07-26: 6,282,939 rows ported in 103.3s; local-lake copy only, loaders untouched)
Block 6c: one-time copy of a local PITStore dataset's full batch history into Delta — not a re-run of the vendor loaders (that larger scope was explicitly deferred, see docs/STATE.md). Preserves every `knowledge_ts` batch (not just the current asof view): each batch is stripped of its local stamp columns and re-appended through `DeltaPITStore.append` under its ORIGINAL `knowledge_ts`, so bitemporal history survives the copy exactly. `part=`-split batches under the same `knowledge_ts` (PITStore's per-file storage detail, no PIT meaning) collapse into one Delta append, matching `DeltaPITStore`'s lack of a `part` concept.

| function | does |
|---|---|
| `port_dataset(local_store, delta_store, dataset, keys)` | groups the local dataset's rows by `knowledge_ts`, converts each group to a Spark DataFrame (via pandas — new `pyarrow` dependency, needed only for this Polars→pandas bridge), appends via `delta_store.append` |
| `main(argv)` | CLI: `python -m research.data.port_to_delta --dataset yfinance_daily` — must run under `.venv-delta/` (needs `databricks.connect`), prints rows/s for METRICS.md |

### research/data/loaders/crsp_daily.py — **built** (6 tests; live pull blocked until fall)
CRSP daily bars via WRDS, CIZ format (`crsp.dsf_v2`). Delisting returns arrive inside `dlyret` — no separate merge.

| function | does |
|---|---|
| `CRSPDailyLoader.verify_schema()` | asserts expected CIZ columns exist on live table before any pull (columns unverified until first real connection) |
| `load_year(year, knowledge_ts)` | pull one calendar year (common-stock SQL filter) → transform → audit → append on pass / quarantine on fail |
| `_transform(pdf)` | pandas→Polars, vendor→internal names (permno→security_id), derives `dollar_volume`, `market_cap` |
| `_audit(df, year)` | thin wrapper over shared `audit_daily_bars` (null cols: close, ret, volume, shrout) |
| `_quarantine(df, year, ts)` | failed batch → lake/_quarantine/, never enters PIT data |
| `main(argv)` | CLI: `python -m research.data.loaders.crsp_daily --start 2011` — per-year reports, rows/s for METRICS.md |

### research/data/loaders/audit.py — **built (part 2b, shared by all loaders)**
| symbol | does |
|---|---|
| `AuditReport` | per-chunk result: rows, days, null counts, outliers, fetch_failures, failures, `ok` |
| `audit_daily_bars(df, year, null_cols, ...)` | hard-fail: empty chunk, dup (security_id, effective_date), bad trading-day count for past years; nulls + \|ret\|>200% + vendor fetch failures counted, never dropped |

### research/data/loaders/yfinance_daily.py — **built (part 2b; interim vendor while WRDS blocked)**
Dataset `yfinance_daily` keyed by ticker; never merged with `crsp_daily` (security master, part 4). Survivorship-biased, no delisting returns — replaced wholesale by CRSP in fall.

| function | does |
|---|---|
| `YFinanceClient` | real adapter: chunked `yf.download` (auto_adjust=False: raw Close for dollar_volume, Adj Close for returns), `fast_info["shares"]`; paced (`pause_s` between chunks) + exponential backoff on Yahoo throttle (60s doubling, `max_retries`, then chunk skipped into fetch_failures) |
| `_rate_limited_errors(errors)` | detects Yahoo throttle in `yfinance.shared._ERRORS` (batch download swallows YFRateLimitError instead of raising); delisted-ticker errors never match |
| `YFinanceDailyLoader.load_year(year, tickers, knowledge_ts, chunk_size)` | chunked pull → transform → shared audit → append `part=year` / quarantine; failed chunks + missing tickers → `fetch_failures` (flagged, not fatal) |
| `_transform(frames)` | wide→long stack; drops all-null grid artifacts (pre-IPO dates); `ret` = Adj Close pct_change per ticker (first bar/year null, counted); dollar_volume from raw close |
| `load_shares_current(tickers, ts)` | one-row-per-ticker snapshot → own dataset `yfinance_shares_current`, effective_date = fetch date (current-only value; per-bar storage would embed look-ahead) |
| `YFinanceClient.sector_info(ticker)` | (sector, industry) via yfinance `.info` (Yahoo's own taxonomy, not literal GICS) — heavier/more rate-limited than `fast_info`, paced by `pause_s` per call |
| `load_sector_current(tickers, ts)` | one-row-per-ticker snapshot → own dataset `yfinance_sector_current`, mirrors `load_shares_current` exactly (current-only, same look-ahead reasoning). Factor-exposure input for the Block 3 risk model |
| `fetch_listed_tickers()` | NASDAQ Trader symbol files → filter test issues/ETFs/'$'-preferreds, map `.`→`-` (BRK.B→BRK-B) |
| `select_liquid_tickers(store, top_n, year)` | fetch triage for two-phase backfill: top-N by median daily dollar volume in one year (median: spike days don't buy slots). NOT the part-3 universe |
| `read_tickers_file(path)` | one ticker/line, blanks + # comments skipped (feeds `--tickers-file`) |
| `main(argv)` | CLI: `python -m research.data.loaders.yfinance_daily --start 2011` (+`--pause/--max-retries/--backoff` pacing, `--no-threads` sequential drip, `--tickers-file`, `--select-top N --select-year Y` ranking mode, `--shares`) — per-year reports, rows/s for METRICS.md |

### research/universe.py — **built (part 3, 9 tests)**
Monthly PIT universe: dataset `universe_monthly`, one snapshot per month-end trading day, rows = (effective_date, security_id, rank, median_dollar_volume, last_close, days_traded). Market-cap filter deferred to CRSP (no shares data in yfinance bars).

| function | does |
|---|---|
| `month_end_trading_days(bars)` | last observed trading date per calendar month — rebuild dates come from the data, no calendar lib |
| `build_snapshot(bars, rebuild_date, top_n, adv_window, min_price, min_days)` | one month's membership: trailing `adv_window` trading days, per-security median dollar_volume / last raw close / days traded; filters coverage ≥ min_days, close > min_price; rank + cut top_n. Short trailing history → empty (no noise universes) |
| `build_universe(store, start_year, end_year, ..., knowledge_ts)` | asof-read bars at knowledge cutoff (default now), one `build_snapshot` per month-end in range, concat |
| `main(argv)` | CLI: `python -m research.universe --start 2011 --top 1000 --window 60 --min-price 5` — writes `universe_monthly` part per year (idempotent), per-year + done lines for METRICS.md |

### research/security_master.py — **built (part 4, blocks 1-3 of 4; 14 tests)**
Fixes the identity mismatch between `crsp_daily.security_id` (permno) and `yfinance_daily`/`universe_monthly.security_id` (ticker): a permanent `internal_id` spine mapped to date-ranged external identifiers. No CRSP hookup yet (block 4).

| symbol | does |
|---|---|
| `SCHEMA` | `effective_date` (=valid_from, store's required column, repurposed like universe.py), `internal_id` (UInt32 spine), `id_type` (free string — "ticker" today, "permno"/"cusip" later), `id_value`, `valid_to` (null = current), `source` |
| `empty_master()` | zero-row frame matching `SCHEMA`, mirrors `universe.py`'s `_empty_snapshot()` pattern |
| `_ticker_segments(bars, gap_days)` | one row per (ticker, contiguous trading run); a >`gap_days`-calendar-day hole between consecutive trading dates starts a new segment — heuristic proxy for symbol reassignment, NOT a real corporate-actions feed (can't tell "reused ticker" from "long vendor data gap" — confirmed against real data, see METRICS.md) |
| `build_ticker_segments(bars, gap_days=90, source=...)` | segments → `SCHEMA`-shaped frame; `internal_id` assigned deterministically by sorting on (valid_from, ticker) so reruns reproduce the same IDs; `valid_to=null` only for the segment reaching the lake's most recent date |
| `main(argv)` | CLI: `python -m research.security_master --lake lake --gap-days 90` — writes `security_master` (single batch, no year-partitioning — it's an identity table, not a timeseries), reports segment/reuse counts for METRICS.md |
| `resolve_securities(store, id_values, as_of, id_type, knowledge_ts)` | vectorized panel lookup: internal_id for a whole list of identifiers as of one shared date, one query (house rule: no Python loops over stocks). Unresolvable identifiers are simply absent from the output |
| `resolve_security(store, id_value, as_of, ...)` | scalar convenience wrapping `resolve_securities` with one identifier — tests/debugging, not production panel code |

Dataset `security_master` writes/reads through the exact same `store.append`/`store.asof` calls as every other dataset — no new storage mechanism. Proven in tests: ticker reuse (two `internal_id`s sharing one `id_value` over disjoint date ranges) resolves to the correct one via a plain `effective_date`/`valid_to` filter after `asof()`.

### research/signals/ — **built (Phase 2, 7 tests)**
Every signal follows one contract: `fn(bars: pl.LazyFrame, rebuild_date: date) -> pl.DataFrame[effective_date, security_id, signal_value]`. Only looks backward from `rebuild_date` — the PIT boundary this whole project enforces. Scope is momentum/reversal/low-vol only; value/quality/size need fundamentals not yet ingested (data fact, not a preference).

| file / symbol | does |
|---|---|
| `momentum.py` — `compute_momentum(bars, rebuild_date, lookback_days=252, skip_days=21)` | 12-1 month momentum: cumulative log-return from 252 trading days ago to 21 days ago (skip-month excludes reversal contamination). Per-security cumsum + lagged diff, vectorized |
| `reversal.py` — `compute_reversal(bars, rebuild_date, window_days=21)` | trailing 21-day cumulative return, RAW (not sign-flipped) — reversal theory predicts negative IC; the signal reports the empirical value and lets IC measurement reveal the sign |
| `low_vol.py` — `compute_low_vol(bars, rebuild_date, window_days=252)` | trailing 252-day stdev of daily `ret`, RAW (same no-sign-flip convention). Uses `universe.py`'s window-of-dates technique, not momentum's cumsum-diff |
| `__init__.py` — `SIGNAL_REGISTRY` | `{"momentum": compute_momentum, "reversal": compute_reversal, "low_vol": compute_low_vol}` — add a 4th signal by writing the file + one registry line, nothing else changes |

### research/alpha/ic.py — **built (Phase 2, 8 tests)**
IC = rank correlation of a signal vs. the forward return it's trying to predict (DESIGN.md Block 2). Rebalance dates + membership come from `lake/universe_monthly`, point-in-time.

| function | does |
|---|---|
| `compute_forward_returns(bars, rebuild_date, horizon_days=21)` | forward 21-trading-day return per security, from `rebuild_date`. Deliberately reads AHEAD in time — never call from signal/decision code. Bounded to a forward date-window (same technique as `low_vol`) — computing over full history measured at 3.3s/call vs 1.2s bounded (docs/METRICS.md) |
| `compute_ic(signal_df, forward_returns_df)` | Spearman rank correlation between joined signal value and forward return; `None` (not 0) if fewer than 2 securities have both |
| `_ic_for_date(bars, members, d, signal_fns, horizon_days)` | one IC value per signal, for a single rebalance date — extracted from `build_ic_series`'s loop body (block 6d, 2026-07-27) so the same per-date unit is callable both from the local loop and from a Spark `applyInPandas` group (`research/alpha/spark_ic.py`), without duplicating the logic |
| `build_ic_series(store, signal_fns, start_year, end_year, horizon_days=21)` | one IC value per rebalance date, per signal in `signal_fns` (typically the whole `SIGNAL_REGISTRY`) — forward returns computed ONCE per date and shared across every signal via `_ic_for_date`, not recomputed per signal (fixed a 3x redundant-computation bug same session) |
| `ic_summary(ic_series)` → `IcSummary` | mean IC, IC std, IC t-stat — is the edge statistically real or noise |
| `main(argv)` | CLI: `python -m research.alpha.ic --start 2011 --end 2026` — per-signal IC summary + total wall time, for METRICS.md |

### research/alpha/spark_ic.py — **built** (block 6d, not exported from `research/alpha/__init__.py` — same precedent as `delta_store.py`/`port_to_delta.py`)
Spark version of `build_ic_series` (block 6d benchmark, compares against the 824.2s local baseline). Reads both Delta tables via `DeltaPITStore.asof`, distributes the per-date computation across executors via `groupBy(rebalance_date).applyInPandas(...)`, each task calling the SAME `_ic_for_date` (research/alpha/ic.py) that the local loop uses — no duplicated math. No `sc.broadcast()`: Spark Connect (`DatabricksSession`) has no `sparkContext`/RDD-broadcast API at all (confirmed by inspecting the Connect session class directly). A first version instead closed the per-date function over the full driver-collected Polars frames — hit a real 128MB gRPC message-size cap (the pickled closure came out to 462MB; `applyInPandas` ships its function as one unchunked blob, unlike `spark.createDataFrame`). Fixed with a real Spark-side `F.broadcast` RANGE-JOIN: a tiny 185-row `dates_sdf` (rebalance_date + a 430-day-back/35-day-forward window, sized off momentum's real 273-trading-day need) joined against `bars_sdf` on `effective_date BETWEEN window_start AND window_end`, so each group already carries its own bars window server-side. Universe membership stays a small closure dict (a few MB, nowhere near the cap).

| function | does |
|---|---|
| `build_ic_series_spark(delta_store, signal_fns, start_year, end_year, horizon_days=21)` | same long-format result (rebalance_date/signal/ic rows) as `build_ic_series`, computed via Spark instead of a local loop |
| `main(argv)` | CLI: `python -m research.alpha.spark_ic --start 2011 --end 2026` — must run under `.venv-delta/`, prints per-signal summary + wall time for METRICS.md |

### research/risk/ — **built (Block 3, full Barra-style scope, 17 tests)**
First numpy-matrix module in the repo (everything before this is Polars-only). Real-lake verified: 985 securities, 13 factors, 179.5s — see docs/METRICS.md for the 2-bug-plus-1-red-herring debugging chain that got it there.

| file / symbol | does |
|---|---|
| `exposures.py` — `build_exposure_matrix(bars, sectors, rebuild_date, members)` | B per date: market (constant 1.0), sector dummies (11th dropped — dummy-trap fix), z-scored momentum/low_vol. Filters null sector values (real bug: 3 tickers unresolved by yfinance crashed `sorted()` before this fix) |
| `regression.py` — `cross_sectional_regression(returns, exposures)` | OLS per date via `numpy.linalg.lstsq`; coefficients = factor returns, residuals = specific returns. Filters null `ret` (real bug: the loader's known first-bar-of-year null flowed into `.to_numpy()` as NaN and corrupted every downstream matmul before this fix) |
| `factor_covariance.py` — `build_factor_covariance(factor_return_history, halflife_days=63)` | EWMA-weighted (via a row-rescaling trick, since sklearn's `LedoitWolf` has no native sample-weight support) + Ledoit-Wolf shrunk + Newey-West (Bartlett kernel lagged autocovariance) → F |
| `specific_variance.py` — `build_specific_variance(specific_return_history, halflife_days=63)` | Polars native `ewm_var(half_life=...)` per security → D |
| `model.py` — `RiskModel` (dataclass, `.sigma()`), `build_factor_return_history`, `build_risk_model` | orchestrates all of the above into Σ = B·F·Bᵀ + diag(D) for one date, using trailing history for F/D. `RiskModel.sigma()`'s docstring documents the benign Apple Accelerate BLAS warning quirk found here |

### research/portfolio/ — **Block 4 Optimizer BUILT (kicked off 2026-07-20, 14 tests)**
Path corrected to match DESIGN.md's locked repo-layout (`portfolio/`, not `optimizer/` — real-world data ground truth caught mid-build, see docs/STATE.md).

| file / symbol | does |
|---|---|
| `inputs.py` — `build_optimizer_inputs(store, rebuild_date, w_prev=None, lookback_years=3, shrink=0.5, cap=3.0, knowledge_ts=None)` → `OptimizerInputs \| None` | assembles one aligned frame: alpha (placeholder equal-weight blend of all 3 signals in `SIGNAL_REGISTRY`, z-scored then `clip(shrink*mean, -cap, cap)` per DESIGN.md's "optimizer is an error maximizer" defense), beta (`compute_market_beta` over the alpha-surviving set), B/F/D subset+reordered from `RiskModel` to match (kept in factor form, not materialized to a full Σ), and `w_prev` (0.0 default for a flat/new-name start). `None` propagates from `build_risk_model` or an empty post-join cross-section — same "absent means insufficient data" convention as risk/ |
| `OptimizerInputs` (dataclass) | `rebuild_date`, `security_ids`, `factor_names`, `B` (N×K), `F` (K×K), `D` (N), `alpha` (N), `beta` (N), `adv` (N, $ median daily dollar volume from `universe_monthly`), `w_prev` (N) — all N-length arrays row-aligned to `security_ids` |
| `beta.py` — `compute_market_beta(bars, rebuild_date, security_ids, window_days=252, min_obs=None)` | per-stock rolling beta = cov(stock ret, mkt ret)/var(mkt ret); market proxy = equal-weighted mean return across the SAME `security_ids` passed in (no mcap data yet). Fills a real gap: the risk model's own `"market"` exposure (risk/exposures.py) is a constant `1.0` for every stock, not a per-stock CAPM beta — β·w=0 against it would just collapse to dollar-neutral. Needed for the optimizer's real beta-neutral constraint (block 4b) |
| `constraints.py` — `build_constraints(inputs, w, gross_cap=2.0, turnover_cap=0.5, factor_exposure_cap=0.5, adv_days=5.0, book_notional=10_000_000.0)` → `list[cp.Constraint]` | dollar-neutral (`sum(w)==0`), beta-neutral (`beta @ w==0`, real per-stock beta), sector-neutral (each `sector_*` column dotted with `w`==0), ADV-relative position caps (`\|w_i\| <= adv_days*adv_i/book_notional`, `book_notional` a placeholder QP-scaling constant — no real capital figure exists in this project), turnover cap + gross leverage cap (L1 norms), style-factor exposure bounds (momentum/low_vol, `±factor_exposure_cap`). Net-leverage limit and the constant `"market"` column deliberately left unconstrained — both already collapse into dollar-neutral. Borrow-availability filter deliberately NOT built — no free borrow data exists in the lake |
| `solve.py` — `solve_qp(inputs, risk_aversion=5.0, cost_penalty=10.0, **constraint_kwargs)` → `(w, problem)` | builds `max αᵀw − λ·wᵀΣw − κ·‖w−w_prev‖²` s.t. `build_constraints(...)`, solves via cvxpy. Risk term kept in factor form (`quad_form(Bᵀw, F, assume_PSD=True) + Σ(D_i·w_i²)`) — never materializes the full N×N Σ. `assume_PSD=True`: F (Ledoit-Wolf shrunk) is theoretically PSD, skips a spurious DCP failure from float-rounding. The κ soft-turnover term is layered ON TOP of 4b's hard `turnover_cap`, not a replacement |
| `model.py` — `TargetPortfolio` (dataclass), `build_target_portfolio(store, rebuild_date, w_prev=None, lookback_years=3, shrink=0.5, cap=3.0, risk_aversion=5.0, cost_penalty=10.0, knowledge_ts=None, **constraint_kwargs)` → `TargetPortfolio \| None` | block 4d: chains `build_optimizer_inputs` → `solve_qp` into one call, mirroring `research/risk/model.py`'s `build_risk_model` role. `None` propagates from `build_optimizer_inputs` (same "insufficient data" convention). A non-`None` result can still carry a non-optimal `status` (e.g. `"infeasible"` if `w_prev` no longer satisfies that day's caps) — deliberately NOT collapsed into `None`, since infeasibility is real signal for a future backtester, not a data gap; callers must check `status` before trusting `weights`. No CLI (mirrors `risk/model.py`, which also has none). `TargetPortfolio` widened 2026-07-23 (block 5b) with `w_prev`/`adv` fields (straight from `inputs.w_prev`/`inputs.adv`) so `research/backtest/simulate.py`'s cost calc reuses the already-aligned arrays instead of re-deriving them |

### research/backtest/ — **Block 5 Backtester BUILT (kicked off 2026-07-23, 11 tests)**
New directory, sibling to signals/alpha/risk/portfolio/attribution — DESIGN.md's repo-layout diagram never named one explicitly (2026-07-23 decision, docs/STATE.md).

| file / symbol | does |
|---|---|
| `costs.py` — `trade_cost(delta_w, adv, book_notional, half_spread_bps=5.0, impact_coef=10.0, fee_bps=1.0)` → `np.ndarray` ($ per security) | research-side cost proxy since Block 5/C++ hasn't built its own yet: spread + square-root market impact + fees, DESIGN.md's explicit "square-root impact model as starting point." Borrow/financing costs deliberately deferred — no free borrow-rate data exists (same gap as block 4b). Cost RATE (bps) grows sub-linearly (~sqrt) in trade size; total $ cost still grows *faster* than linear since rate × size compounds — do not conflate the two when reasoning about this model. |
| `simulate.py` — `BacktestStep` (dataclass), `run_backtest(store, start_date, end_date, lookback_years=3, shrink=0.5, cap=3.0, risk_aversion=5.0, cost_penalty=10.0, book_notional=10_000_000.0, knowledge_ts=None, cost_kwargs=None, **constraint_kwargs)` → `list[BacktestStep]` | block 5b, THE walk-forward day-loop — the sole sanctioned Python loop-over-dates in this codebase (coding conventions §8's pre-authorized exception). Iterates `universe_monthly` rebalance dates, calls `build_target_portfolio` chaining `w_prev` forward (insufficient-history dates skipped, `w_prev` carries over unchanged — matches a real failed rebalance), applies `trade_cost` to the delta, computes each step's holding-period return via `_holding_period_return` (cumulative return over `(date, next_date]`, dot with target weights, mid-period-missing names dropped — documented approximation, see docs/STATE.md Decisions). `BacktestStep` widened 2026-07-24 (block 5c) with a `turnover` field (`\|delta_w\|.sum()`, computed alongside cost from data already in hand). Block 5d (same file): `HELD_OUT_START = dt.date(2023, 7, 24)` (fixed, DESIGN.md's backtest-overfitting defense — final 3y held out until design freeze; deliberately never recomputed from "today", or the boundary would silently creep forward) + `allow_held_out: bool = False` kwarg — `run_backtest` raises `ValueError` if `end_date >= HELD_OUT_START` unless explicitly overridden. |
| `result.py` — `BacktestResult` (dataclass), `summarize_backtest(steps, book_notional=10_000_000.0)` → `BacktestResult` | block 5c: pure aggregation over `BacktestStep`, mirrors `research/alpha/ic.py`'s `IcSummary` empty-input precedent (no data -> empty result, NOT `None` — unlike `build_target_portfolio`/`build_risk_model`, this function never fails to build, it just has nothing to summarize). Drops the final step (never has a `period_return`). `net_returns = gross_returns - costs/book_notional`; `equity_curve = cumprod(1+net_returns)`. |

### engine/ — **built (broker simulator + order gateway + position keeper + risk checker + market data handler + live AlpacaGateway, 46 Catch2 tests)**
First C++ in the repo. CMake + Catch2 v3.9.1, C++20. Requires Homebrew LLVM on this dev machine (`-DCMAKE_CXX_COMPILER=/opt/homebrew/opt/llvm/bin/clang++`) — system AppleClang/CommandLineTools libc++ headers are broken.

| file / symbol | does |
|---|---|
| `include/broker/OrderEvent.hpp` — `OrderId`, `EventType`, `to_string(EventType)`, `OrderEvent` | shared event type (id, type, qty, price, ts, reason) emitted by any gateway implementation into the same journal |
| `include/broker/IBrokerGateway.hpp` — `Order`, `IBrokerGateway` | abstract interface (`submit_order`/`cancel_order`/`poll_events`) implemented by both `BrokerSimulator` (now) and the future live `AlpacaGateway` |
| `src/broker/BrokerSimulator.hpp/.cpp` — `BrokerSimulator` | mock broker: `submit_order` only registers the order; nothing happens until a test calls `inject_ack`/`inject_fill`/`inject_reject`/`inject_cancel_ack`; every injected event appended to the journal (if set) then queued for `poll_events()`. `inject_fill` validates fill price against a non-market order's `limit_price` (buy: `price <= limit`, sell: `price >= limit`), throws `std::invalid_argument` on violation (fixed 2026-07-28, was a documented gap) |
| `src/journal/EventJournal.hpp/.cpp` — `EventJournal` | append-only CSV log of every `OrderEvent`, flushed synchronously; skeleton only — binary framing + replay-on-restart parser scoped later |
| `include/order/OrderGateway.hpp` / `src/order/OrderGateway.cpp` — `OrderState`, `OrderGateway` | broker-agnostic order state machine (DESIGN.md Block 5) wrapping any `IBrokerGateway`; `submit_order`/`cancel_order` pass through, `pump()` drains `poll_events()` and applies each event to gateway-owned state, `state(id)` queries it. An event on an order already in a terminal state (`Filled`/`Cancelled`/`Rejected`) throws `std::logic_error`; unknown `OrderId` throws `std::out_of_range` (matches `BrokerSimulator::cancel_order`'s precedent). Built 2026-07-30, first of the remaining unscoped Block 5 C++ pieces (position keeper, risk checks, market data handler, live `AlpacaGateway` still not started). |
| `include/position/PositionKeeper.hpp` / `src/position/PositionKeeper.cpp` — `Position`, `PositionKeeper` | average-cost position/P&L tracker built from fills (DESIGN.md Block 5's position keeper), standalone -- not yet wired to `OrderGateway.pump()`'s output (waits on the execution scheduler/main loop, still unscoped). `on_fill(symbol, qty, price, is_buy)`: same-direction fill re-averages cost basis; opposite-direction fill closes open qty first (realizing P&L on the closed portion) and flips to a new position on the other side at the fill price if it overshoots past zero. `position(symbol)` on an untraded symbol returns a default flat `Position{}` (qty=0), not a throw -- unlike `OrderGateway`'s unknown-`OrderId` (a caller bug), never having traded a symbol is normal. |
| `tests/test_broker_simulator.cpp` | 9 Catch2 scenarios: ack, out-of-order fill-before-ack, partial-then-full fill, reject-with-reason, poll drains the queue, cancel on unknown id throws, buy-above-limit throws, sell-below-limit throws, exact-limit fill legal |
| `tests/test_order_gateway.cpp` | 9 Catch2 scenarios: starts New, pump applies Ack, out-of-order fill reaches Filled, partial-then-full fill, reject, cancel-ack, event-on-terminal-order throws, unknown-id state/cancel throw |
| `tests/test_position_keeper.cpp` | 7 Catch2 scenarios: untraded symbol flat, single buy opens long, same-direction fill re-averages cost, partial close realizes P&L, close-past-zero flips side, short position accumulates/closes with correct sign, symbols independent |
| `include/risk/RiskChecker.hpp` / `src/risk/RiskChecker.cpp` — `RiskResult`, `RiskChecker` | pre-trade fat-finger/position-limit/buying-power checks (DESIGN.md Block 5's pre-trade risk checks), the first C++ engine piece that composes two components -- holds a `PositionKeeper&` to read current position. `check(order, price, buying_power)` returns `RiskResult{passed, reason}` (not a throw -- a failing check is routine, matches `research/portfolio/model.py`'s `TargetPortfolio.status` "surface, don't raise" precedent), checked in order: fat-finger (order notional over `max_order_notional`) -> position limit (resulting position notional over `max_position_notional`) -> buying power (buy notional over available cash; sells unconstrained, no margin modeling). No market-data handler exists yet, so `price` is an explicit per-call parameter, same convention as the Python side always taking price/ADV as external input. Bounds are uncalibrated placeholders, same posture as `research/portfolio/solve.py`'s `risk_aversion=5.0`. |
| `tests/test_risk_checker.cpp` | 6 Catch2 scenarios: passes under every limit, fat-finger rejects, position limit rejects, buying power rejects a buy, a sell is unconstrained by buying power, fat-finger is checked first (short-circuit order) |
| `include/marketdata/MarketDataHandler.hpp` / `src/marketdata/MarketDataHandler.cpp` — `Trade`, `Quote`, `MarketDataHandler` | top-of-book tracker (DESIGN.md Block 5's market data handler) -- IEX free feed gives trades+quotes only, no L2 depth. `on_message(raw_json)` parses one of Alpaca's message arrays (real schema verified against Alpaca's own docs, not guessed: trade fields `T,S,i,x,p,s,c,z,t`, quote fields `T,S,bx,bp,bs,ax,ap,as,c,z,t`) and updates the latest trade/quote per symbol; unrecognized message types (auth/subscription acks) are skipped, not an error; malformed JSON propagates as an exception. Pure logic, fully offline-testable -- deliberately separate from the live connection, same split as `DeltaPITStore`'s "live-verified once, not faked" posture. |
| `include/marketdata/AlpacaMarketDataStream.hpp` / `src/marketdata/AlpacaMarketDataStream.cpp` — `AlpacaMarketDataStream` | live `IXWebSocket` connection to `wss://stream.data.alpaca.markets/v2/iex`, feeding raw messages into a `MarketDataHandler`. Auth is a JSON action message sent after connecting (not an HTTP header, per Alpaca's protocol); subscribe is sent only after the server acks authentication. Not unit-tested (needs a real connection); live-verified 2026-08-02 -- connect/auth/subscribe all confirmed against the real server (subscription ack received for AAPL trades+quotes), but no live tick observed since markets were closed (Sunday night) at verification time; re-run during market hours to confirm the tick-parsing path end-to-end. |
| `tools/smoke_market_data.cpp` | one-off live verification tool (not part of the automated suite) -- loads `.env`, connects, prints the first trade/quote received or a diagnostic timeout message. Run: `engine/build/smoke_market_data [symbol] [wait_seconds]` from the repo root. |
| `tests/test_market_data_handler.cpp` | 7 Catch2 scenarios: untraded symbol empty, trade updates latest, quote updates latest, multi-symbol/multi-type batch, unrecognized type skipped, later trade overwrites, malformed JSON throws |
| `src/broker/AlpacaGateway.hpp/.cpp` — `parse_trade_update()`, `AlpacaGateway` | live `IBrokerGateway` backed by Alpaca's real Trading API (DESIGN.md's execution path) -- REST (`libcurl`) for `submit_order`/`cancel_order` against `POST/DELETE .../v2/orders`, the separate `trade_updates` websocket (`wss://.../stream`, its own auth/subscribe/envelope shape, distinct from the market-data feed -- verified against Alpaca's own docs after an initial guess turned out wrong for a related SDK, corrected before shipping) for async order status. `client_order_id` set to `str(OrderId)` on submit so incoming events map back without a reverse lookup; a forward map (`OrderId -> Alpaca UUID`) is kept for cancel, which needs Alpaca's own id. `parse_trade_update()` is a free function (pure JSON-to-`OrderEvent` translation, event-type mapping `new->Ack, fill->Fill, partial_fill->PartialFill, canceled/expired->Cancel, rejected->Reject`, else skipped) -- offline-testable, same live/offline split as `MarketDataHandler`. First genuinely concurrent class in the codebase: the websocket delivers events on its own thread while the caller's thread calls `submit_order`/`cancel_order`/`poll_events`, guarded by one mutex. Not live-order-tested yet (submitting a real paper order is a side-effecting action, held for explicit go-ahead separate from the read-only market-data smoke test). |
| `tests/test_alpaca_gateway.cpp` | 8 Catch2 scenarios covering `parse_trade_update()`: fill/partial_fill/new/canceled/expired/rejected event-type mapping, untracked event type skipped, non-`trade_updates` stream skipped, unrecognized `client_order_id` skipped |
| `CMakeLists.txt` (root + tests/) | Catch2 pinned via FetchContent (v3.9.1); IXWebSocket v12.0.1 (`USE_TLS=ON`, auto-selects Apple SecureTransport on macOS) + nlohmann/json v3.12.0 also via FetchContent; system `libcurl` via `find_package(CURL REQUIRED)` (no FetchContent needed, already on macOS); `build/` gitignored; `broker_sim` library now also builds `src/broker/AlpacaGateway.cpp` + `src/order/OrderGateway.cpp` + `src/position/PositionKeeper.cpp` + `src/risk/RiskChecker.cpp` + `src/marketdata/MarketDataHandler.cpp` + `src/marketdata/AlpacaMarketDataStream.cpp`; links `nlohmann_json::nlohmann_json` + `CURL::libcurl` (PRIVATE, .cpp-only use) and `ixwebsocket::ixwebsocket` (PUBLIC -- `AlpacaMarketDataStream.hpp`/`AlpacaGateway.hpp` hold an `ix::WebSocket` member by value, so it leaks into the public interface) |

### Barrel files
- `research/data/__init__.py` — exports `PITStore`
- `research/data/loaders/__init__.py` — exports `CRSPDailyLoader`, `YFinanceDailyLoader`, `AuditReport`, `audit_daily_bars`

### tests/ — **106 passing, 1 skipped (Python)** + **46 passing (C++, `ctest --test-dir engine/build`)**
| file | covers |
|---|---|
| `test_store.py` | round trip, PIT asof windows (before/mid/after revision), idempotent append, part coexist+overwrite+path-safety, schema rejection |
| `test_delta_store.py` | same 4 behaviors as test_store.py (round trip, asof windows, idempotent append via MERGE, schema rejection), against a real Unity Catalog table — skipped without `DATABRICKS_TOKEN`, skipped at collection entirely outside `.venv-delta` |
| `test_port_to_delta.py` | one append call per distinct knowledge_ts (not one blob), stamp columns stripped before handoff, same-knowledge_ts parts collapse into one call — against a `FakeDeltaStore` double, runs in the main venv (no live connection needed) |
| `test_crsp_loader.py` | happy path into store, re-run idempotency, dup quarantine, short-past-year audit fail, nulls/outliers flagged not dropped, schema verify (offline FakeConn) |
| `test_universe.py` | month-end date derivation, median-not-mean ranking + top-N cut + rank column, $5 filter on raw close, coverage filter (sparse ticker out), short-history empty guard, knowledge-cutoff hides later loads, one snapshot per month, CLI writes dataset, empty-lake exit 1 |
| `test_security_master.py` | empty-frame schema match, round trip through store, store's own effective_date validation still applies, reused-ticker date-ranged resolution (two internal_ids, one id_value, disjoint valid ranges, correct one picked per as-of date incl. the unassigned gap), gap-based segment splitting, no-gap stays one segment, internal_id ordered by valid_from, CLI writes dataset + reports reuse count, panel resolution incl. gap/unresolvable/current cases, scalar wrapper matches panel |
| `test_yfinance_loader.py` | happy path (ret from Adj Close, dollar_volume from raw close), idempotency, grid-artifact drop vs partial-null keep, fetch failures flagged not fatal, failed chunk skipped, dup quarantine, short-past-year fail, shares snapshot, sector/industry snapshot (incl. unresolved ticker -> null), symbol-file parsing (offline FakeClient); throttle detector + backoff schedule + give-up + legit-partial-no-retry (monkeypatched yf.download, fake sleep); volume dtype pinned to Float64 regardless of source int/float split |
| `test_signals.py` | momentum/reversal closed-form match for constant returns, low-vol zero for constant returns, short-history empty guard (all 3), momentum ignores data after rebuild_date (look-ahead safety), registry contains all 3 |
| `test_ic.py` | forward-return closed-form match, empty when insufficient future data, IC perfect positive/negative correlation, IC None below 2 joined rows, build_ic_series restricts to universe membership (and shares forward-returns across signals), ic_summary basic + null-handling + empty |
| `test_exposures.py` | shape + sector dummy correctness, missing-sector exclusion, null-sector-value exclusion (real bug regression test), empty on insufficient history |
| `test_regression.py` | zero-noise exact-coefficient recovery, drops securities missing from either side, null-ret exclusion (real bug regression test), underdetermined → empty |
| `test_factor_covariance.py` | shape/symmetry/shrinkage bounds, correlated factors show higher covariance than uncorrelated, short half-life weights recent data more than a long one (all deterministic, no random-statistical tolerances) |
| `test_specific_variance.py` | constant returns → zero variance, varying returns → positive variance, single-observation exclusion, empty input |
| `test_risk_model.py` | end-to-end shape/symmetry/positive-diagonal against a real PITStore, None on insufficient history |
| `test_portfolio_inputs.py` | end-to-end shape/alignment (B/D/alpha/beta/w_prev all N-length), None on insufficient risk-model history, w_prev supplied vs. flat-start default |
| `test_beta.py` | closed-form match against independent numpy cov/var recomputation, short-history empty guard, outsider security (not in `security_ids`) excluded from both output and the market proxy |
| `test_constraints.py` | real cvxpy Problem (alpha-driven, ridge-regularized objective so the solver actually explores constraint boundaries, not just w=0), asserts every constraint holds on the solved `w`; separate test with an artificially tight ADV cap confirming it actually binds |
| `test_solve.py` | full constraint-satisfaction check on a real `solve_qp` run, zero-alpha-flat-start returns exactly w=0 (deterministic), higher λ provably shrinks gross exposure (monotonicity) |
| `test_model.py` | end-to-end `build_target_portfolio` shape/status/dollar-neutral check on a real store+solve, None on insufficient risk-model history, `**constraint_kwargs` forwarding verified via a tight `gross_cap` that actually binds |
| `test_costs.py` | zero trade -> zero cost, impact RATE (not total $ cost) grows sub-linearly with trade size (flat components zeroed to isolate the sqrt term), lower ADV -> higher cost for the same trade |
| `test_simulate.py` | one step per usable rebalance date (earliest fixture date correctly skipped for insufficient history), w_prev threads across dates (flat-start cost > warm-start cost), insufficient-history dates skipped without crashing the loop, final step's period_return is None, held-out period blocked by default (ValueError), `allow_held_out=True` lets it through |
| `test_result.py` | equity curve matches a hand-computed value exactly (synthetic 3-step list, final no-return step dropped), net return < gross return when cost > 0, empty steps list -> empty result (not None), no crash |
| `engine/tests/test_broker_simulator.cpp` | ack, out-of-order fill-before-ack, partial-then-full fill, reject-with-reason, poll drains the queue, cancel-on-unknown-id throws |

### Config
- `pyproject.toml` — deps: polars ≥1.42, wrds ≥3.2, yfinance ≥1.5, numpy ≥2.0, scikit-learn ≥1.5, cvxpy ≥1.5, pyarrow ≥19 (Polars→pandas bridge, block 6c); pytest config. `delta` extra: databricks-connect ==16.1.* (install into `.venv-delta/` only, per module docstring)

## Not yet started (DESIGN.md blocks)
security master block 4 (CRSP permno/CUSIP hookup) · `research/attribution/` · `common/` · `infra/` (all Block 5 C++ engine pieces now built: broker simulator, order gateway, position keeper, risk checker, market data handler, live AlpacaGateway -- see engine/ section above; live order submission not yet tested, needs explicit go-ahead)
