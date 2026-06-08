# AITrader: Macro AI Trader

Last updated: Jun 7 2026

---

## (a) Design Section

### Overview

**AITrader** is a macro-economic news–driven equity prediction system. It ingests macro and sector news, learns which sentiment keywords historically moved prices, detects when those relationships drift, clusters today's news against historical regimes, and outputs multi-horizon price forecasts and buy/sell recommendations under a fixed-capital portfolio policy.

**Initial scope:** SPY (large-cap) and RUT (small-cap) as anchor indices; 8–12 GICS-aligned sectors with 10–12 liquid names each. **Expansion path:** full-universe scan with ranked long/short candidates.

**Normative orchestration:** **Recipe — Macro AI Trader (parent)** composes child recipes below. Runtime artifacts live under **`~/data/aitrader/runs/{run_slug}/`** — never in `.cursor/context/`.

### Core Design Decisions

1. **Sector-first universe (not flat ticker list)**
   - **Rationale:** Macro shocks propagate through sectors; keyword sensitivity is sector-specific.
   - **Approach:** Define sectors via **Recipe — Sector universe definition**; maintain `sectors.yaml` + `universe.csv` per run.
   - **Benefits:** Interpretable keyword maps; controlled expansion from SPY/RUT anchors to full universe.

2. **Historical sentiment → price linkage before live prediction**
   - **Rationale:** Keywords that "feel macro" may not move prices; fit on history first.
   - **Approach:** **Recipe — Sentiment keyword discovery** builds per-sector keyword–return models from news + OHLCV.
   - **Benefits:** Evidence-backed features; audit trail for each keyword's lift.

3. **Explicit concept-drift layer**
   - **Rationale:** Macro regimes change (Fed cycle, inflation regime, geopolitical); static keyword weights decay.
   - **Approach:** **Recipe — Concept drift detection** monitors rolling IC, hit-rate, and keyword stability; triggers hypothesis refresh.
   - **Benefits:** Prevents silent model rot; documents when to retrain vs. when to hold.

4. **News clustering against historical regimes**
   - **Rationale:** Today's headline mix should map to past clusters with known return distributions.
   - **Approach:** Embed + cluster news windows; align clusters to historical return buckets per sector/index.
   - **Benefits:** Analog-based forecasts complement parametric models.

5. **Multi-horizon outputs (2w / 1m / 3m)**
   - **Rationale:** Macro trades have different holding periods; portfolio needs aligned horizons.
   - **Approach:** Separate calibrated heads per horizon; aggregate in **Recipe — Multi-horizon price prediction**.
   - **Benefits:** Consistent reporting for SPY, RUT, sector ETFs, and single names.

6. **Fixed-capital portfolio policy**
   - **Rationale:** Recommendations must be actionable with a budget constraint.
   - **Approach:** **Recipe — Portfolio allocation** maps scores → weights under max position, sector cap, and cash buffer rules.
   - **Benefits:** Direct buy/sell list with share counts and rationale.

7. **Yahoo Finance primary; Schwab fallback**
   - **Rationale:** Yahoo is zero-setup for alpha; Schwab adds live quotes, account-aware execution later.
   - **Approach:** **Recipe — Yahoo Finance historical data ingest** first; **Recipe — Charles Schwab API setup** when Yahoo fails or live trading is required.
   - **Benefits:** Fast bootstrap; clear upgrade path.

### Technical Implementation Details

#### Data model (runtime artifacts under `runs/{run_slug}/`)

| Artifact | Path | Description |
|----------|------|-------------|
| Sector config | `config/sectors.yaml` | Sector ids, ETF proxies, selection rules |
| Universe | `data/universe.csv` | `sector_id,ticker,name,weight_proxy,liquidity_rank` |
| OHLCV cache | `data/ohlcv/{ticker}.parquet` | Daily bars from Yahoo or Schwab |
| News corpus | `data/news/{date}.jsonl` | Normalized headlines + body snippets + source |
| Keyword map | `models/keyword_map_{sector_id}.json` | Keyword → coefficient, IC, last_validated |
| Drift report | `reports/drift_{date}.md` | Drift metrics + refresh recommendation |
| News clusters | `models/news_clusters.pkl` | Fitted clusterer + cluster centroids |
| Predictions | `reports/predictions_{date}.csv` | `ticker,horizon,expected_return,confidence,cluster_id` |
| Portfolio | `reports/portfolio_{date}.csv` | `action,ticker,shares,notional,rationale` |

#### Anchor indices and sector template

| Role | Ticker | Use |
|------|--------|-----|
| Large-cap anchor | `SPY` | Broad market regime, beta baseline |
| Small-cap anchor | `RUT` (index) / `IWM` (ETF proxy) | Size-factor regime |
| Sector ETF proxy | e.g. `XLK`, `XLF`, `XLE`, … | Sector-level macro beta |

**Starter sectors (8–12):** GICS Level-1 — Technology, Financials, Energy, Health Care, Consumer Discretionary, Industrials, Materials, Consumer Staples, Utilities, Real Estate, Communication Services. Trader may add **Macro Themes** (Rates, FX, Commodities) as synthetic sectors using ETF proxies (`TLT`, `UUP`, `DBC`).

