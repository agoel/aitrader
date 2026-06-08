## IMPORTANT: Context Discovery and Loading (Run First Every Turn)

When the user prompts something, use **user context in Cursor memory** + **the prompt** to understand what topics the request belongs to. Based on those topics, discover the relevant agents and their sections/sub-sections. Produce a **loadable context summary** for the Cursor agent and **load it before running further**.

**Portable stack:** Load **this file** (`router.md`) for **domain / product L2** work and **`.cursor/context/l345_router.md`** for standards, MR shape, recipe templates, and agent authoring. **Both routers every turn** when both exist. **No remote catalog fetch** — agents live under **`.cursor/context/`**.

**Domain agents (this workspace):** No product-specific sub-agents are shipped yet. When **Topic Router** clusters below reference a basename, that file must exist under **`.cursor/context/`** — otherwise **stop** and ask the user to add it (do not download). Until you add domain `*.md` files, domain discovery may yield an **empty** loadable context; still run **l345_router.md** every turn.

**Expert pushback (mandatory):** User may be an expert—**still assume non-expert for stack/process**. Push back **hardest at requirements**; less at design; least at execution. **lsai_subagents.md** § **Recipe of Recipes** → **Expert pushback (mandatory — agent is the expert)**.

**Recipe reuse (mandatory):** L345 recipes and patterns are indexed in **`l345_router.md`** § **Recipe index (canonical)**—scan there before inlining steps. Domain recipes you add belong in **# Recipe index** below (mirror the L345 table). **DRY:** cite or compose via child recipes; do not duplicate **Run** blocks. **lsai_subagents.md** § **Recipe of Recipes** → **DRY, deduplication, and modularization (mandatory)**.

**Project interaction log (mandatory every turn):** Resolve **`{run_slug}`**; log at **`~/data/{project_slug}/runs/{run_slug}/interaction_log.md`** (**repo_overview.md** § **Active run**). **Never overwrite**; prepend per **lsai_superagent.md** § **Recipe — Project interaction log** → **Prepend algorithm** (read entire file first).

**Agent vision (check before proceeding):** See **lsai_superagent.md** § **Router Architecture and Builder** → **### Agent vision**. **Push back** if a required dimension is ambiguous (e.g. which branch to diff)—do not guess.

### Steps to Discover and Load Context

1. **Extract the goal** from the prompt and session.
2. **Match the goal to 2–3 topics** from the **Topic List** below (semantic match; weights are hints).
3. **Look up** each topic under **# Topic Router** and collect `agent.md | section: …` lines.
4. **Build a loadable context summary** (group by file; list sections).
5. **Ensure** each listed `.md` exists and is non-empty under **`.cursor/context/`** — **stop** and report missing files (no download).
6. **Load** those sections before planning, coding, or tools.
7. **Also run** **l345_router.md** Context Discovery when the task touches MR format, recipe structure, coding standards, stack bootstrap, or sub-agent templates.
8. **Interaction log:** At response end, prepend the turn block per **Project interaction log** above.

### Topic List

macro ai trader (6)
sector universe (5)
sentiment keywords (5)
concept drift (5)
macro news prediction (5)
portfolio allocation (5)
yahoo finance data (4)
schwab api setup (4)
stack bootstrap domain (4)
domain sub-agent wiring (3)
portable stack verification (3)

### Example

**User prompt:** "Bootstrap the portable stack and confirm both routers are wired."

**Topics:** stack bootstrap domain, portable stack verification.

**Loadable context:**
```
(empty from domain router — no domain sub-agents shipped)
l345_router.md: stack bootstrap, stack bootstrap portable, superagent install
```

---

# Recipe index (domain — reuse before rewrite)

**Purpose:** Index **product/domain** `## Recipe — …` blocks in domain sub-agents under **`.cursor/context/`**. L345 bundle recipes live in **`l345_router.md`** § **Recipe index (canonical)**—do not duplicate them here.

