# Multi-product monorepo: overview and navigation

Last updated: May 5 2026

---

## (a) Design Section

### Overview

**`{WORKSPACE_ROOT}`** is the root of a large **multi-product** source tree. It typically contains several product lines (each with UI, runtime, and config packages), **shared vendor libraries**, configuration-only packages, and infrastructure tooling. This document is the top-level map for layout, conventions, build and test flows, and routing into **domain sub-agent** documents under **`{CONTEXT_DIR}/`**.

**Key problem it solves:** Monorepos sprawl across products. Developers and agents need one entry point for structure, conventions, commands, and where deeper domain docs live.

**High-level approach:** One overview that describes directory patterns, conventions, build and test commands, release coordination, and a **directory → sub-agent** map (where a sub-agent exists). It also flags areas that still lack dedicated sub-agent docs.

### Core Design Decisions

1. **Product-per-directory layout (one convention, not mandatory)**
   - **Rationale:** Giving each product line its own UI, runtime, config, and web-server packages keeps boundaries clear and lets teams deploy independently—**when** that split matches your org.
   - **Approach (example only):** **`{Product}UI/`**, **`{Product}Runtime/`**, **`{Product}RuntimeConfig/`**, **`{Product}UIConfig/`** per product. Shared business logic might live under a **product-common** tree (e.g. **`{PRODUCT_COMMON}/`**) and/or **cross-product vendor libraries** (see decision 2). **Your tree may use different top-level names, fewer products, or a polyrepo—adapt the principles, not necessarily these exact directory tokens.**
   - **Benefits:** When this pattern fits, you get clear ownership, predictable dependencies, and config consumed at deploy time.

2. **Shared libraries over duplication**
   - **Rationale:** Cross-cutting assets (UI metadata codegen, crypto helpers, cloud utilities, HTTP endpoint base classes) should be reused, not forked per product.
   - **Approach:** Install shared functionality from your org’s **vendor packages** (npm, PyPI, crates.io, internal registries—whatever your stack uses). Prefer importing shared libraries before adding product-only copies.
   - **Benefits:** Single source of truth, consistent behavior, easier upgrades.

3. **Config repos consumed at deploy-time**
   - **Rationale:** Environment- or customer-specific JSON/HTML and templates must stay secret-free and deploy on their own cadence.
   - **Approach:** **`*Config/`** trees hold those assets. Never commit secrets; use placeholders, secret manager references, or environment injection.
   - **Benefits:** Safer deploys, clean split between code and configuration.

4. **Experiments and local data isolated from production**
   - **Rationale:** Research scripts and ad-hoc datasets must not become silent production dependencies.
   - **Approach:** Keep **`experiments/`** and local **`data/`** (or equivalent) out of import paths for shipped services unless explicitly reviewed and promoted.
   - **Benefits:** Reduces accidental coupling to unstable code paths.

### Active run

**Purpose:** Point agents at the **current** run workspace. Normative **`{run_slug}`** rules: **lsai_subagents.md** § **Recipe of Recipes** → **Run slug (`{run_slug}`) identification**. Update when starting a **new** run or when the user names a different run to resume.

| Item | Value / placeholder |
|------|------------------------|
| **Project slug** | `aitrader` |
| **Username** | `agoel` |
| **Active `{run_slug}`** | `agoel_stack-bootstrap_20260607-193720` |
| **Run directory** | `~/data/aitrader/runs/agoel_stack-bootstrap_20260607-193720/` |
| **Interaction log** | `~/data/aitrader/runs/agoel_stack-bootstrap_20260607-193720/interaction_log.md` |
| **`{run_started}`** | `20260607-193720` |

**Architecture (template — fill paths at bootstrap):** **Normative stack** lives in **this repo** — **`.cursor/context/`** (agents, routers) and **`.cursor/scripts/`** (router pipeline, bootstrap). **Runtime artifacts** live only under **`~/data/{project_slug}/runs/`** — interaction logs, CoT, MR slug packs, domain outputs. Repo scripts (if any) are invoked by path; they write into the active run folder, not into `.cursor/context/`.

**Prior runs:** *(none yet — when you start a new run, list the previous `{run_slug}` here for resume context.)*

**L2 Cursor keywords (primary):** After L1 OHLCV + news corpus, run `bash .cursor/scripts/run_cursor_keywords.sh` with the run directory above. CoT notes: `{run_dir}/cot/cursor_keywords.cot.md`. Recipe: **`aitrader_subagent.md`** § **Recipe — Cursor keyword extraction (primary)**.

### Project interaction log (per run)