#### Prediction stack (conceptual)

```
News ingest → normalize → embed
                ↓
Historical keyword map ←── OHLCV + labeled news windows
                ↓
Drift monitor ──(refresh)──→ updated keyword map
                ↓
Cluster today's news → regime id
                ↓
Multi-horizon heads (2w, 1m, 3m) → predictions CSV
                ↓
Portfolio allocator → buy/sell recommendations
```

#### Horizons

| Horizon id | Calendar | Target |
|------------|----------|--------|
| `2w` | 10 trading days | Short-term macro reaction |
| `1m` | 21 trading days | Medium tactical |
| `3m` | 63 trading days | Thematic / policy cycle |

### Key Components

| Module | Path (planned) | Recipe |
|--------|----------------|--------|
| Orchestrator CLI | `src/aitrader/cli.py` | **Recipe — Macro AI Trader (parent)** |
| Run workspace | `src/aitrader/workspace.py` | L1 layout + `meta.json` updates |
| Universe builder | `src/aitrader/universe.py` | **Recipe — Sector universe definition** |
| Yahoo connector | `src/aitrader/data/yahoo.py` | **Recipe — Yahoo Finance historical data ingest** |
| Sector starters | `src/aitrader/config/sector_starters.yaml` | 11 GICS sectors × 10 names + SPY/IWM |
| Schwab connector | `src/aitrader/data/schwab.py` | **Recipe — Charles Schwab API setup and connector** |
| News ingest | `src/aitrader/nlp/news.py` | **Recipe — Macro news ingest and clustering** (ingest slice) |
| Historical news (GDELT DOC) | `src/aitrader/nlp/gdelt.py` | **Recipe — Historical macro news ingest** (3mo API) |
| Historical news (GKG bulk) | `src/aitrader/nlp/gdelt_gkg.py` | **Recipe — Historical macro news ingest** (5y backfill) |
| News feeds config | `src/aitrader/config/news_feeds.yaml` | Fed, BLS, BEA, Treasury RSS |
| Historical news config | `src/aitrader/config/historical_news_sources.yaml` | GDELT queries, BigQuery backfill notes |
| Cursor keyword extract | `src/aitrader/nlp/cursor_extract.py` | **Recipe — Cursor keyword extraction** |
| Keyword cache | `src/aitrader/nlp/keyword_cache.py` | Shared cache + phrase grounding |
| Keyword discovery | `src/aitrader/nlp/keywords.py` | **Recipe — Sentiment keyword discovery** |
| Drift monitor | `src/aitrader/ml/drift.py` | **Recipe — Concept drift detection** |
| News clusterer | `src/aitrader/nlp/cluster.py` | **Recipe — Macro news ingest and clustering** (cluster slice) |
| Predictor | `src/aitrader/ml/predict.py` | **Recipe — Multi-horizon price prediction** |
| Portfolio | `src/aitrader/portfolio/allocate.py` | **Recipe — Portfolio allocation (fixed capital)** |

### Layered Implementation sequence

| Global Layer | Name | Delivers |
|--------------|------|----------|
| **L1** | Data plane | Yahoo ingest, universe, OHLCV cache *(shipped)* |
| **L2** | NLP features | News ingest, keyword discovery, clustering *(ingest + keywords shipped)* |
| **L3** | Models + drift | Historical fit, drift monitor, refresh loop *(shipped)* |
| **L4** | Prediction | Multi-horizon heads for SPY/RUT + sectors *(shipped)* |
| **L5** | Portfolio | Fixed-capital allocator, buy/sell report |
| **L6** | Expansion | Full-universe scan, Schwab live quotes |

### Related Files

- **Domain router:** `.cursor/context/router.md`
- **L345 standards:** `.cursor/context/l345_router.md`, `coding_standards.md`
- **Run workspace:** `repo_overview.md` § **Active run**
- **E2E patterns:** `lsai_e2e.md` § Alpha harness

**Cited by:** `router.md`, `repo_overview.md`

---

## Recipe — Macro AI Trader (parent)

**Purpose:** End-to-end macro trading cycle — universe → data → keywords → drift check → news cluster → predict → allocate. Invoke this recipe when the user asks to "run the macro trader," refresh predictions, or produce buy/sell recommendations.

### Formal parameters

| Parameter | Type | Required / Optional / Default | Description |
|-----------|------|-------------------------------|-------------|
| `{run_slug}` | string | **Required** | From `repo_overview.md` § Active run or user-named |
| `{project_slug}` | string | **Default:** `aitrader` | Project data root |
| `{capital_usd}` | number | **Default:** `10000` | Fixed portfolio budget |
| `{anchor_indices}` | list | **Default:** `["SPY","IWM"]` | `IWM` proxies `RUT` for data availability |
| `{horizons}` | list | **Default:** `["2w","1m","3m"]` | Prediction horizons |
| `{lookback_years}` | number | **Default:** `5` | Historical window for keyword fit |
| `{news_sources}` | list | **Default:** `["rss","yahoo_finance"]` | See child news recipe |
| `{drift_threshold}` | number | **Default:** `0.15` | IC drop vs. baseline triggering refresh |
| `{data_provider}` | enum | **Default:** `yahoo` | `yahoo` \| `schwab` |
| `{universe_mode}` | enum | **Default:** `sector` | `sector` \| `full` (L6 expansion) |

