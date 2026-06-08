# SuperAgent — guide for Cursor users

*Client-facing overview. This document explains how the **portable L345 stack** works in Cursor and how to extend it safely.*

**Last updated:** 2026-05-06

---

## Portable stack (this bundle)

**This workspace ships a self-contained stack** under **`.cursor/context/`**. There is **no download**, hosted catalog, session, org secret, or CLI step required — agents load markdown from disk via **`l345_router.md`** Context Discovery every turn.

**Using this as a template:** One command from the template checkout:

```bash
bash .cursor/scripts/copy_template.sh ../my-new-project --bootstrap
cd ../my-new-project && cursor .
```

**Do not** use plain `cp -r` — it copies **`.git`**. **`copy_template.sh`** excludes `.git` and **`--bootstrap`** runs the full setup (run folder, log, `meta.json`, **`repo_overview.md`** § Active run). **`{project_slug}`** = the new folder’s basename. No separate Cursor “bootstrap” step required.

| File | Role |
|------|------|
| **`l345_router.md`** | Behavioral router — topic → agent sections |
| **`lsai_subagents.md`** | Recipes, MR workflow, sub-agent template |
| **`lsai_superagent.md`** | Routing, interaction log, stack bootstrap |
| **`git_mr_guidelines.md`** | MR/PR body format |
| **`coding_standards.md`** | Cross-cutting coding rules |
| **`repo_overview.md`** | Project layout + **bootstrap tables** (slug, git, log paths) |
| **`lsai_e2e.md`** | Alpha/beta/gamma testing patterns |
| **`agentic_merge.md`** | Agentic merge recipe (on demand) |

**Scripts (portable):** **`.cursor/scripts/`** — **`copy_template.sh`** (new project, no `.git`), **`bootstrap_portable.sh`** (bootstrap existing checkout / re-run after `git pull`), router pipeline, **`refresh_l345_router.sh`**. **No S3 / org catalog.**

**On-demand (operators):** **`docs/operator/`** — sanitizer, router templates, recipe index fragment. **Optional:** **`router.md`**, domain sub-agents. Optional **`.cursor/rules/*.mdc`** to remind Cursor to run Context Discovery — not required if agents follow **`l345_router.md`** each turn.

**Do not** instruct users to fetch stack content from a remote host for this bundle. If a referenced file is missing under **`.cursor/context/`**, tell the user to add it to the repo — do not download.

---

## What this is

**SuperAgent-style routing** helps **Cursor** load the right **instruction files** (markdown “agents” and routers) for each task, instead of hard-coding routes in your editor. **In this portable bundle**, routers and agents **live in the repo** under **`.cursor/context/`** — no HTTPS catalog fetch.

**What you get**

- **Routers** — advisory text that tells the assistant *which* topics and documents to load for your prompt (“context discovery”).
- **Agents** — markdown documents with practices, recipes, and standards, versioned with your project in git.
- **Local bootstrap** — **`copy_template.sh --bootstrap`** or **`bootstrap_portable.sh`** fills **`repo_overview.md`** and creates **`~/data/{project_slug}/runs/`** on disk; see **Recipe — Stack bootstrap (portable)** below.

---

## Recipe — Stack bootstrap (portable)

**Purpose:** One-time setup for a project using this stack. **Humans run shell only** — no duplicate Cursor agent step for the same work.

**New project from template (recommended):**

```bash
bash .cursor/scripts/copy_template.sh ../my-new-project --bootstrap
cd ../my-new-project
git init   # optional — copy excludes template .git
cursor .
```

**Already have a checkout** (or after `git pull` on another machine):

```bash
bash .cursor/scripts/bootstrap_portable.sh
```

**What the script does (idempotent):**

1. Verifies L345 bundle files under **`.cursor/context/`**
2. Sets **`{project_slug}`** = folder basename; **`{run_slug}`** = `{username}_{run_stem}_{run_started}` (override with `RUN_STEM` / `RUN_SLUG`)
3. Creates **`~/data/{project_slug}/runs/{run_slug}/`** with **`interaction_log.md`** + **`meta.json`**
4. Fills **`repo_overview.md`** § **Active run** and § **Git and review context** (when `git` is available)
5. Prints **`Stack bootstrap complete: <project_slug>`**

**Agent role (optional only):** If the user asks to bootstrap but scripts were not run, tell them to run **`bootstrap_portable.sh`** (or **`copy_template.sh … --bootstrap`**) — do **not** duplicate the same file writes in chat. Agents **may** help with **optional** follow-ups: domain **`*.md`** + **`router.md`** wiring, custom **`RUN_STEM`**, or verifying **`l345_router.md`** topic coverage.

