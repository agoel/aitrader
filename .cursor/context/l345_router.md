## IMPORTANT: Context Discovery and Loading (Run First Every Turn)

When the user prompts something, use **user context in Cursor memory** + **the prompt** to understand what topics the request belongs to. Based on those topics, discover the relevant agents and their sections/sub-sections. Produce a **loadable context summary** for the Cursor agent and **load it before running further**.

**Portable L345 bundle:** This workspace ships **only** the markdown files under **`.cursor/context/`** listed in the Topic Router below. **No download or hosted install** — the stack is repo-local. There is **no** domain **`router.md`** here unless you add it. Do not assume other agent filenames exist; add missing **`.md`** files to the repo if routing references them.

**Expert pushback (mandatory):** User may be an expert elsewhere—**still assume non-expert for this stack**. Push back **most aggressively at requirements** (highest ambiguity); less at design; least at execution. **Stop before edits** on vague spec or skipped stages. **lsai_subagents.md** § **Recipe of Recipes** → **Expert pushback (mandatory — agent is the expert)**.

**Recipe reuse and DRY (mandatory):** Before writing or editing procedure prose, scan **# Recipe index (canonical)** below. **Reuse** an indexed recipe (load its section and follow it); **compose** via parent **Child recipes**; **extend** only when the delta is small. **Do not** duplicate **Run:** / **Verify:** blocks across files—cite or split into a child recipe. When designing a new recipe, **modularize aggressively**—propose child recipes for reusable sub-flows. **lsai_subagents.md** § **Recipe of Recipes** → **DRY, deduplication, and modularization (mandatory)**.

**Agent vision (check before proceeding):** Before planning, coding, or tool execution, verify that all required **agent vision dimensions** are aligned with the prompt. See **lsai_superagent.md** § **Router Architecture and Builder** → **### Agent vision** for the full table: (A) code diff, (B) uncommitted changes, (C) agent context, (D) session history, (E) run/build output, (F) test output, (G) UI. If something required is ambiguous (e.g. which branch to diff), **push back** before acting—not a silent guess.

**Recipe documentation cadence:** During multi-round harness loops, update **logs and scratch artifacts** after each round; **defer** bulk edits to curated **`.cursor/context/*.md`** until the pass stops, then batch-update once. Full rule: **lsai_superagent.md** § **Router Architecture and Builder** → **### Recipe documentation cadence**.

**Project interaction log (mandatory every turn):** Resolve **`{run_slug}`** (**lsai_subagents.md** § **Recipe of Recipes** → **Run slug identification**; **repo_overview.md** § **Active run**). Log at **`~/data/{project_slug}/runs/{run_slug}/interaction_log.md`**. **Resume** same run—**never overwrite**; if missing, create with **full header**. Prepend per **Prepend algorithm** — **lsai_superagent.md** § **Recipe — Project interaction log (every turn)** (read entire file first; do not truncate). **Question:** verbatim; **Response:** summary.

**Important:** Even for L2-style implementation work, load **coding standards**, **MR guidelines**, and **sub-agent template** context when the task touches process, tests, or MR text. For L3 work (authoring or restructuring agents), **`lsai_subagents.md`** is primary.

### Steps to Discover and Load Context

1. **Extract the goal** from the prompt and session.
2. **Match the goal to 2–10 topics** from the **Topic List** below (semantic match; use weights as a hint only).
3. **Look up** each topic under **# Topic Router** and collect `agent.md | section: …` lines.
4. **Build a loadable context summary** (group by file; list sections).
5. **Load** those files from **`.cursor/context/`** before planning or coding.
6. **Interaction log:** At response end, prepend the turn block per **Project interaction log** above (do not skip for L2-only tasks).

### Topic List

