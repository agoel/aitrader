# Coding Standards & Review Checklist

Last updated: May 5 2026

---

## Overview

This document defines coding standards for a **large multi-product monorepo** (Cursor workspace). **Sections below for Python, TypeScript/Angular, and UI codegen apply only when those trees exist** in your checkout—this minimal OmMeGo context bundle may ship **markdown-only** until you add application code.

Use this file when making changes to existing projects or adding new code. For repo layout, build commands, and sub-agent mapping, see **`{CONTEXT_DIR}/repo_overview.md`**. For MR format and structure, see **`{CONTEXT_DIR}/git_mr_guidelines.md`**. *(Legacy internal basename `gitlab_mr_guidelines.md` may exist in older snapshots—public file is `git_mr_guidelines.md`.)*

Set **`{CONTEXT_DIR}`** to your agent context root (commonly **`.cursor/context/`** under **`{WORKSPACE_ROOT}`**). Set **`{COMPANY_DOC_PREFIX}`** to the basename prefix your org uses for sub-agent markdown files (may be **empty**; otherwise a short token such as **`acme_`**—never hard-code another company’s prefix in a sanitized bundle).

---

## Python runtimes

- Follow PEP8 plus `black` formatting (88 columns) except where legacy code breaks; touch-up only the lines you edit.
- Keep IO, network, and DB access inside `services/` or `clients/` modules; expose pure functions or dataclasses for business logic.
- Add unit tests under the nearest `test/` package. Favor pytest parametrization over ad-hoc loops.
- Validate config with `pydantic` models when adding new JSON payloads to `*Config` repositories.

## TypeScript/Angular clients

- Prefer standalone services for HTTP access inside `src/app/shared/services`. Reuse existing HTTP service patterns for REST calls.
- Components belong inside feature folders with matching `.ts`, `.html`, `.css`. Keep templates declarative; push logic into the component class or shared pipes.
- Use RxJS `Observable` streams instead of Promises so existing interceptors continue to work.
- Run `npm run lint` and `npm run test` before shipping complex UI changes.

## File organization (Python)

- Major classes are stored in their own files with the same name.
- Minor enum or helper-related classes are defined at the top of the file of the most important class they belong to, keeping the same name.
- New libraries must be added to `setup.py` correctly for wheels packaging—usually a new sub-folder inside `python/` in a deployable package under **`{PACKAGE_NAME}`** (shared library or product runtime tree).
- Use a `general.py` for helper static methods in a brand-new Python package.

## Cross-cutting rules

- **Expert pushback:** User may be an expert; **still assume non-expert for stack recipes/process**. Push back **most aggressively at requirements**; intensity drops through design → execution. **lsai_subagents.md** § **Recipe of Recipes** → **Expert pushback (mandatory — agent is the expert)**.
- **Recipe DRY:** Scan **`l345_router.md`** § **Recipe index (canonical)** before writing procedure steps; reuse, compose via **Child recipes**, or cite—never duplicate indexed **Run** blocks. **lsai_subagents.md** § **Recipe of Recipes** → **DRY, deduplication, and modularization (mandatory)**.
- Avoid hard-coding credentials or tenant-specific URLs; read them from the appropriate `config.json` file or environment.
- Document every new script or job with usage notes in a sibling `README`.
- When touching multiple products, land shared changes in your **shared Python library** first and bump the dependent packages.
- Keep large data files (CSV, media) out of the repo—store them in **object storage** (e.g. **S3** or equivalent under **`{BUCKET}`**) and reference the path or URI instead of committing blobs.

### Timestamp and datetime standardization (MANDATORY)

**DO NOT** create new datetime format constants, new timestamp helper methods, or inline `strftime`/`strptime` calls against format strings when your platform already publishes a **canonical format** and **shared helpers** (typically in a **`general`** module under your shared Python tree). All new code **must** reuse the org-defined helpers.

| Constant / Helper | What it does |
|-------------------|--------------|
| `DATETIME_FORMAT_MICROSECONDS` (`"%Y-%m-%d:%H:%M:%S:%f"`) | **The** standard datetime format for the platform. All new timestamp fields must use this format. |
| `get_server_time_stamp_as_str(dt)` | Format a `datetime` → string using the standard format. |
| `get_server_current_time_stamp_utc()` | Return `(datetime, str)` of the current UTC time in the standard format. |
| `get_server_time_stamp_from_str_utc(s)` | Parse a standard-format string → `datetime`. |
| `parse_date_time_microseconds(s)` | Same parse, simpler alias. |

**Rules:**
1. **Never introduce a new format constant** (e.g. `VERSION_DATETIME_FORMAT`, `MY_CUSTOM_FORMAT`). Use the platform’s canonical constant (above).
2. **Never call `strftime` / `strptime` directly** against a format string when one of the four helpers above already does the job.
3. **Never use legacy spaced variants** for new fields when your platform documents a colon-separated canonical form; reserve alternate layouts for legacy fields only.
4. When a module needs the current UTC time as a version or creation stamp, call **`get_server_current_time_stamp_utc()`** — do not call `datetime.now(timezone.utc).strftime(...)` with a custom format.

**Why this matters:** Multiple incompatible timestamp formats across the codebase cause silent parsing failures, broken comparisons, and hard-to-diagnose production bugs. One format, one set of helpers, everywhere.

## Code-generated files (DO NOT EDIT)

Some files in the repo are **code-generated** by a **UI metadata code generator** pipeline. Agents and developers **must never** hand-edit these files—changes will be silently overwritten on the next codegen run, and manual edits cause merge noise and subtle bugs.