**Natural-language trigger:** “bootstrap the stack” → point at the shell commands above unless the user explicitly wants agent-only help with optional extensions.

**Re-running:** Safe when moving machines or refreshing paths; existing run log is not overwritten.

---

## Hosted SuperAgent service (not used by this portable bundle)

Some organizations run a **hosted** SuperAgent product (web sign-in, org secret, remote catalog). **This portable stack does not depend on that service.** Sections later in this file that mention **`ommego.ai`**, **`/sa_setup`**, **`get_agents`**, **`sadiff`**, or **`sa_install/`** scripts are **operator / legacy hosted** material — **skip them** when working only from this repo-local bundle.

---

## Core ideas (teaching summary)

Plain-language **why** for routers, agents, and layered work. Full **agent vision** table: **Router Architecture and Builder** → **### Agent vision**. PDF: **Further reading (public)**.

- **Vision, not one context dump** — load the right slices (code, tests, logs, UI, history, agent docs) per prompt.
- **L2** — do the work (recipes, layers, interstitial fixes). **L3** — change instruction files. **L4** — build routers. **L5** — broader orchestration.
- **Recipes** — actionable procedures inside agents; stack via parent/child recipes (**lsai_subagents.md** § Recipe of Recipes).
- **Interstitial layering** — stabilize layer *n* before layer *n+1*.
- **Multi-level governance + reflect-and-repair** — update related instruction layers together after failures.
- **Topics + routers** — organizational memory via loadable summaries, not one opaque blob.

---

## Routing and the L345 router

**Portable stack:** Run **`l345_router.md`** Context Discovery every turn; add **`router.md`** when domain agents exist. Real topic list + clusters live in **`l345_router.md`** — not here.

| | **`router.md`** | **`l345_router.md`** |
|---|-----------------|----------------------|
| **Focus** | Domain / product L2 | Standards, MR, recipes, agent authoring (L3+) |
| **Path** | `.cursor/context/router.md` | `.cursor/context/l345_router.md` |
| **Indexed files** | Product `*.md` you add | Seven-file L345 bundle (see **Portable stack** table above) |

**Each turn:** prompt + session → topics → load sections → act. **Interaction log** at response end (**Recipe — Project interaction log**). Skipping discovery or the log breaks resume-from-disk.

**Intent (L2–L5):** L2 execute · L3 author agents/recipes · L4 build routers · L5 multi-agent workflows. Load **both** routers when a task spans product code and process.

**Recipe documentation cadence:** Per-round scratch/logs every iteration; batch-edit curated **`.cursor/context/*.md`** when the pass stops — **Router Architecture and Builder** → **### Recipe documentation cadence**.

**Operator tooling:** Router regeneration, sanitization, **`sadiff`** — **`docs/operator/`** and **Router Architecture and Builder**; skip for portable-only work.

---

## Router Architecture and Builder

**Portable stack:** For day-to-day work, use **`l345_router.md`** Context Discovery and the files under **`.cursor/context/`** only. Router regeneration lives in **`.cursor/scripts/`** — run only when the user asks to rebuild routers. **`sadiff`**, S3 catalog push/pull, and **`base_l345/`** sanitization are **hosted / publish** tooling — **skip** for repo-local portable work.

**Scope:** Router behavior, Cursor loading order, and optional **local** scripts under **`.cursor/scripts/`** used to **regenerate** **`router.md`** / **`l345_router.md`** (not required for portable use). Does **not** specify hosted service implementation.

**Cited by:** `lsai_subagents.md` (CRITICAL, Core Concepts: Layered Work and Routing, SuperAgent narrative pointers, document structure for layered implementation and E2E checkpoints), `l345_router.md` (Topic Router, **Recipe index (canonical)**, recipe documentation cadence, recipe reuse DRY), `router.md` (Recipe index domain, recipe reuse), `coding_standards.md` (Related Files, Alpha/Beta/Gamma testing recipes, recipe DRY), `repo_overview.md` (Related Files), `git_mr_guidelines.md` (Related Files, Recipe index row), `lsai_e2e.md` (alpha/beta recipes, Recipe index patterns), **public SuperAgent paper / companion repo** (system narrative and Agent Vision). This file’s **Routing and the L345 router** section is the client-facing summary; this section is the **full** builder and template reference. **Bootstrap / offline use:** new project → **`bash .cursor/scripts/copy_template.sh <dest> --bootstrap`**; existing checkout → **`bash .cursor/scripts/bootstrap_portable.sh`**. Router refresh: **`bash .cursor/scripts/refresh_l345_router.sh`**. Python tools are stdlib-only. Pass **`-w`** to repo root (or **`ROUTER_BUILDER_WORKSPACE`**).