agent creation (6)
agent template (5)
alpha beta gamma testing (5)
clippable mr (5)
coding standards (5)
design update (5)
e2e environments (5)
git merge context docs (4)
git MR format (5)
layered implementation (5)
MR closeout (3)
overview (4)
recipe structure (5)
recipe formal parameters (5)
recipe RSI (5)
recipe self healing (4)
expert pushback (5)
layered MR slug pack (5)
mr slug pack (5)
router building (5)
sub-agent design (5)
superagent install (3)
stack bootstrap (5)
repo layout (4)
git review context (3)
bidirectional citation (3)
agentic merge (3)
agent brain map html producer (2)
base l345 agents refresher (2)
router update (2)
test section update (2)
MR anti-pattern warnings (2)
steps vs tasks terminology (2)
MR step status update (2)
design vs MR bug tracking boundary (2)
duplicate MR sections prevention (2)
agent corruption prevention (2)
core concepts layered work (2)
superagent paper (2)
recipe documentation cadence (2)
stack bootstrap portable (2)
l345 router self (1)
project interaction log (5)
recipe reuse DRY (5)
recipe modularization (4)

### Example

**User prompt:** "Create a new sub-agent for the Foo domain."

**Topics:** agent creation, agent template, sub-agent design.

**Loadable context:**
```
lsai_subagents.md: Recipe of Recipes ((1) How a recipe should look like); Document Structure ((a) Design Section, (b) Project MR Tracking)
coding_standards.md: Related Files (Sub-agent template)
git_mr_guidelines.md: Sections
```

---

# Recipe index (canonical — reuse before rewrite)

**Purpose:** Single lookup for shipped recipes and reusable patterns. Routers **index**; agent docs **own** bodies. When adding or renaming `## Recipe — …`, update this table and add a matching **Topic Router** cluster (or extend an existing one). Domain-only recipes belong in **`router.md`** § **Recipe index** when you add product agents.

| Name | Type | Owner | Section / pattern | Use when |
|------|------|-------|-------------------|----------|
| Stack bootstrap (portable) | recipe | `lsai_superagent.md` | `## Recipe — Stack bootstrap (portable)` | First-time portable stack; fill `repo_overview`, create run folder + log |
| Project interaction log (every turn) | recipe | `lsai_superagent.md` | `### Recipe — Project interaction log (every turn)` | Every turn; prepend to per-run log |
| Base L345 agents refresher | recipe | `docs/operator/l345_sanitizer.md` | `# Recipe — Base L345 agents refresher` | Sanitize bundle agents into `base_l345/` (operator) |
| Agentic merge (agent .md conflicts) | recipe | `agentic_merge.md` | `# Recipe — Agentic merge (agent .md conflicts)` | Resolve merge conflicts in context `.md` files |
| Router templates (build_router.py) | operator | `docs/operator/router_templates.md` | full file | Stamp `router.md` / `l345_router.md` |
| Router scripts (portable) | operator | `.cursor/scripts/` | `copy_template.sh`, `bootstrap_portable.sh`, `refresh_l345_router.sh` | New project (no `.git`); bootstrap; optional router refresh |
| Agent brain map HTML producer | recipe | `lsai_subagents.md` | `## Recipe — Agent brain map HTML producer` | HTML outline viewer for sub-agent `.md` |
| Clippable MR generation (git paste) | recipe | `lsai_subagents.md` | `## Recipe — Clippable MR generation (git paste)` | Export MR text for review paste |
| Layered MR slug pack | recipe | `lsai_subagents.md` | `## Recipe — Layered MR slug pack` | Spec → design → execution tracks under `runs/{run_slug}/` |
| Layer/step status table | recipe | `git_mr_guidelines.md` | `## Recipe — Layer/step status table` | Update MR layer/step status rows |
| Alpha harness (local API) | pattern | `lsai_e2e.md` | `## Alpha harness for local API testing (pattern)` | Localhost interstitial loop, `run_rest`-style |
| Beta / staging remote ops | pattern | `lsai_e2e.md` | `## Beta / staging — remote operations recipe (pattern)` | Deploy, babysit, remote logs on staging |
| Recipe structure & composition | meta | `lsai_subagents.md` | `Recipe of Recipes` → **DRY**, **Parent and child recipes**, **Formal parameters** | Authoring, splitting, citing recipes |
| Slice-first performance gate (data pipelines) | recipe | `lsai_subagents.md` | `## Recipe — Slice-first performance gate (data pipelines)` | Profile small slice, fix hot path, then full batch |
| Router Builder | meta | `lsai_superagent.md` | `Router Architecture and Builder` → **Router Builder Recipe** | L4 topic index generation |