| Name | Type | Owner | Section | Use when |
|------|------|-------|---------|----------|
| Macro AI Trader (parent) | recipe | `aitrader_subagent.md` | `## Recipe — Macro AI Trader (parent)` | End-to-end macro trading cycle |
| Sector universe definition | recipe | `aitrader_subagent.md` | `## Recipe — Sector universe definition` | Define sectors; pick 10–12 stocks each |
| Yahoo Finance historical data ingest | recipe | `aitrader_subagent.md` | `## Recipe — Yahoo Finance historical data ingest` | Pull OHLCV without API key |
| Charles Schwab API setup and connector | recipe | `aitrader_subagent.md` | `## Recipe — Charles Schwab API setup and connector` | OAuth + quotes when Yahoo fails |
| Sentiment keyword discovery | recipe | `aitrader_subagent.md` | `## Recipe — Sentiment keyword discovery` | Historical keyword→return fit |
| Concept drift detection | recipe | `aitrader_subagent.md` | `## Recipe — Concept drift detection` | Detect hypothesis decay; trigger refresh |
| Macro news ingest and clustering | recipe | `aitrader_subagent.md` | `## Recipe — Macro news ingest and clustering` | Ingest and cluster current news |
| Multi-horizon price prediction | recipe | `aitrader_subagent.md` | `## Recipe — Multi-horizon price prediction` | 2w / 1m / 3m forecasts |
| Portfolio allocation (fixed capital) | recipe | `aitrader_subagent.md` | `## Recipe — Portfolio allocation (fixed capital)` | Buy/sell under fixed budget |

**When adding a domain recipe:** one canonical `## Recipe — …` in the owning agent doc · one row here · one **Topic Router** cluster · bidirectional **Cited by** · prefer **Child recipes** over inlined duplicate steps.

---

# Topic Router

### macro ai trader

- aitrader_subagent.md | section: (a) Design Section | sub-section: Overview
- aitrader_subagent.md | section: Recipe — Macro AI Trader (parent)
- aitrader_subagent.md | section: (b) Project MR Tracking

### sector universe

- aitrader_subagent.md | section: Recipe — Sector universe definition
- aitrader_subagent.md | section: (a) Design Section | sub-section: Technical Implementation Details

### sentiment keywords

- aitrader_subagent.md | section: Recipe — Sentiment keyword discovery
- aitrader_subagent.md | section: (a) Design Section | sub-section: Technical Implementation Details

### concept drift

- aitrader_subagent.md | section: Recipe — Concept drift detection
- aitrader_subagent.md | section: Recipe — Macro AI Trader (parent)

### macro news prediction

- aitrader_subagent.md | section: Recipe — Macro news ingest and clustering
- aitrader_subagent.md | section: Recipe — Multi-horizon price prediction
- aitrader_subagent.md | section: Recipe — Macro AI Trader (parent)

### portfolio allocation

- aitrader_subagent.md | section: Recipe — Portfolio allocation (fixed capital)
- aitrader_subagent.md | section: Recipe — Macro AI Trader (parent)

### yahoo finance data

- aitrader_subagent.md | section: Recipe — Yahoo Finance historical data ingest
- aitrader_subagent.md | section: (a) Design Section | sub-section: Key Components

### schwab api setup

- aitrader_subagent.md | section: Recipe — Charles Schwab API setup and connector
- aitrader_subagent.md | section: (a) Design Section | sub-section: Key Components

### domain sub-agent wiring

- aitrader_subagent.md | section: (a) Design Section
- aitrader_subagent.md | section: Related Files

*(Add more product `*.md` under **`.cursor/context/`**, then add **Topic List** entries and **`###` clusters** here per **lsai_superagent.md** § **Router Builder Recipe**. Do not cite L345 bundle files in this router — **l345_router.md** owns them.)*

### portable stack verification

- lsai_superagent.md | section: Recipe — Stack bootstrap (portable)
- repo_overview.md | section: Active run
- repo_overview.md | section: Project interaction log (per run)

*(Run **`bash .cursor/scripts/bootstrap_portable.sh`** — fills **`repo_overview.md`** § Active run and creates run dir + log + meta on disk. One command; no separate agent bootstrap step.)*

### stack bootstrap domain

- lsai_superagent.md | section: Recipe — Stack bootstrap (portable)
- repo_overview.md | section: Active run
- lsai_subagents.md | section: Recipe of Recipes | sub-section: ### Run slug (`{run_slug}`) identification
- lsai_subagents.md | section: Recipe of Recipes | sub-section: ### Run workspace (`~/data/{project_slug}/runs/{run_slug}/`)

*(After copy: **`{project_slug}`** = folder basename. Fill § **Active run**; ensure run dir has log + meta. Architecture: repo **`.cursor/`** = normative; **`~/data/.../runs/`** = runtime only.)*

**Cited by:** `repo_overview.md`, `l345_router.md`, `lsai_subagents.md` (DRY modularization), `lsai_superagent.md` (Router Architecture and Builder, Recipe index L4 guardrail)