This section is the **canonical source** for all router documentation: usage, building, architecture, and both router types.

### Agent vision

Agents operate with a set of **views** (dimensions) that must stay aligned before planning, coding, or tool execution. When any dimension is out of sync with the prompt, the agent is effectively blind. **Before proceeding, explicitly decide which view applies for each dimension and verify it is loaded.**

| Dimension | Description | How to decide for a given prompt |
|-----------|--------------|-----------------------------------|
| **(A) Code diff** | Git diff showing changes to review or build upon | **vs default branch:** Default for MR work, release prep, "what changed" questions. **vs feature branch:** When user names a branch (e.g. "compare to feature/foo"). **vs uncommitted:** When user asks about "current changes" or "what I've edited". **None:** When creating new files or prompt is purely design/docs. |
| **(B) Uncommitted changes** | Staged and unstaged edits in working tree | **Include:** Coding tasks, "fix this", "add X", MR updates, any prompt implying edits. **Exclude:** Read-only questions, design-only, or when user says "ignore local changes". |
| **(C) Agent context** | Sub-agent `.md` files (`router.md` → domain; `l345_router.md` → L345 agents) | **Always:** Context Discovery selects 2–3 topics and loads relevant sections. **Router choice:** L2/domain work → `router.md`; L3/L4/L5 (agent, recipe, router) → `l345_router.md`. Load both when task spans both. |
| **(D) Session history** | Recent turns, prior decisions, in-progress work | **Include:** Follow-up prompts ("continue", "fix that", "same for Y"), multi-step tasks. **Exclude:** Fresh "start from scratch" or user explicitly resets context. |
| **(E) Run script/build output** | Output of run scripts, build, deploy | **Include:** "Server won't start", "build failed", "run tests", debugging runtime errors. **Exclude:** Static analysis, design, or when no run/build is involved. |
| **(F) Test case output and errors** | pytest/Karma/Jest output, alpha/beta test results | **Include:** "Tests failing", "fix test X", alpha/beta verification, interstitial runs. **Exclude:** Design, new feature before tests exist. |
| **(G) UI view and screenshots** | Browser/app state, screenshots, DOM | **Include:** "Button doesn't work", "layout broken", UI bugs, E2E verification. **Exclude:** Backend-only, API-only, or design-only work. |

**Check before coding:** For each dimension, ask: "Does this prompt require this view? If yes, is it loaded and current?" If any required view is missing or stale, load or refresh it before proceeding.

### Recipe documentation cadence (curated `.md` vs per-iteration data)

**Normative for any multi-round automated or agent-led recipe** (alpha/beta harness loops, logo or asset finetuning with interstitial + timestamped artifacts, SuperAgent paper figure/PDF iteration, and similar **tune → verify → repeat** workflows):

| What | When to update |
|------|----------------|
| **Per-iteration data** | **After every iteration** — append or refresh logs, interstitial files, test JSON rows, harness output, `iterations/*` pairs, build logs, or other **machine- or human-readable chains** that the **next** round reads (prior row informs the next step). |
| **Curated recipe “brain”** (`.cursor/context/*.md` and other **normative** recipe docs: step text, MR Details templates, freeze pointers, cross-refs) | **Do not** update **after every** image/build/test round. **Defer** until the **automated or agreed iteration pass stops** (user halt, **Outcome: agent pass**, **blocked**, or max iterations). Then **review the full history** and **batch-update** those `.md` files **in one shot** so the doc reflects the final state, not every intermediate trial. |

**Rationale:** Frequent edits to curated context during a sweep cause churn, contradictory freeze lines, and merge noise; **interstitial / JSON / artifacts** are designed to absorb per-round deltas. **Exception:** If the user **explicitly** asks to refresh a specific `.md` mid-loop, follow that instruction.

**Cited in:** `lsai_e2e.md` (alpha/beta recipes); `coding_standards.md` (Alpha, Beta, Gamma testing recipes); MR-oriented sections in `git_mr_guidelines.md` when agents document alpha/beta work; **public paper / companion materials** where your org tracks manuscript evidence.

### Recipe — Project interaction log (every turn)