**Run:** Match user goal → row above → load owner section only. **Verify:** No new inline procedure duplicates an indexed **Run** block without a child-recipe cite.

---

# Topic Router

### recipe reuse DRY

- l345_router.md | section: # Recipe index (canonical — reuse before rewrite)
- lsai_subagents.md | section: Recipe of Recipes | sub-section: ### DRY, deduplication, and modularization (mandatory)
- lsai_subagents.md | section: Recipe of Recipes | sub-section: (2) How to extract a set of recipes from existing agents
- lsai_superagent.md | section: Router Architecture and Builder | sub-section: ### Router usage (CRITICAL)

### recipe modularization

- lsai_subagents.md | section: Recipe of Recipes | sub-section: ### Parent and child recipes (composition)
- lsai_subagents.md | section: Recipe of Recipes | sub-section: ### DRY, deduplication, and modularization (mandatory)
- l345_router.md | section: # Recipe index (canonical — reuse before rewrite)

### agent creation

- lsai_subagents.md | section: Recipe of Recipes | sub-section: (1) How a recipe should look like
- lsai_subagents.md | section: Core Concepts: Layered Work and Routing
- lsai_superagent.md | section: Router Architecture and Builder | sub-section: ### Agent vision

### agent template

- lsai_subagents.md | section: Recipe of Recipes | sub-section: (1) How a recipe should look like
- lsai_subagents.md | section: Document Structure
- coding_standards.md | section: Related Files | sub-section: ### Sub-agent template

### alpha beta gamma testing

- lsai_e2e.md | section: Stages (typical meanings)
- lsai_e2e.md | section: Alpha harness for local API testing (pattern)
- lsai_e2e.md | section: Beta / staging — remote operations recipe (pattern)
- coding_standards.md | section: Alpha, Beta, Gamma testing (recipes)
- lsai_subagents.md | section: Document Structure | sub-section: ### (b) Project MR Tracking

### clippable mr

- lsai_subagents.md | section: Recipe — Clippable MR generation (git paste)
- lsai_subagents.md | section: Recipe of Recipes | sub-section: ## Recipe — Layered MR slug pack
- git_mr_guidelines.md | section: Clippable MR export (preflight — mandatory)
- git_mr_guidelines.md | section: Sections
- git_mr_guidelines.md | section: Global layer numbering (read first) | sub-section: ### Layered Implementation Sequence (for complex projects)

### coding standards

- coding_standards.md | section: Overview
- coding_standards.md | section: Cross-cutting rules
- coding_standards.md | section: Related Files

### design update

- lsai_subagents.md | section: Document Structure | sub-section: ### (a) Design Section
- lsai_subagents.md | section: Document Structure | sub-section: ### (b) Project MR Tracking
- git_mr_guidelines.md | section: Sections

### e2e environments

- lsai_e2e.md | section: Principles (product-agnostic)
- lsai_e2e.md | section: Interstitial loop (one “layer” of work)
- lsai_e2e.md | section: Org template — plug in **your** alpha harness
- coding_standards.md | section: Alpha, Beta, Gamma testing (recipes)

### git merge context docs

- lsai_subagents.md | section: How to do Agentic Merge when there is conflict in Agents .md while merging

### agentic merge

- lsai_subagents.md | section: How to do Agentic Merge when there is conflict in Agents .md while merging
- lsai_subagents.md | section: Recipe of Recipes | sub-section: ## Recipe — Layered MR slug pack

### git MR format

- git_mr_guidelines.md | section: Sections
- git_mr_guidelines.md | section: Recipe — Layer/step status table
- git_mr_guidelines.md | section: Title
- lsai_subagents.md | section: Recipe — Clippable MR generation (git paste)
- lsai_superagent.md | section: Router Architecture and Builder | sub-section: ### Router usage (CRITICAL)

### layered implementation

- git_mr_guidelines.md | section: Global layer numbering (read first)
- git_mr_guidelines.md | section: Global layer numbering (read first) | sub-section: ### Layered Implementation Sequence (for complex projects)
- lsai_subagents.md | section: Document Structure | sub-section: #### Layered Implementation sequence
- lsai_subagents.md | section: Document Structure | sub-section: #### Layered implementation and per-layer E2E checkpoints