| Generated file pattern | Source of truth |
|---|---|
| `*Runtime/python/*/uig_metadata.json.template` | `{Product}UIConfig/components/*.json` + codegen templates |

**Regeneration command (template):**

```bash
{VENV_PYTHON} {UI_CODEGEN_ROOT}/generate_ui.py -c {PRODUCT}UIConfig
```

Set **`{VENV_PYTHON}`** to your project virtualenv’s `python`. Set **`{UI_CODEGEN_ROOT}`** and **`{PRODUCT}`** per your workspace layout. Example product prefixes: `{PRODUCT}` uppercase with matching lowercase venv/product folder names as used in your org.

**Rules:**
1. **Never edit `uig_metadata.json.template` directly.** Edit the source JSON in `{Product}UIConfig/components/` and re-run the codegen command above.
2. If you need to change generated UI metadata, trace back to the component JSON in `*UIConfig/components/` and the templates under your codegen tree.
3. When reviewing diffs, skip `uig_metadata.json.template` changes — they should only appear as a result of codegen, never as hand-edits.

**Why this matters:** Agents repeatedly edit generated templates during agentic coding sessions because they look like normal config files. They are not—they are regenerated from UI config JSON and templates.

---

## Alpha, Beta, Gamma testing (recipes)

When doing alpha, beta, or prod (gamma) testing, use **recipes** in **`{CONTEXT_DIR}/{COMPANY_DOC_PREFIX}e2e.md`** when that agent ships in your bundle. The main router (**`{CONTEXT_DIR}/router.md`**) routes topics to the right recipe sections:

| Stage | When to use | Recipe source | Router topics |
|-------|-------------|----------------|----------------|
| **Alpha** | Localhost development, before beta/prod | `{COMPANY_DOC_PREFIX}e2e.md` — execution environments, alpha setup, interstitial loop, per-run evidence; for UX bugs with video, video-debug sections | `alpha`, `alpha testing`, `alpha test design template`, `video UX debugging` |
| **Beta** | Remote integrations (e.g. third-party webhooks), deploy to staging | `{COMPANY_DOC_PREFIX}e2e.md` — remote staging, evidence files, log analysis, warm-up/throttle templates | `beta testing`, `beta Apache babysitter`, `run_beta_monitor` |
| **Gamma** | Production one-box pre-merge validation | `{COMPANY_DOC_PREFIX}e2e.md` — stage validation and MR reporting | `alpha beta gamma testing` |
| **Domain overlays** | Product-specific E2E | Domain agents under **`{CONTEXT_DIR}/`** when present (offers, integrations, indexer, KPI, etc.) | Match topics in **`router.md`** to those agents **when `router.md` exists** |

**How to discover:** Use **`router.md`** Context Discovery when that file exists—match your goal to topics, then load the listed sections. For alpha/beta/gamma testing, **`{COMPANY_DOC_PREFIX}e2e.md`** is the canonical template when present; domain-specific agents add their own Run/Verify steps.

**Updating docs during iterative recipes:** Refresh **logs, interstitial files, and test data** every round; **do not** update curated **`{CONTEXT_DIR}/*.md`** recipe “brain” after every iteration — **batch-update when the pass stops**. See **`{COMPANY_DOC_PREFIX}superagent.md`** (router architecture, recipe documentation cadence) and **`{COMPANY_DOC_PREFIX}e2e.md`** (principles / documentation cadence).

---

## Related Files

**Cited by:** `repo_overview.md`, `git_mr_guidelines.md`, `lsai_subagents.md` *(example basename; your org may use `{COMPANY_DOC_PREFIX}subagents.md`)*, `l345_router.md` (recipe reuse DRY topic), `{COMPANY_DOC_PREFIX}superagent.md`, `{COMPANY_DOC_PREFIX}e2e.md`, and other domain agents as deployed.

### Bidirectional citation rule

**Bidirectional citation rule (MANDATORY):** When you add a new reference to another document in this section (or elsewhere in this file), you **must** also add this file to the **Cited by** line in that target document. Format: `coding_standards.md (§ <section name>)`. Do not add references without updating the target's Cited by—both directions must stay in sync.

- **Repo overview:** `{CONTEXT_DIR}/repo_overview.md` — Top-level layout, build/test commands, sub-agent mapping.
- **MR format:** `{CONTEXT_DIR}/git_mr_guidelines.md` — git remote review body structure and sections (host choice in **repo_overview.md** § **Git and review context**).

### Sub-agent template

- **Sub-agent template:** `{CONTEXT_DIR}/{COMPANY_DOC_PREFIX}subagents.md` — Template for documenting sub-agent projects. **MR shape:** `{CONTEXT_DIR}/git_mr_guidelines.md` § **Sections**.
- **E2E recipes:** `{CONTEXT_DIR}/{COMPANY_DOC_PREFIX}e2e.md` — Alpha/beta/gamma testing recipes; interstitial patterns and evidence. For UX bugs demonstrated by video, see video-debug sections when present.
- **Domain router (optional):** `{CONTEXT_DIR}/router.md` — Topic-based routing to **product** agents when that file exists; otherwise rely on **`l345_router.md`** and any project rules you add.
- **L345 router:** `{CONTEXT_DIR}/l345_router.md` — L3/L4/L5 agentic work (agent creation, recipes, router building); use when creating or modifying agents, recipes, or routers.
- **Router documentation:** `{CONTEXT_DIR}/{COMPANY_DOC_PREFIX}superagent.md` § Router Architecture and Builder — Router usage, building, architecture, and router types.