### Child recipes

| Child recipe | When invoked | Params passed |
|--------------|--------------|---------------|
| **Recipe — Sector universe definition** | Step 1; missing or stale `universe.csv` | `{anchor_indices}`, `{universe_mode}` |
| **Recipe — Yahoo Finance historical data ingest** | Step 2; `{data_provider}=yahoo` | `{lookback_years}`, tickers from universe |
| **Recipe — Charles Schwab API setup and connector** | Step 2; Yahoo fails or `{data_provider}=schwab` | Schwab tokens from env |
| **Recipe — Cursor keyword extraction** | Step 3a; before IC fit | `{batch_size}`, `{run_dir}` |
| **Recipe — Sentiment keyword discovery** | Step 3b; after Cursor cache | `{lookback_years}`, sector ids |
| **Recipe — Concept drift detection** | Step 4; every run before predict | `{drift_threshold}` |
| **Recipe — Macro news ingest and clustering** | Step 5 | `{news_sources}`, date range |
| **Recipe — Multi-horizon price prediction** | Step 6 | `{horizons}`, `{anchor_indices}` |
| **Recipe — Portfolio allocation (fixed capital)** | Step 7 | `{capital_usd}` |

### Run workspace

`~/data/{project_slug}/runs/{run_slug}/` — bind all params in `meta.json` before Step 1.

### RSI

| Constant | Value |
|----------|-------|
| `_RSI_TYPE` | `external_metric` (L4 predict); `test_suite` (package) |
| `_RSI_MAX_ROUNDS` | `5` (L4 predict) |
| `_RSI_STOP_CONDITION` | News-backed backtest: IC ≥ 0.12, hit rate ≥ 65%, coverage ≥ 60%, N ≥ 3 |
| `_RSI_ARTIFACT_DIR` | `runs/{run_slug}/rsi/` |

### Expert pushback

- **Stop** if `{capital_usd}` unset — allocations are meaningless without budget.
- **Stop** if user requests live Schwab orders before paper/backtest validation — default to recommendation-only.
- **Default** `IWM` over `RUT` for Yahoo OHLCV unless Schwab index feed is configured.
- **Push back** on `universe_mode=full` before L6 ships — start with sector mode.

### Run

1. Resolve `{run_slug}`; `mkdir -p ~/data/{project_slug}/runs/{run_slug}/{config,data,models,reports,rsi}`; update `meta.json` with bound params.
2. Invoke **Recipe — Sector universe definition**.
3. Invoke data child: **Yahoo** (default) or **Schwab** on failure/user choice.
4. Invoke **Recipe — Cursor keyword extraction** (prepare → agent batch JSON → apply → finalize).
5. Invoke **Recipe — Sentiment keyword discovery** on Cursor cache (skip if maps exist and drift not triggered).
6. Invoke **Recipe — Concept drift detection**; if `refresh_recommended`, re-run Cursor + keyword discovery.
7. Invoke **Recipe — Macro news ingest and clustering**.
8. Invoke **Recipe — Multi-horizon price prediction**.
9. Invoke **Recipe — Portfolio allocation (fixed capital)**.
10. Write summary `reports/run_summary_{date}.md` with top buys/sells per horizon and drift status.

**Verify:** `reports/predictions_{date}.csv` and `reports/portfolio_{date}.csv` exist; SPY and IWM rows present for all `{horizons}`; `meta.json` lists completed child recipes.

#### Self-healing

| Symptom | Assess | Recover |
|---------|--------|---------|
| Missing `universe.csv` | Step 1 skipped | Re-run sector universe child |
| Empty OHLCV for ticker | Data gap | Drop illiquid name; log in `reports/data_gaps.md`; retry Yahoo then Schwab |
| Drift refresh loop > 2 | Unstable keywords | Widen `{lookback_years}`; push back on news source quality |
| Zero news today | Ingest failure | Extend window 3 days; check RSS URLs |

---

## Recipe — Sector universe definition

**Purpose:** Define macro-relevant sectors and select 10–12 liquid equities per sector plus anchor indices.

### Formal parameters

| Parameter | Type | Required / Optional / Default | Description |
|-----------|------|-------------------------------|-------------|
| `{sectors_min}` | int | **Default:** `8` | Minimum sector count |
| `{sectors_max}` | int | **Default:** `12` | Maximum sector count |
| `{stocks_per_sector}` | int | **Default:** `10` | Target names per sector (10–12) |
| `{min_avg_volume}` | int | **Default:** `1000000` | 30-day avg daily volume filter |
| `{anchor_indices}` | list | **Required** | e.g. `["SPY","IWM"]` |

### Run