**Purpose:** Resume agent work from disk without re-reading the full Cursor chat. **Canonical templates** (header + turn block) live **here**. Rules + prepend algorithm: **`lsai_superagent.md`** § **Recipe — Project interaction log (every turn)**. **One log per run** under **`runs/{run_slug}/`**. **Fill § Active run** at bootstrap.

**Never overwrite:** Resume the **same run’s** log; **update** (prepend turns, refresh header)—**never** truncate or replace in place. New run → new `{run_slug}` folder and new `interaction_log.md`. **lsai_subagents.md** § **Recipe of Recipes** → **Interaction log on resume (never overwrite)**.

**File header** (preserve when prepending; update **Last updated** each turn):

```markdown
# Interaction log — {project_slug} / {run_slug}

| Field | Value |
|-------|-------|
| **Project slug** | `{project_slug}` |
| **Run slug** | `{run_slug}` |
| **Username** | `{username}` |
| **Run directory** | `~/data/{project_slug}/runs/{run_slug}/` |
| **Log file** | `~/data/{project_slug}/runs/{run_slug}/interaction_log.md` |
| **Run started** | `{run_started}` |
| **Last updated** | `yyyy-mm-dd:hh:mm:ss` |
| **Order** | Newest `## Turn` block first (below this header) |

---
```

**Turn block** (prepend immediately after `---`; one blank line between turns):

```markdown
## Turn XXX
<yyyy-mm-dd:hh:mm:ss>
Question: <full user message — verbatim>
Response: <summary of assistant work>
```

**Run:** Resolve `{run_slug}`; `mkdir -p ~/data/{project_slug}/runs/{run_slug}`; **create `interaction_log.md`** with full header if missing. **Prepend:** **lsai_superagent.md** § **Recipe — Project interaction log (every turn)** → **Prepend algorithm (mandatory — do not truncate)**. **Verify:** log exists under the active run folder; latest `## Turn` is first below `---`; `## Turn` count increased by 1; oldest turn still at bottom.

### MR slug packs (under active run)

**Purpose:** Portable multi-layer MR workspaces live **inside** the run folder. Normative recipe: **`lsai_subagents.md`** § **Recipe — Layered MR slug pack**.

| Item | Value / placeholder |
|------|------------------------|
| **Root** | `~/data/{project_slug}/runs/` |
| **Pack path** | `~/data/{project_slug}/runs/{run_slug}/` |
| **`{run_slug}`** | `{username}_{run_stem}_{run_started}` — **Run slug identification** |
| **Branch binding** | `manifest.json` → `git_branch` (helpers must checkout before work) |
| **Share** | `tar -czf {run_slug}.tar.gz {run_slug}/` from `~/data/{project_slug}/runs/` |

Each pack includes `manifest.json`, layer folders with **CoT** + artifact (`spec.md`, `design.md`, `execution/<track>/steps.md`), and `merges/` for agentic merge audit.

### Git and review context

**Purpose:** Record **your** git host and integration branch when bootstrapping the portable stack. MR recipes use **git** (`git diff`, branches, remotes) and these placeholders — they do **not** hard-code GitHub, GitLab, or any host CLI. **Fill at project bootstrap** (**lsai_superagent.md** § **Recipe — Stack bootstrap (portable)**, step 3).

| Item | Value / placeholder |
|------|------------------------|
| **`{git_default_branch}`** | *(local only — run `git init` and add remote, or set manually)* |
| **`{git_host}`** | *(fill — e.g. GitHub, GitLab, self-hosted)* |
| **`{git_review_label}`** | *(optional UI label — PR, MR, etc.)* |
| **`{git_review_cli}`** | *(optional host CLI — `gh`, `glab`, …; leave empty for clipboard paste only)* |
| **Remote** | *(none)* |

**Bootstrap:** Run **`bash .cursor/scripts/bootstrap_portable.sh`** once (or **`copy_template.sh … --bootstrap`** for a new copy). If **`{git_default_branch}`** is unset, detect via `git symbolic-ref refs/remotes/origin/HEAD` or set manually after `git init`.

### Technical Implementation Details

#### Top-level layout (patterns)

| Directory pattern | Purpose |
|-------------------|---------|
| **`{Product}UI/`** | Web clients per product. Each **`web/`** holds SPA sources (TypeScript, HTML, SCSS); **`android/`** / **`ios/`** when present. |
| **`{Product}Runtime/`** | Backend services (language per product: Python, Go, Node, JVM, etc.). Shared logic in **`{PRODUCT_COMMON}/`** or vendor shared packages. |
| **`*Config/`** | Environment- or customer-specific assets and templates; consumed at **deploy** time. |
| **Vendor shared packages** *(often a common prefix per org)* | Cross-product libraries (crypto, HTTP helpers, codegen, cloud SDKs, etc.). |
| **`experiments/`**, **`data/`** | Research tooling and local datasets — **not** production import paths by default. |
| **`*Apache/`** or equivalent | Web server / reverse-proxy configuration and deploy artifacts. |
| **Internal tooling trees** | Product management, build orchestration, etc. — follow your org’s **build/deploy sub-agent** (filename in your catalog; template **`{CONTEXT_DIR}/{COMPANY_DOC_PREFIX}pnd.md`**) or equivalent docs for clean / init / build / deploy recipes. |