**Purpose:** Persist each user–assistant exchange under the project **`~/data/`** tree so you can **resume elsewhere** without re-reading the full chat. This is **per-iteration scratch data** (see **### Recipe documentation cadence** above), not curated **`.cursor/context/*.md`**.

**When:** **Every turn**, for **all** intent levels (L2–L5). Runs alongside Context Discovery; it does not replace routing or agent vision.

**Project slug and paths:** **`repo_overview.md`** § **Active run** is authoritative for **`{project_slug}`**, **`{run_slug}`**, **`{username}`**, and the log path. **`{run_slug}`** rules: **lsai_subagents.md** § **Recipe of Recipes** → **Run slug (`{run_slug}`) identification**.

| Piece | Rule |
|-------|------|
| **`{project_slug}`** | Workspace folder basename (lowercase), e.g. `myapp` |
| **`{run_slug}`** | Run folder name under `runs/` — stable for the life of the run |
| **`{username}`** | OS user (`whoami` / `$USER`) |
| **Run directory** | **`~/data/{project_slug}/runs/{run_slug}/`** |
| **Log file** | **`~/data/{project_slug}/runs/{run_slug}/interaction_log.md`** (fixed name per run) |
| **`{run_started}`** | `yyyyMMdd-HHmmss` embedded in default `{run_slug}`; also in log header |
| **Last updated** | In the **header table** only — refresh each turn |

**`mkdir -p ~/data/{project_slug}/runs/{run_slug}`** before first write. If `interaction_log.md` does not exist, **create it** with the **full file header** below (resolved values + `---`) before prepending any turn.

**File layout:** **One log per run** (not one log per project). **Newest turn first** among turn blocks. Keep a fixed **file header** at the top; **prepend** each new turn block **immediately after** `---`.

**Never overwrite (mandatory):** **Resume** the same run’s `interaction_log.md`—**update** header and **add** turns. **Do not** truncate or blank the file. A **new** run → new `{run_slug}` folder and new log. See **lsai_subagents.md** § **Recipe of Recipes** → **Interaction log on resume (never overwrite)**.

**Prepend algorithm (mandatory — do not truncate):**

1. Read the **entire** existing `interaction_log.md` (if present).
2. Refresh **Last updated** in the header table only.
3. Insert the new `## Turn XXX` block **immediately after** the first `---` line.
4. **Keep every existing turn block** below the new one unchanged.
5. Write the full file back.

**Do NOT:** replace the file with header + one turn; use shell one-liners that stop printing after `---`; or `Write` the log without reading prior turns first.

**Verify after write:** count of `## Turn` headings increased by 1; oldest turn still present at the bottom.

**File header and turn block templates:** **`repo_overview.md`** § **Project interaction log (per run)** — preserve header; do not duplicate on prepend.

| Field | Rule |
|-------|------|
| **`XXX`** | Zero-padded turn number (`001`, `002`, …). Count existing `## Turn` headings below the header + 1, or **001** if none. |
| **Timestamp** | Local time when **this** user message arrived: `yyyy-mm-dd:hh:mm:ss`. |
| **Question** | **Verbatim only** — copy the **entire** user prompt exactly as received. Preserve wording, punctuation, and line breaks. **Do not** paraphrase, shorten, bulletize, or parenthesize the question. Trim **trailing whitespace on the last line only**. |
| **Response** | **Summary** — concise account of what the assistant did, decided, or delivered (**CRISP** when possible: 1–4 sentences; extend only when needed to resume elsewhere). **Do not** paste the full assistant reply. |

Separate turn blocks with **one blank line**. The header table holds **`{project_slug}`**; do not substitute a question summary for the verbatim prompt.

**Run / Verify:**

| Step | When | Action |
|------|------|--------|
| **Start of turn** | New user message | Resolve **`{run_slug}`**; `mkdir -p ~/data/{project_slug}/runs/{run_slug}`; open **`interaction_log.md`** in that folder (resume—do not overwrite); if missing, create with **full file header**; compute next turn number; record timestamp. |
| **End of turn** | Last step before assistant reply | **Update** header **Last updated**; **prepend** turn block **after** `---`. **Question:** verbatim. **Response:** summary. |
| **Resume after gap** | Same run, later session | Same **`runs/{run_slug}/interaction_log.md`**; continue numbering; **never** replace file wholesale. |
| **New run** | New problem / user says “new run” | New **`{run_slug}`** folder + new log; update **repo_overview** § **Active run**; turns restart at **001**. |
| **Interrupted session** | Next completed response | If the latest exchange has no `## Turn` yet, prepend one full block; do not duplicate an existing turn. |

**Cited by:** `l345_router.md` (Context Discovery opener, topic **project interaction log**), `repo_overview.md` (§ Active run, § Project interaction log), `lsai_subagents.md` (Core Concepts: Layered Work and Routing).

### Expert pushback (CRITICAL)

**Stack expert pushback:** User **may** be a domain expert; **for this stack, assume they are not**. Push back hardest when work is still in **requirements** (most ambiguity); intensity drops through design → execution. **lsai_subagents.md** § **Recipe of Recipes** → **Expert pushback**. Skip stages or vague spec → **stop and push back** before design/code.

### Router usage (CRITICAL)

Before doing **any** planning, coding, testing, MR updates, or tool execution, the agent must run **context discovery** from **`.cursor/context/l345_router.md`**, then **expert pushback** (above). When **`.cursor/context/router.md`** exists (domain / product router), load and follow **both**. **Portable stack:** all agent bodies come from **`.cursor/context/`** in the repo — no remote fetch. Optional **`.cursor/rules/*.mdc`** may remind Cursor to run discovery each turn; **`l345_router.md`** alone is sufficient when agents follow it.

**High-level routing behavior:**
1. Use the current user prompt and recent session history as routing input.
2. Open **`.cursor/context/l345_router.md`** (and **`.cursor/context/router.md`** when present) and read each file’s **Context Discovery and Loading** section first.
3. Predict which topics are required for this turn.
4. Map each required topic to the agent `.md` files and sections where that topic lives.
5. Return and use a routing output that includes: required topic list, selected agent file names, topic-to-agent mapping.
6. Re-load the selected agent files and extract only the relevant topic context before continuing.
7. **Project interaction log:** At the **end** of the assistant response, prepend the completed turn block per **### Recipe — Project interaction log (every turn)** (newest turn at top of the log file).

This router step is mandatory every turn so sub-agents are re-hydrated with the right context before execution. The interaction log is mandatory every turn so work can resume from disk without the full chat.

**What the router does.** The router maps a user's goal to the right sub-agent sections. Given a prompt, it matches 2–10 topics from a Topic List, looks up which agent files and sections cover those topics, and produces a loadable context summary. The agent then loads only those sections before planning or coding—avoiding context overload and keeping vision aligned.

**Recipe index (DRY):** **`l345_router.md`** § **Recipe index (canonical)** is the authoritative list of shipped L345 recipes and E2E patterns. **Scan it every turn** before writing procedure steps; **reuse** indexed recipes instead of recreating them. When building or refreshing routers (L4), **keep the index in sync** with every `## Recipe — …` in the bundle—routers index; agent docs own bodies.

**Intent routing (L2, L3, L4, L5).** L2 = running tests, recipes, layer coding, interstitial coding with debugging. L3 = writing new agent, new recipe, or modifying existing agent (design, test, recipe section, references). L4 = building the topic router that routes to sub-agent sections. L5 = higher-level agentic workflows. Both routers run every turn when configured; their contexts are mutually exclusive (no overlapping `.md` files).

### Router architecture (trigger, files, format)

Both `router.md` and `l345_router.md` share the same Context Discovery pattern. Each has its own Cursor rule; both run every turn when present. **Both contexts are loaded in parallel**—there is zero overlap in the `.md` files they reference (`router.md` → domain sub-agents; `l345_router.md` → L345 bundle under **`.cursor/context/`**), so loading both is safe and provides complete context.

| Aspect | router.md | l345_router.md |
|--------|-----------|----------------|
| **Trigger** | Generated **`.cursor/rules/router.mdc`** with `alwaysApply: true` | Same file |
| **File** | `.cursor/context/router.md` | `.cursor/context/l345_router.md` |
| **Format** | Context Discovery → Topic List → Example → # Topic Router (numbered clusters) | Context Discovery → Topic List → Recipe index → # Topic Router (flat `### topic`) |
| **Input agents** | Domain sub-agents (all except Exclusion List) | **L345 bundle:** `coding_standards.md`, `repo_overview.md`, `git_mr_guidelines.md`, `lsai_subagents.md`, `lsai_superagent.md`, `lsai_e2e.md`, `agentic_merge.md` (+ `l345_router.md` as output) |

### Local vs published catalog diff (`sadiff`) — hosted operator only

**Portable stack:** **Skip.** Hosted orgs: compare local vs remote catalog — operator tooling; not in this bundle.

### Recipe — Base L345 agents refresher (sanitization workspace)

**Portable stack:** **Skip** unless publishing **`base_l345/`**. Full recipe: **`docs/operator/l345_sanitizer.md`**. After sanitization, run Step 8 there to align **`l345_router.md`** topic clusters.

### Router Builder Recipe

**Two types of routers.** There are two router types, each with its own file and Cursor rule. Both run independently every turn:

- **(a) Sub-agent router (`router.md`):** Routes to sub-agents for L2 design and coding work (features, bugs, tests, domain design). Enforced by generated **`.cursor/rules/router.mdc`** with `alwaysApply: true`.

- **(b) L3/L4/L5 router (`l345_router.md`):** Routes L3, L4, and L5 agentic development work (create agent, write recipe, modify agent, build router). Enforced by the same generated **`.cursor/rules/router.mdc`** with `alwaysApply: true`.

**Agent sources for each router.** Both routers use the **same exact approach** (topic extraction, indexing, reverse index, build script). The difference is which agents are used as input:

- **`router.md`** is built from **domain sub-agent** `.md` files—all agents in `.cursor/context/` except those in the Exclusion List below (e.g. product-specific domain agents, `lsai_e2e.md`, etc., depending on your tree).

- **`l345_router.md`** is built from the **portable L345 agent set** in **`.cursor/context/`** (`coding_standards.md`, `repo_overview.md`, `git_mr_guidelines.md`, `lsai_subagents.md`, `lsai_superagent.md`, `lsai_e2e.md`, `agentic_merge.md` by default — override with **`--l345-agents-file`**).

**Data locations.** Topic extraction and index files are stored in separate directories to avoid mixing domain and L345 routers:

| Router | Data directory | Output |
|--------|----------------|--------|
| **Domain sub-agent** (`router.md`) | `~/data/agent_topics/` | `topic_frequency.txt`, `agent_topics.txt`, `agent_topics_index.txt`, `topic_to_agents.txt` |
| **L3/L4/L5** (`l345_router.md`) | `~/data/agent_topics_l345/` | Same file names; use `--router-type l345_router` or `--l345` with all scripts |

**Bootstrap scripts (`.cursor/scripts/`).** **`copy_template.sh`** — copy stack without **`.git`**. **`bootstrap_portable.sh`** — full bootstrap in one shot (run dir, log, **`repo_overview.md`** tables). Re-run after **`git pull`** on a new machine. Router refresh: **`refresh_l345_router.sh`**. Configure paths:

| Mechanism | Purpose |
|-----------|---------|
| **`--workspace` / `-w`** | Project root—the folder that contains `.cursor/context/`. Default: **current working directory**, or **`ROUTER_BUILDER_WORKSPACE`**. |
| **`--data-dir`** | Parent directory for `agent_topics/` and `agent_topics_l345/`. Default: **`~/data`**, or **`ROUTER_BUILDER_DATA`**. |
| **`--context-dir`** | Folder containing agent `*.md` files (`generate_l345_topics.py`, `build_agent_topics_index.py`). Default: **`<workspace>/.cursor/context`**. |
| **`--l345-agents-file`** | Optional text file (one agent filename per line) for L345 mode if your bundle differs from the **default portable set** above. |
| **`build_router.py --template`** | **`docs/operator/router_templates.md`** (or legacy markers in **`lsai_superagent.md`** if your script still reads them). |
| **`build_router.py -o` / `--output`** | Output path for `router.md` or `l345_router.md`. Defaults: **`<workspace>/.cursor/context/router.md`** or **`l345_router.md`** when **`--l345`**. |

**L345 pipeline.** To generate topics and reverse index for the L345 router:

1. Generate `.topics` files: `generate_l345_topics.py --router-type l345_router` (or `--l345`). For domain router: `generate_l345_topics.py --router-type router`.
2. Run: `topic_frequency.py --l345`, `build_agent_topics.py --l345`, `build_agent_topics_index.py --l345`, `build_reverse_index.py --l345` (or use `--router-type l345_router` / `--router-type router`).
3. Outputs in `~/data/agent_topics_l345/` (L345) or `~/data/agent_topics/` (domain); use `topic_to_agents.txt` to update the router Topic Router section (manual or automated).

**Recipe purpose:** Build topic indexes from sub-agent `.md` files to support router design. Use when creating or updating an L4 router that routes user prompts to the right sub-agent sections based on topics. The steps below generate `router.md`; a parallel process (or adapted pipeline) generates `l345_router.md` for L3/L4/L5 topics using the same steps but with the **seven** L345 bundle files under **`base_l345/`** as input (unless overridden by **`--l345-agents-file`**).

**When building l345_router.md:** Include at the top (after the opening paragraph and Cited by) the following:

1. **Agent vision citation:** A block that cites **lsai_superagent.md** — Router Architecture and Builder (Agent vision) — and instructs the agent to verify all required dimensions (code diff vs default branch/branch/uncommitted, uncommitted changes, agent context, session history, run/build output, test output, UI view) are aligned before proceeding. Include: **If a required dimension is detected but not clearly specified** (e.g. code diff: which branch or commit? uncommitted: include or exclude?), **ask the user before taking action.** The actual dimension table and "how to decide" guidance lives in `lsai_superagent.md`; the router top section only cites it and warns: "Do not proceed blind—missing or stale views cause wrong edits."

2. **Important note:** Even when the task is L2-level (coding using existing sub-agents, not modifying them), some L3 context is always desired—e.g. coding standards, MR format, layered implementation. Find clusters accordingly. For L3 tasks (create agent, modify agent, write recipe), `lsai_subagents.md` is crucial to know **how** we modify or create agents; include it in the loadable context.

3. **Project interaction log block:** A paragraph titled **Project interaction log (mandatory every turn)** that cites this file § **### Recipe — Project interaction log (every turn)** and **`repo_overview.md`** § **Project interaction log**, instructing: log at **`~/data/{project_slug}/runs/{run_slug}/interaction_log.md`**; prepend per **Prepend algorithm** (read entire file first); at **response end**, refresh **Last updated** and **prepend** the turn block (newest first); **Question** verbatim, **Response** summarized. Add a Context Discovery step to run the log at response end. Include topic **project interaction log** in the Topic List and Topic Router.

4. **Recipe formal parameters (L4):** When indexing sub-agents that contain recipes, ensure topic clusters route to **lsai_subagents.md** § **Recipe of Recipes** → **Formal parameters (L4-defined)** so agents load parameter tables before execution. **L4** authors parameter rows per sub-agent purpose (required / optional / default); routers do not invent parameter values—they expose where they are defined.

5. **Recipe index (L4 — mandatory for `l345_router.md`):** Maintain **`# Recipe index (canonical — reuse before rewrite)`** in **`l345_router.md`** (and **`# Recipe index (domain)`** in **`router.md`** for product recipes). One row per `## Recipe — …` or reusable E2E **pattern** subsection. When adding, renaming, or removing a recipe, update the index and **Topic Router** in the **same** edit. Routers **never** embed full **Run** steps—only index rows and topic clusters. **DRY:** **lsai_subagents.md** § **Recipe of Recipes** → **DRY, deduplication, and modularization (mandatory)**.

**Definition:**
- A **topic** is made up of 2–5 words and covers something that is likely to be a high-level important concept that repeats many times.
- Prefer **general** topics over long or highly specific ones. Topics are software-development oriented (e.g. "authentication", "schema validation", "test execution")—avoid overly narrow phrases tied to one symbol; prefer broader phrases like "endpoint base class", "mock response", "stage restriction".
- A paragraph, section, or sub-section could contain 2–4 topics, or sometimes just one.

**1.** Given a list of sub-agent `.md` files, do the steps below one agent at a time, paying attention to the Definition above:

**a.** Goal: find the topics that exist in each of the main text paragraph, section, or sub-section for the sub-agent (navigate to section or sub-section if they are found and treat each sub-section separately). If there are references to code or other agents or sections, read them also. Tag each of these paragraphs/sections/subsections separately and then repeat. **DO NOT** tag a section if it has sub-sections—tag only the subsections. Keep topics **general** and software-development oriented (see Definition); avoid long, specific phrases. Write out to: `~/data/agent_topics` (domain router) or `~/data/agent_topics_l345` (L345 router) with a file name that is `<agent file name>.topics` where the output is: `<line number start to end>: comma delimited topics`.

**b.** After you are done generating `<agent file name>.topics` for all agents (human user will tell you when you are done), run the Python scripts from **`.cursor/scripts/`** (or **`bash .cursor/scripts/refresh_l345_router.sh`** for L345). Use `--router-type router` (default, `~/data/agent_topics`) or `--router-type l345_router` / `--l345` (`~/data/agent_topics_l345`); override with **`--data-dir`** or **`ROUTER_BUILDER_DATA`**. Pass **`-w` / `--workspace`** (or **`ROUTER_BUILDER_WORKSPACE`**) so `build_agent_topics_index.py` and `build_router.py` resolve `.cursor/context/`. Scripts: `topic_frequency.py`, `build_agent_topics.py` (default: freq > 1), `build_agent_topics_index.py`, `build_reverse_index.py`, `generate_l345_topics.py`. Output in `topic_frequency.txt`—one topic per line, sorted in reverse order:
```
<topic>:<frequency total count across all agents>
```

**c.** Select all topics occurring more than once (freq > 1) and produce a new file called `~/data/agent_topics/agent_topics.txt`. Use `build_agent_topics.py --min-freq N` to change the threshold.

**d.** Now select these topics and go and find which of them occur in each of the files `<agent file name>.topics` and use the line numbers there to identify the section title (##), sub-section title (### or deeper), or line numbers where they occur. Use line numbers only when there is no section or sub-section. Write another Python script to do this accurately if needed. Produce a new file called `~/data/agent_topics/agent_topics_index.txt` which contains for each agent all the topics that occur and where they occur (section name, sub-section name, or line ranges). Note that we are only picking topics from `~/data/agent_topics/agent_topics.txt`.

**e.** Write a Python script that takes the indexed `~/data/agent_topics/agent_topics_index.txt` and produces a reverse index of topics to a list of agents and their locations. Output format per line: `<topic>:<agent.md>:section:<title>:sub-section:<title>:<line numbers>`. **Format rules:** Do not include `section` if it is missing. Do not include `sub-section` if it is not there. Use line numbers only when both section and sub-section are missing. Produce the list sorted by most frequent topics first (reverse order).

**f.** Run `build_router.py` to generate `router.md` or `l345_router.md` from **`docs/operator/router_templates.md`** (or `--template`). The script stamps the topic list, appends clustered sections from `topic_to_agents.txt`, and writes the output. Use **`--l345`** for L345 mode.

- **Run:** `python3 .cursor/scripts/build_router.py -w <path-to-your-project>` (or **`bash .cursor/scripts/refresh_l345_router.sh`**). Add **`--l345`** to write `l345_router.md`. Optional: **`--data-dir`**, **`--template`**, **`-o`**. L345 mode merges **`docs/operator/l345_router_recipe_index.md`** and uses flat **`### topic`** clusters.
- **Verify:** The Context Discovery block and Topic List appear at the top of the output file; the `# Topic Router` clustered section follows. The opener includes **Agent vision**, **Project interaction log (mandatory every turn)**, and (for L345) the L3-context **Important** note—do not strip these when merging topic clusters (**L4** guardrail).

### Exclusion List (Router Builder)

**Admin-maintained.** Your **platform admin** (or whoever owns router indexing) decides which **`.md`** files under **`.cursor/context/`** should be **skipped** when building the **domain** router topic index. The list below is a **template only**—replace placeholders with your organization’s real basenames (scratch exports, training docs, one-off experiments, local-only agents).

**How to use**
- **Add** basenames you never want in the **domain** topic pipeline (one filename per line in your internal config or doc—exact storage is org-specific).
- **Remove** any sample name that does not exist in your tree.
- **Typical pattern:** exclude **MR workflow** and **L345 bundle** agents from the **domain** index when a separate **L345** router already covers them—mirror that policy using **your** filenames (e.g. `git_mr_guidelines.md`, `lsai_subagents.md`, `lsai_superagent.md`) **only if** those files exist in your bundle.

**Placeholder examples (delete or replace)**
- `scratch_notes.md`
- `local_MR_export.md`
- `onboarding_playground.md`

**Verify:** No sample line here is authoritative for every customer; operators **must** customize before running **`generate_l345_topics.py`** / domain topic steps in production.

### Router templates (operator only)

**`build_router.py`** stamps **`router.md`** / **`l345_router.md`** from **`docs/operator/router_templates.md`**. Do not embed full templates in this file.

---

## Hosted SuperAgent service (optional)

**Portable stack does not use this.** Some orgs run a hosted catalog (sign-in, org secret, remote agent fetch). Use your admin console for CLI/rules — not reproduced here.

---

### Further reading (public)

- **Open companion repository (Apache-2.0):** [github.com/OmMeGo-AI/oai-public](https://github.com/OmMeGo-AI/oai-public) — templates, examples, and **`docs/`** (including **paper** and **deck** PDFs when published).  
- **Citing the stack:** Use **`CITATION.cff`** in that repo when you need a formal citation.  
- **Paper PDF:** Prefer links under **`docs/`** in **`oai-public`** rather than internal developer build paths. If you already have a local copy (for example a downloaded **`2026_omg_ai_paper.pdf`**), you may use it for the same definitions and narrative—keep citations pointed at the public companion when sharing externally.

---

## Support

**Product and onboarding:** Use the contact or help address your organization provides (often listed on the product website or in admin communications).

**Org-specific agents and standards:** Ask your **provider manager** or internal platform team.