### MR closeout

- lsai_subagents.md | section: How to clean up MR section AFTER the release is ready to ship: user can ask for "close out MR"
- git_mr_guidelines.md | section: Global layer numbering (read first) | sub-section: ### Layered Implementation Sequence (for complex projects)
- lsai_e2e.md | section: Change-request / MR reporting: remote stages (template)

### overview

- repo_overview.md | section: (a) Design Section | sub-section: ### Overview
- repo_overview.md | section: (a) Design Section | sub-section: ### Git and review context
- coding_standards.md | section: Overview

### git review context

- repo_overview.md | section: (a) Design Section | sub-section: ### Git and review context
- git_mr_guidelines.md | section: Clippable MR export (preflight — mandatory)
- lsai_subagents.md | section: Recipe — Clippable MR generation (git paste)

### recipe structure

- lsai_subagents.md | section: Recipe of Recipes | sub-section: (1) How a recipe should look like
- lsai_subagents.md | section: Recipe of Recipes | sub-section: ### Structure
- lsai_subagents.md | section: Recipe of Recipes | sub-section: ### DRY, deduplication, and modularization (mandatory)
- lsai_subagents.md | section: Recipe of Recipes | sub-section: ### Parent and child recipes (composition)
- l345_router.md | section: # Recipe index (canonical — reuse before rewrite)

### recipe formal parameters

- lsai_subagents.md | section: Recipe of Recipes | sub-section: ### Formal parameters (L4-defined)
- lsai_subagents.md | section: Recipe of Recipes | sub-section: ### Run workspace (`~/data/{project_slug}/runs/{run_slug}/`)
- lsai_subagents.md | section: Recipe of Recipes | sub-section: ### Run slug (`{run_slug}`) identification
- lsai_subagents.md | section: Recipe of Recipes | sub-section: ### CoT step headings and backtrack
- lsai_subagents.md | section: Recipe of Recipes | sub-section: ### Expert pushback (mandatory — agent is the expert)
- lsai_subagents.md | section: Recipe of Recipes | sub-section: ### Parent and child recipes (composition)
- lsai_subagents.md | section: Recipe of Recipes | sub-section: ### Interaction log on resume (never overwrite)
- lsai_superagent.md | section: Router Architecture and Builder | sub-section: ### Router Builder Recipe

### recipe RSI

- lsai_subagents.md | section: Recipe of Recipes | sub-section: ### RSI — recursive self-improvement (one type per recipe)

### recipe self healing

- lsai_subagents.md | section: Recipe of Recipes | sub-section: ### Self-healing

### expert pushback

- lsai_subagents.md | section: Recipe of Recipes | sub-section: ### Expert pushback (mandatory — agent is the expert)
- lsai_subagents.md | section: Core Concepts: Layered Work and Routing
- lsai_superagent.md | section: Router Architecture and Builder | sub-section: ### Expert pushback (CRITICAL)
- coding_standards.md | section: Cross-cutting rules

### layered MR slug pack

- lsai_subagents.md | section: Recipe of Recipes | sub-section: ## Recipe — Layered MR slug pack
- git_mr_guidelines.md | section: Sections
- repo_overview.md | section: (a) Design Section | sub-section: ### MR slug packs

### mr slug pack

- lsai_subagents.md | section: Recipe of Recipes | sub-section: ## Recipe — Layered MR slug pack
- lsai_subagents.md | section: How to do Agentic Merge when there is conflict in Agents .md while merging
- repo_overview.md | section: (a) Design Section | sub-section: ### MR slug packs

### router building

- lsai_superagent.md | section: Router Architecture and Builder
- lsai_superagent.md | section: Routing and the L345 router

### sub-agent design

- lsai_subagents.md | section: Core Concepts: Layered Work and Routing
- lsai_subagents.md | section: Document Structure | sub-section: ### (a) Design Section

### stack bootstrap