1. Seed `config/sectors.yaml` from GICS Level-1 template (see Design § Anchor indices) plus optional **Macro Themes** ETFs.
2. For each sector, pick sector ETF proxy (e.g. Technology → `XLK`) for macro beta reference.
3. Rank candidates by market cap and `{min_avg_volume}` within sector (use Yahoo screener or static starter list in `config/sector_starters.yaml`).
4. Select top `{stocks_per_sector}`; ensure no duplicate tickers across sectors unless flagged as dual-listed.
5. Write `data/universe.csv` columns: `sector_id,sector_name,ticker,name,etf_proxy,is_anchor,weight_proxy`.
6. Mark `SPY` and anchor rows with `is_anchor=true`.

**Verify:** Row count ≥ `{sectors_min}` × `{stocks_per_sector}` + anchors; every `sector_id` has an `etf_proxy`; CSV parses without null tickers.

#### Self-healing

| Symptom | Recover |
|---------|---------|
| Sector has < 10 names after liquidity filter | Lower `{min_avg_volume}` once; document in `reports/data_gaps.md` |
| Duplicate tickers | Keep higher-liquidity sector; drop other |

---

## Recipe — Yahoo Finance historical data ingest

**Purpose:** Pull daily OHLCV and corporate actions for universe tickers via Yahoo Finance (no API key).

### Formal parameters

| Parameter | Type | Required / Optional / Default | Description |
|-----------|------|-------------------------------|-------------|
| `{tickers}` | list | **Required** | From `data/universe.csv` |
| `{lookback_years}` | number | **Default:** `5` | History depth |
| `{interval}` | enum | **Default:** `1d` | Bar interval |

### Run

1. `pip install yfinance pandas pyarrow` in project venv.
2. For each ticker in `{tickers}`:
   ```bash
   python -m aitrader.data.yahoo --ticker <TICKER> --years {lookback_years} \
     --out ~/data/aitrader/runs/{run_slug}/data/ohlcv/<TICKER>.parquet
   ```
3. Align calendars; forward-fill missing single-day gaps only (max 1 session).
4. Write `data/ohlcv_manifest.json` with row counts and date ranges.

**Verify:** Every universe ticker has a parquet file; manifest shows `start_date` ≤ today − `{lookback_years}`; SPY file non-empty.

#### Self-healing

| Symptom | Recover |
|---------|---------|
| `yfinance` empty for `RUT` | Use `IWM` ETF proxy; note in manifest |
| Rate limit / HTTP 429 | Sleep 2s between tickers; batch size 20 |
| Persistent failure for ticker | Invoke **Recipe — Charles Schwab API setup and connector** for that symbol |

---

## Recipe — Charles Schwab API setup and connector

**Purpose:** Register Schwab developer app, obtain OAuth tokens, and ingest quotes/OHLCV when Yahoo is insufficient or live data is required.

### Formal parameters

| Parameter | Type | Required / Optional / Default | Description |
|-----------|------|-------------------------------|-------------|
| `{schwab_app_key}` | string | **Required** | From Schwab Developer Portal |
| `{schwab_app_secret}` | string | **Required** | Store in env only — never commit |
| `{redirect_uri}` | string | **Default:** `https://127.0.0.1:8182` | Must match portal registration |
| `{token_path}` | path | **Default:** `~/data/aitrader/secrets/schwab_tokens.json` | OAuth token cache |

### Run — Portal setup (one-time, user-guided)