#### Source code conventions

- **UI packages:** Match the **framework generation** already in the tree (NgModule vs standalone components, feature folders under `src/app/<Feature>`).
- **Backend services:** Match the **language and layout** each product documents (for Python-heavy trees, many orgs use **Python 3.9+** with a **`python/`** installable package and **`scripts/`** CLIs—adapt or drop when your repo is not Python).
- **Config repos:** Deploy-time consumption only; **no secrets** in tracked JSON—use placeholders and runtime injection.

**Additional coding standards:** **`{CONTEXT_DIR}/coding_standards.md`** — language-specific sections apply when those stacks exist in your tree.

#### Build & test commands

For product-level UI/backend commands, virtualenv conventions, clean/init/build/deploy, and long-running REST test harnesses, use your **E2E / environments sub-agent** when shipped — template path:

**`{CONTEXT_DIR}/{COMPANY_DOC_PREFIX}e2e.md`**

(set **`{COMPANY_DOC_PREFIX}`** to your org’s markdown prefix for agent files, or `""` if you use unprefixed names).

Quick reference (adapt names to your tree):

- **UI:** `cd <Product>UI/web && npm install && npm run build` — artifacts under **`dist/`** (or your bundler output).
- **Backend (Python example):** `cd <Product>Runtime/python && pip install -e . && pytest` — **omit** if you have no Python runtime.
- **Shared libs:** e.g. `python -m build` for Python wheels, or your package manager’s publish flow for other ecosystems.
- **Interpreter:** use **`{VENV_PYTHON}`** from your documented virtualenv layout; see **`{CONTEXT_DIR}/{COMPANY_DOC_PREFIX}subagents.md`** (or your onboarding doc) for “virtual environment mapping by product” patterns.

#### Release coordination

1. Refresh matching **`*Config/`** content before UI/runtime cuts that depend on new templates.
2. Land backend/API changes before UI that consumes them.
3. Smoke-test with your org’s **staging** or **compose** recipes before tagging.

### Key Components

Use **`{COMPANY_DOC_PREFIX}`** in the **Sub-agent doc** column: final filenames look like `` `{COMPANY_DOC_PREFIX}accounts.md` `` (prefix may be empty). Replace topic tokens with the basenames your **router** and **catalog** actually ship.

| Area | Sub-agent doc (template) | Notes |
|------|--------------------------|-------|
| Accounts, auth, verification | `{COMPANY_DOC_PREFIX}accounts.md` | Signup, deletion, verification flows |
| Background jobs | `{COMPANY_DOC_PREFIX}background.md` | Job catalog, workflow runners |
| Connections / RBAC | `{COMPANY_DOC_PREFIX}connections.md` | Connection APIs, access control |
| E2E testing | `{COMPANY_DOC_PREFIX}e2e.md` | Alpha / beta / gamma recipes |
| HTTP endpoints / base classes | `{COMPANY_DOC_PREFIX}endpoint.md` | Endpoint framework, tests |
| Third-party device / webhook integrations | `{COMPANY_DOC_PREFIX}integrations.md` | Replace with your integration agent basename |
| KPI / metrics recipes | `{COMPANY_DOC_PREFIX}kpi.md` | Recipe-driven analytics |
| SuperAgent / routing | `{COMPANY_DOC_PREFIX}superagent.md` | Router-first SuperAgent design |
| Notifications / chat | `{COMPANY_DOC_PREFIX}notifications.md` | Messaging stack |
| Offers / commerce | `{COMPANY_DOC_PREFIX}offers.md` | Offer lifecycle |
| Payments / billing | `{COMPANY_DOC_PREFIX}payments.md` | Billing integration |
| Build / deploy / PND | `{COMPANY_DOC_PREFIX}pnd.md` | Clean, init, build, deploy |
| State-machine / agent workflows | `{COMPANY_DOC_PREFIX}som_framework.md`, `{COMPANY_DOC_PREFIX}som_testing.md` | As applicable |
| Status & settings | `{COMPANY_DOC_PREFIX}status_and_settings.md` | Product settings surfaces |
| Transactions / ledger | `{COMPANY_DOC_PREFIX}transactions.md` | Ledger formats |
| Web stack / codegen | `{COMPANY_DOC_PREFIX}web_arch.md` | Framework and UI generation |
| Search / indexer | `{COMPANY_DOC_PREFIX}web_indexer.md` | Indexing, publish pipelines, object-store ledgers |
| Cross-cutting ops (CI, admin API, resources) | `{COMPANY_DOC_PREFIX}tooling_other.md` | Tooling boundaries vs deploy and endpoints |
| Mobile async | `{COMPANY_DOC_PREFIX}async_mobile.md` | Mobile integration patterns |
| Macro AI Trader | `aitrader_subagent.md` | Macro news → sector stocks → drift-aware predictions → portfolio |
| Domain-specific product docs | *(router-listed basenames in your checkout)* | As present in your router |