- lsai_superagent.md | section: Portable stack (this bundle)
- lsai_superagent.md | section: Recipe — Stack bootstrap (portable)
- repo_overview.md | section: (a) Design Section | sub-section: ### Active run
- repo_overview.md | section: (a) Design Section | sub-section: ### Project interaction log (per run)
- repo_overview.md | section: (a) Design Section | sub-section: ### Git and review context

### superagent install

- lsai_superagent.md | section: Recipe — Stack bootstrap (portable)
- lsai_superagent.md | section: Portable stack (this bundle)

### repo layout

- repo_overview.md | section: (a) Design Section
- repo_overview.md | section: (a) Design Section | sub-section: ### Technical Implementation Details

### bidirectional citation

- lsai_subagents.md | section: CRITICAL: Load router context first (see lsai_superagent.md)
- coding_standards.md | section: Related Files | sub-section: ### Bidirectional citation rule

### agent brain map html producer

- lsai_subagents.md | section: Recipe — Agent brain map HTML producer

### base l345 agents refresher

- lsai_superagent.md | section: Router Architecture and Builder | sub-section: ### Recipe — Base L345 agents refresher (sanitization workspace)

### router update

- lsai_superagent.md | section: Router Architecture and Builder | sub-section: ### Router Builder Recipe

### test section update

- git_mr_guidelines.md | section: Global layer numbering (read first) | sub-section: ### Alpha Testing
- git_mr_guidelines.md | section: Global layer numbering (read first) | sub-section: ### Beta Testing
- lsai_subagents.md | section: Document Structure | sub-section: #### Alpha Testing

### MR anti-pattern warnings

- git_mr_guidelines.md | section: Global layer numbering (read first) | sub-section: ### MR structure guardrails (hard requirements)
- git_mr_guidelines.md | sub-section: ### Do NOT do these (common MR failures)

### steps vs tasks terminology

- lsai_subagents.md | section: Core Concepts: Layered Work and Routing
- git_mr_guidelines.md | section: Global layer numbering (read first) | sub-section: ### Layered Implementation Sequence (for complex projects)

### MR step status update

- lsai_subagents.md | section: Document Structure | sub-section: #### Updating Step Status
- git_mr_guidelines.md | section: Recipe — Layer/step status table

### design vs MR bug tracking boundary

- lsai_subagents.md | section: Document Structure | sub-section: ### (b) Project MR Tracking
- git_mr_guidelines.md | section: Global layer numbering (read first) | sub-section: ### MR structure guardrails (hard requirements)

### duplicate MR sections prevention

- git_mr_guidelines.md | sub-section: ### Do NOT do these (common MR failures)
- lsai_subagents.md | section: Document Structure | sub-section: ### (b) Project MR Tracking

### agent corruption prevention

- git_mr_guidelines.md | section: Clippable MR export (preflight — mandatory)
- lsai_subagents.md | section: Recipe — Clippable MR generation (git paste)

### core concepts layered work

- lsai_subagents.md | section: Core Concepts: Layered Work and Routing
- lsai_superagent.md | section: Core ideas (from the public SuperAgent paper)

### superagent paper

- lsai_superagent.md | section: Core ideas (from the public SuperAgent paper)
- lsai_superagent.md | section: ### Further reading (public)
- lsai_subagents.md | section: ### SuperAgent outside-world narrative (pointer)

### recipe documentation cadence

- lsai_superagent.md | section: Router Architecture and Builder | sub-section: ### Recipe documentation cadence (curated `.md` vs per-iteration data)

### stack bootstrap portable

- lsai_superagent.md | section: Recipe — Stack bootstrap (portable)
- lsai_superagent.md | section: Portable stack (this bundle)

### l345 router self

- l345_router.md | section: IMPORTANT: Context Discovery and Loading (Run First Every Turn)
- l345_router.md | section: # Recipe index (canonical — reuse before rewrite)
- l345_router.md | section: # Topic Router

### project interaction log

- repo_overview.md | section: (a) Design Section | sub-section: ### Active run
- repo_overview.md | section: (a) Design Section | sub-section: ### Project interaction log (per run)
- lsai_superagent.md | section: Router Architecture and Builder | sub-section: ### Recipe — Project interaction log (every turn)
- l345_router.md | section: IMPORTANT: Context Discovery and Loading (Run First Every Turn)