1. Open [Schwab Developer Portal](https://developer.schwab.com/) → **Create App**.
2. Set **API Product** to **Market Data** (and **Accounts & Trading** only if execution is in scope later).
3. Set **Callback URL** to `{redirect_uri}` (HTTPS required; local callback via Schwab's documented loopback).
4. Copy **App Key** and **App Secret** into environment (not repo):
   ```bash
   export SCHWAB_APP_KEY="<your_app_key>"
   export SCHWAB_APP_SECRET="<your_app_secret>"
   mkdir -p ~/data/aitrader/secrets
   ```
5. Run OAuth authorization (browser flow):
   ```bash
   python -m aitrader.data.schwab auth \
     --redirect-uri {redirect_uri} \
     --token-path {token_path}
   ```
6. Complete browser login; approve market data scope; callback writes refresh + access tokens to `{token_path}`.
7. Test quote fetch:
   ```bash
   python -m aitrader.data.schwab quote --symbol SPY --token-path {token_path}
   ```
8. Historical pull (if implemented): map Schwab price history endpoint to same parquet schema as Yahoo.

**Verify:** `quote` returns last price and timestamp; token file exists with `refresh_token`; SPY parquet matches Yahoo within 1% on overlapping dates.

#### Self-healing

| Symptom | Recover |
|---------|---------|
| `401 Unauthorized` | Re-run `auth` subcommand; refresh token expired |
| Callback port blocked | Change portal callback to approved URI; update `{redirect_uri}` |
| Index symbol `RUT` unsupported | Use `IWM` or `$RUT` per Schwab symbology docs |

**Security:** Never commit `{token_path}`, app secret, or `.env` with credentials. Add `~/data/aitrader/secrets/` to global gitignore.

---

## Recipe — Cursor keyword extraction (primary)

**Purpose:** **Cursor agent (CoT)** labels news articles with macro/sector keyword phrases — **no OpenAI API key**. Same prepare → agent → apply pattern as vidtrain step 2.

### Formal parameters

| Parameter | Type | Required / Optional / Default | Description |
|-----------|------|-------------------------------|-------------|
| `{batch_size}` | int | **Default:** `8` | Articles per Cursor batch brief |
| `{run_dir}` | path | **Required** | Active run workspace |

### Child recipes

| Child | When |
|-------|------|
| **Recipe — Sentiment keyword discovery** | After cache populated — IC fit on Cursor phrases |

### Run

1. `python -m aitrader keywords prepare-cursor --run-dir {run_dir}` — writes `data/news/cursor_batches/batch_NNN.md` + `_in.json`.
2. **Parallel extract (fast path):** `keywords fill-cursor --pending-only --workers 8` — uncached articles only; or `keywords run-cursor --workers 8` (fill + apply + discover).
3. **Cursor agent (optional):** read each batch `.md`; write `batch_NNN_out.json`. Policy fill runs in parallel when `--fill` (default on `run-cursor`).
4. `python -m aitrader keywords apply-all-cursor --run-dir {run_dir} --workers 8` — merge batch JSON into `llm_keywords.jsonl`.
5. `python -m aitrader keywords finalize-cursor --run-dir {run_dir}` when done.
6. `python -m aitrader keywords discover --run-dir {run_dir} --workers 8` — IC fit per sector (parallel).

**One-shot:** `bash .cursor/scripts/run_cursor_keywords.sh {run_dir}` — runs `keywords run-cursor --workers 8`.

**CoT backtrack:** append agent notes to `{run_dir}/cot/cursor_keywords.cot.md` per batch checkpoint.

**Optional comparison track:** `keywords extract-openai` (requires `OPENAI_API_KEY`) — not primary.

### Human progress feedback (mandatory on long runs)

Long steps print **`[phase] done/total (pct%) — N left`** to stdout and update **`{run_dir}/reports/pipeline_status.json`**:

| Pipeline | Phases (step/total) | Item progress |
|----------|---------------------|---------------|
| `keywords.run-cursor` | prepare → fill_pending → fill_batches → apply → finalize → discover (5–6) | articles / batches / sectors |
| `keywords.discover` | sector_ic_fit | 12 sectors |
| `predict.backtest` | build_month_features → walkforward_spy | month-ends |
| `news.ingest-historical` | GKG bulk downloads | sampled GKG files |

**Monitor while running:**

```bash
# Live status file (safe to tail in another terminal)
cat ~/data/aitrader/runs/{run_slug}/reports/pipeline_status.json

# Example stdout
# == keywords.run-cursor step 2/5: fill_pending ==
# [fill-pending-keywords] 4000/21317 (19%) — 17317 left — chunk 8/43
```

Use `--quiet` / `-q` to suppress stdout; status file still updates.

**Verify:** `llm_keywords.jsonl` row count increases per `apply-cursor`; `meta.json` → `cursor_keywords.batches_done`; discover report shows `cursor+ic`; `pipeline_status.json` ends with `"status": "done"`.

---

## Recipe — Sentiment keyword discovery

**Purpose:** From historical news + returns, discover keywords/phrases whose sentiment correlates with future price moves per sector.

### Formal parameters

| Parameter | Type | Required / Optional / Default | Description |
|-----------|------|-------------------------------|-------------|
| `{label_horizon}` | enum | **Default:** `1m` | Return label horizon for keyword fit |
| `{min_keyword_ic}` | number | **Default:** `0.03` | Minimum information coefficient to keep |
| `{max_keywords_per_sector}` | int | **Default:** `50` | Cap vocabulary size |
| `{keyword_source}` | enum | **Default:** `cursor` | `cursor` (cached phrases) or `tokens` (bag-of-words fallback) |

### Run

1. Prefer **Recipe — Cursor keyword extraction** cache in `llm_keywords.jsonl`; fallback to token extract if missing.
2. Build labeled dataset: forward return per ticker/sector ETF at `{label_horizon}` (sectors run in **parallel** with `--workers`).
3. Score keyword presence; keep phrases with \|IC\| ≥ `{min_keyword_ic}`.
4. Write `models/keyword_map_{sector_id}.json`:
   ```json
   {"keyword": "rate cut", "coef": 0.012, "ic": 0.05, "direction": "bullish", "last_fit": "2026-06-07"}
   ```
5. Produce `reports/keyword_report_{date}.md` — top 10 movers per sector.

**Verify:** Every sector in `sectors.yaml` has a keyword map; at least 5 keywords per sector or documented sparse sector; no keyword with zero historical support.

#### Self-healing

| Symptom | Recover |
|---------|---------|
| Sparse news history | Extend `{lookback_years}`; add RSS sources in news recipe |
| All IC below threshold | Lower `{min_keyword_ic}` once; flag low-confidence in report |

---

## Recipe — Concept drift detection

**Purpose:** Detect when keyword→return relationships have decayed (concept drift) and recommend hypothesis refresh before live predictions.

### Formal parameters

| Parameter | Type | Required / Optional / Default | Description |
|-----------|------|-------------------------------|-------------|
| `{drift_threshold}` | number | **Default:** `0.15` | Relative IC drop vs. trailing baseline |
| `{eval_window_days}` | int | **Default:** `63` | Rolling evaluation window |
| `{baseline_window_days}` | int | **Default:** `252` | Baseline IC window |

### Run

1. Load current `keyword_map_*.json` and score recent news windows over `{eval_window_days}`.
2. Compute rolling IC, hit-rate, and mean absolute error vs. baseline `{baseline_window_days}`.
3. Per sector, set `drift_score = 1 - (ic_recent / ic_baseline)` (handle sign).
4. If any sector `drift_score > {drift_threshold}` or anchor index drift > threshold → `refresh_recommended=true`.
5. Write `reports/drift_{date}.md` with per-sector metrics and keyword stability table (keywords that flipped sign).

**Verify:** Report includes SPY and IWM drift rows; `refresh_recommended` boolean in `meta.json`; if true, parent re-invokes keyword discovery.

#### Self-healing

| Symptom | Recover |
|---------|---------|
| `ic_baseline` near zero | Sector lacks signal; exclude from portfolio or widen news corpus |
| False positive drift after single event | Require 2 consecutive runs above threshold before refresh |

---

## Recipe — Macro news ingest and clustering

**Purpose:** Ingest macro-economic news, normalize, embed, and cluster current window against historical news regimes.

### Formal parameters

| Parameter | Type | Required / Optional / Default | Description |
|-----------|------|-------------------------------|-------------|
| `{news_window_days}` | int | **Default:** `7` | Days of news to cluster |
| `{cluster_k}` | int | **Default:** `12` | Target clusters (align with sector count) |
| `{embed_model}` | string | **Default:** `text-embedding-3-small` | Or local equivalent |

### Run

1. Ingest from `{news_sources}`: RSS (Fed, BLS, Reuters macro), Yahoo Finance headlines (recent only), optional user CSV.
2. **Before backtest:** invoke **Recipe — Historical macro news ingest** (GDELT + deep RSS) so `corpus.jsonl` has dated macro coverage — Yahoo alone is not sufficient for walk-forward.
3. Normalize to schema: `{id, published_at, title, body, source, tags}` → `data/news/{date}.jsonl`.
4. Embed documents; fit or apply k-means / HDBSCAN with `{cluster_k}`.
5. Map each cluster to historical return profile per sector (from labeled history).
6. Save `models/news_clusters.pkl` and `reports/news_cluster_{date}.md` (top terms per cluster).

**Verify:** Today's jsonl has ≥ 10 articles or documented low-news day; cluster assign for current window written to `models/current_cluster.json`.

#### Self-healing

| Symptom | Recover |
|---------|---------|
| RSS fetch fail | Retry 3×; fall back to cached prior day |
| Single mega-cluster | Increase `{cluster_k}` by 2 once |
| Backtest months with `news_articles=0` | Run historical ingest; do **not** substitute price momentum for missing news |

---

## Recipe — Historical macro news ingest

**Purpose:** Build a **dated** macro news corpus for backtest and walk-forward — independent of Yahoo's recent-headline bias.

### Formal parameters

| Parameter | Type | Required / Optional / Default | Description |
|-----------|------|-------------------------------|-------------|
| `{timespan}` | string | **Default:** `90days` | GDELT DOC rolling window (max ~3 months) |
| `{rss_window_days}` | int | **Default:** `365` | Deep RSS pull from Fed/BLS/BEA/Treasury |
| `{gdelt_queries}` | list | **Default:** from `historical_news_sources.yaml` | fed, inflation, employment, earnings, tariff |
| `{lookback_years}` | number | **Default:** `5` | If > 0.25y, enable GDELT BigQuery GKG export (future) |

### Where historical news lives

| Source | Depth | Module / config |
|--------|-------|-----------------|
| **GDELT GKG 2.0 bulk** | **Primary** — Feb 2015+, sample 1 file / 7 days (5y default) | `nlp/gdelt_gkg.py`, `historical_news_sources.yaml` § `gdelt_gkg` |
| **Google News macro RSS** | ~1 year per query; Reuters/Bloomberg/Fed via search | `historical_news_sources.yaml` § `google_news_rss` |
| **GDELT DOC 2.0 API** | Rolling ~3 months (supplement) | `nlp/gdelt.py` |
| **Fed/BLS/BEA/Treasury/SEC/ECB RSS** | Official releases, precise `pubDate` | `news_feeds.yaml`, `--rss-window-days` |
| **GDELT BigQuery** | Dense SQL export (opt-in) | `historical_news_sources.yaml` § `gdelt_bigquery` |
| Yahoo Finance | Recent headlines only | Not used for historical backtest depth |

### Run

```bash
python -m aitrader news ingest-historical --run-dir ~/data/aitrader/runs/{run_slug} \
  --rss-window-days 365 --gkg-lookback-days 1825 --gkg-sample-days 7
```

1. **GKG bulk** — download sampled `.gkg.csv.zip` files from GDELT masterfilelist; filter `ECON_*` / `EPU_*` themes; prefer Reuters/Bloomberg/CNBC/Fed domains.
2. **Google News RSS** — macro queries with `when:1y` (fed, CPI, earnings, tariffs, Reuters).
3. **GDELT DOC** `ArtList` per macro query (rate limit 6s).
4. **RSS** with `{rss_window_days}`; append to `data/news/corpus.jsonl` (dedupe by `id`).
5. Re-run Cursor keywords + discovery on expanded corpus before `predict backtest`.

**Verify:** `corpus.jsonl` has articles spanning **years** (not a single-day spike); `distinct_dates` ≫ 15; backtest monthly rows show `news_articles > 0` on multiple months.

#### Self-healing

| Symptom | Recover |
|---------|---------|
| GDELT DOC rate limit | Wait 6s between queries; reduce `maxrecords` |
| GKG ingest slow | Raise `{sample_days}` to 14; lower `{max_per_file}` |
| Need denser daily coverage | Enable `gdelt_bigquery` or lower `{sample_days}` to 1 |

**Future indicator (not news):** Price **momentum** will be added as a **separate L4+ indicator** layer. When `news_articles < min_news_confident`, predictor emits `no_news_signal=true` and neutral forecast — momentum does **not** replace missing news.

---

## Recipe — Multi-horizon price prediction

**Purpose:** Produce expected return and confidence for SPY, RUT proxy (IWM), sector ETFs, and universe stocks at 2w, 1m, and 3m horizons.

### Formal parameters

| Parameter | Type | Required / Optional / Default | Description |
|-----------|------|-------------------------------|-------------|
| `{horizons}` | list | **Default:** `["2w","1m","3m"]` | Output horizons |
| `{model_type}` | enum | **Default:** `ensemble` | `linear` \| `gbm` \| `ensemble` |
| `{confidence_method}` | enum | **Default:** `bootstrap` | Uncertainty bands |

### Run

1. Features: keyword scores from current news, cluster id one-hot, recent momentum (training feature only), sector ETF beta to SPY.
2. **No-news policy:** if `news_articles < min_news_confident`, expected return = 0, wide bands, `no_news_signal=true` — do not fall back to momentum-only forecast (momentum indicator is a future separate slice).
3. Train or load per-horizon models (separate heads for `2w`, `1m`, `3m`).
4. Score full universe + anchors; output `reports/predictions_{date}.csv`:
   `ticker,sector_id,horizon,expected_return,confidence_lower,confidence_upper,cluster_id,top_keywords`.
5. Add index summary rows for `SPY` and `IWM` at top of CSV.

**Verify:** All `{horizons}` present for anchors; confidence bounds ordered lower < expected < upper; no duplicate ticker×horizon rows.

**Backtest (mandatory before L5):** `python -m aitrader predict backtest --run-dir {run_dir}` — walk-forward IC/hit-rate vs realized returns; slices by **cluster_id** and **macro event** (fed, inflation, earnings, tariff). Artifacts: `reports/backtest_predictions_{date}.csv`, `backtest_summary_{date}.csv`, `backtest_report_{date}.md`. `l4` runs predict + backtest by default.

**Performance gate (mandatory):** **lsai_subagents.md** § **Recipe — Slice-first performance gate (data pipelines)**. Domain budgets: probe **3 months** + **10 macro days** under **60s** before full backtest; hot paths must reuse `news_clusters.pkl` sector profiles (no per-month `_sector_return_profiles`), macro event study **one row per trading day** (not per article), signal capped to **100** articles/window in backtest only.

**RSI performance:** `build_backtest_feature_cache` runs expensive feature build **once**; each RSI candidate only re-scores walk-forward + macro predictions (~seconds). Do **not** call full `_monthly_spy_backtest` + `_macro_event_study` per round.

**RSI (mandatory before L5):** `python -m aitrader predict rsi --run-dir {run_dir}` — up to 5 tuning rounds; saves `models/predict_config.json` and `rsi/predict_rsi.md`. Stop when news-backed IC ≥ 0.12, hit rate ≥ 65%, confidence coverage ≥ 60% (N ≥ 3 news months). `l4` runs RSI after backtest unless `--skip-rsi`.

#### Self-healing

| Symptom | Recover |
|---------|---------|
| Model file missing for horizon | Train from cached features; flag `cold_start` in CSV |
| Extreme prediction (> 50% in 2w) | Cap at 3σ historical move; log in summary |

---

## Recipe — Portfolio allocation (fixed capital)

**Purpose:** Convert predictions into buy/sell/hold with share counts for a fixed USD budget.

### Formal parameters

| Parameter | Type | Required / Optional / Default | Description |
|-----------|------|-------------------------------|-------------|
| `{capital_usd}` | number | **Required** | Total deployable capital |
| `{max_position_pct}` | number | **Default:** `0.10` | Max weight per single name |
| `{max_sector_pct}` | number | **Default:** `0.25` | Max sector weight |
| `{cash_buffer_pct}` | number | **Default:** `0.05` | Uninvested cash |
| `{primary_horizon}` | enum | **Default:** `1m` | Horizon driving weights |

### Run

1. Rank names by risk-adjusted score: `expected_return / confidence_width` at `{primary_horizon}`.
2. Apply long-only default (short optional in L6); filter confidence below 10th percentile.
3. Optimize weights: maximize score subject to `{max_position_pct}`, `{max_sector_pct}`, `{cash_buffer_pct}`.
4. Convert weights to integer shares using latest close from OHLCV cache.
5. Emit `reports/portfolio_{date}.csv`: `action,ticker,sector_id,shares,notional_usd,weight_pct,rationale`.
6. List sells: names with negative expected return above confidence threshold in existing book (if positions file provided).

**Verify:** Sum of `notional_usd` ≤ `{capital_usd}` × (1 − `{cash_buffer_pct}`); no sector exceeds `{max_sector_pct}`; at least SPY or IWM position rationale in summary.

#### Self-healing

| Symptom | Recover |
|---------|---------|
| Insufficient cash for 1 share of top pick | Skip to next liquid name |
| All scores negative | Raise cash to 100% − buffer; document defensive stance |

---

## (b) Project MR Tracking

#### Title

`Server Only: Release 1: Macro AI Trader — SPY/RUT sector pipeline`

#### Layered Implementation Sequence

| Layer | Step | Description | Status |
|-------|------|-------------|--------|
| L1 | 1 | Sector universe + Yahoo OHLCV ingest | completed |
| L1 | 2 | CLI scaffold + run workspace layout | completed |
| L2 | 1 | Macro news ingest + jsonl schema | completed |
| L2 | 2 | Cursor keyword extraction + IC discovery | completed |
| L3 | 1 | Concept drift detection + refresh loop | completed |
| L3 | 2 | News clustering vs historical regimes | completed |
| L4 | 1 | Multi-horizon prediction (SPY, IWM, sectors) | completed |
| L5 | 1 | Portfolio allocation (fixed capital) | pending |
| L6 | 1 | Schwab connector + full-universe mode | pending |

#### Details

- **Domain agent authored:** `aitrader_subagent.md` with parent recipe and eight child recipes (universe, Yahoo, Schwab, keywords, drift, news, predict, portfolio).
- **Router wired:** `router.md` topic clusters for macro trader workflows.
- **L1 shipped:** `src/aitrader/` package — `workspace.py`, `universe.py`, `data/yahoo.py`, `cli.py`; bundled `sector_starters.yaml` (11 sectors × 10 + SPY/IWM anchors = 112 tickers).
- **L1 verified:** `pytest tests/` (8 passed); active run has `universe.csv` (112 rows), `ohlcv_manifest.json` (112/112 ok), SPY parquet (1255 rows).
- **L2 shipped:** `nlp/news.py` (RSS + Yahoo → jsonl corpus), `nlp/cursor_extract.py` (prepare/apply/finalize), `nlp/keywords.py` (IC on Cursor cache), `config/news_feeds.yaml`.
- **L2 verified:** 1115 articles ingested; Cursor batches under `data/news/cursor_batches/`; `llm_keywords.jsonl` + refreshed `keyword_map_*.json` after `run-cursor`.
- **L3 shipped:** `ml/drift.py` (IC drift + 2-run refresh guard), `nlp/cluster.py` (TF-IDF + KMeans regimes).
- **L3 verified:** `drift_{date}.md`, `news_clusters.pkl`, `current_cluster.json`; tests 18 passed.
- **L4 shipped:** `ml/predict.py` (Ridge per horizon, keyword + cluster + momentum + beta features); CLI `predict run` / `l4`.
- **L4 verified:** `predictions_{date}.csv` with SPY/IWM anchors at top; `predictor_{horizon}.pkl` under `models/`.
- **L4 backtest:** `ml/backtest.py` — walk-forward keyword/cluster/sentiment vs realized; monthly SPY replay when news dates sparse.

#### TODO

- None (L4 complete; L5 portfolio next).

#### TODO Next release

- Schwab OAuth CLI and live quote path.
- Manual per-batch Cursor CoT refinement (replace policy fill for higher-quality phrases).

#### TODO Future release

- Full-universe scan (`universe_mode=full`) with parallel scoring.
- Live order execution via Schwab Accounts API (paper then live).
- Automated RSS expansion (Fed, ECB, BLS, BEA).

#### Alpha Testing

1. **L1-S1 — Yahoo SPY ingest:** **Run:** `python -m aitrader.data.yahoo --ticker SPY --years 5 --out <run>/data/ohlcv/SPY.parquet`. **Verify:** File exists; row count > 1000; latest date within 3 sessions.
2. **L1-S1 — Universe build:** **Run:** sector universe recipe for 8 sectors × 10 names. **Verify:** `universe.csv` row count ≥ 80; anchors flagged.
3. **L3-S1 — Drift report (cold):** **Run:** drift recipe with synthetic keyword map. **Verify:** `reports/drift_{date}.md` created; `refresh_recommended` in meta.

#### Beta Testing

Not applicable — no deployed service in Release 1.

#### Gamma Testing

Not applicable — research/backtest only in Release 1.