#### Web indexer (template)

Search-console and indexing flows are **owned by a dedicated sub-agent** under **`{CONTEXT_DIR}/`** — **basename is org-specific** (edit this paragraph after import: set the real filename your router publishes for “web indexer / search” topics).

Implementation **typically** spans: a **shared library** tree (publisher abstractions, ledger helpers, batch jobs), a **vendor search-provider API** package, and optionally an **`experiments/`** subtree for **non-production** tooling (promotion-candidate only). **Do not** copy class names or paths from another tenant; document real modules in **your** indexer agent after you template this file.

### Related Files

**Cited by:** (fill from your router’s **Cited by** graph after import.)

- **Sub-agent template:** `{CONTEXT_DIR}/{COMPANY_DOC_PREFIX}subagents.md`
- **Coding standards:** `{CONTEXT_DIR}/coding_standards.md`
- **MR format:** `{CONTEXT_DIR}/git_mr_guidelines.md` *(bundle)* or your legacy MR agent basename
- **Domain router (optional):** `{CONTEXT_DIR}/router.md` — when present
- **L345 router:** `{CONTEXT_DIR}/l345_router.md`
- **Router documentation:** `{CONTEXT_DIR}/{COMPANY_DOC_PREFIX}superagent.md` § Router Architecture and Builder
- **Project interaction log:** this file § **Project interaction log**; recipe in **`lsai_superagent.md`** § **### Recipe — Project interaction log (every turn)**
- **MR slug packs:** this file § **MR slug packs**; recipe in **`lsai_subagents.md`** § **Recipe — Layered MR slug pack**

### Modules / packages still needing first-class sub-agents

When a **library or product area** lacks a dedicated `.md` sub-agent, add one before large feature work or broad onboarding. Suggested names use **`{COMPANY_DOC_PREFIX}`** + a short topic stem; align with your catalog rules.

| Module / area | Purpose | Suggested sub-agent (template) |
|---------------|---------|--------------------------------|
| Encryption utilities | Shared crypto helpers | `{COMPANY_DOC_PREFIX}aes.md` |
| Deduplication engine | Record / entity dedupe | `{COMPANY_DOC_PREFIX}deduper.md` |
| Cloud functions pack | Serverless deploy units | `{COMPANY_DOC_PREFIX}lambda.md` |
| LLM adapters | Model vendor glue | `{COMPANY_DOC_PREFIX}llm.md` |
| Media pipelines | Transcode / storage | `{COMPANY_DOC_PREFIX}media.md` |
| Event / calendar integrations | Third-party calendars | `{COMPANY_DOC_PREFIX}meetup.md` |
| ML toolkit | Training / inference helpers | `{COMPANY_DOC_PREFIX}mltk.md` |
| Social automation | Bot workflows | `{COMPANY_DOC_PREFIX}social_bot.md` |
| Placeholder / TBD package | Document purpose when identified | `{COMPANY_DOC_PREFIX}ss.md` |
| Product management system | Roadmap / SKU tooling | `{COMPANY_DOC_PREFIX}pms.md` |
| Offline-capable product variants | Air-gapped or field modes | extend **`{COMPANY_DOC_PREFIX}pnd.md`** or add `*_offline.md` |
| Additional product lines | Domain-specific MRs | product-specific `{COMPANY_DOC_PREFIX}*.md` |
| UI metadata codegen | Beyond web-arch scope | `{COMPANY_DOC_PREFIX}uigen.md` if split |
| Central builder / CI orchestrator | Beyond PND scope | `{COMPANY_DOC_PREFIX}builder.md` if split |
| Experimental indexer CLIs | Under **`experiments/`** | promote before production imports |

**Note:** New sub-agents should follow your **subagent template** document and be wired into **`router.md`** / **`l345_router.md`** topic indexes and your **router build** pipeline so Context Discovery can find them.
