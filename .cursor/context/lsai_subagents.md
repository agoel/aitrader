## CRITICAL: Load router context first (see lsai_superagent.md)

Before doing **any** planning, coding, testing, MR updates, or tool execution, the agent must follow **context discovery** in **`.cursor/context/l345_router.md`** (this bundle’s behavioral router). When your workspace also has **`.cursor/context/router.md`** (domain/product router), load both. **Portable stack:** all context comes from **`.cursor/context/`** in the repo — no remote fetch. See **lsai_superagent.md** § **Portable stack (this bundle)**.

**Cited by:** `coding_standards.md`, `repo_overview.md`, `git_mr_guidelines.md`, `l345_router.md`, `router.md`, `lsai_superagent.md`, `lsai_e2e.md`, `agentic_merge.md` — maintain bidirectional **Cited by** lines when you extend this list.

**Bidirectional citation rule (MANDATORY for all context docs):** When editing any `.cursor/context/*.md` file, if you add a reference to another document (in Related Files, a recipe quick reference, Overview, or any section), you **must** also add this file to the **Cited by** line in that target document. Both directions must stay in sync. Agents often forget the reverse update—always do both in the same edit.

---

# Core Concepts: Layered Work and Routing

This section explains the foundational ideas behind agentic development in this repo. Read it before diving into recipes and templates.

**Agent vision.** For the seven views agents must keep aligned, see **lsai_superagent.md** § Router Architecture and Builder (Agent vision).

**Layered programming and steps.** Work follows a structured flow: design → layers → layer coding → automated test cases → automated tests → interstitial fixes → final working code passing all tests. Each layer is a logical implementation slice containing ordered steps; implement one layer at a time, verify it before moving on. Do not start the next layer until the current one is green.

**Interstitial coding and testing.** Interstitial work is the cycle of: start server (run_rest) → code/test → fix errors → stop → cleanup → repeat. Use **alpha recipes** (localhost, test_endpoint, test_workflow, run_rest) and **beta recipes** (deploy to beta, babysitter, backfill) from `lsai_e2e.md` § Recipes. The agent iterates within a layer until tests pass and no new errors appear in stderr.

**Per-layer E2E.** A layer that ships testable behavior is not complete until the **primary** automated suite is extended for that slice (success and, where relevant, expected failure—e.g. access denied). Document the contract in the sub-agent MR (**E2E checkpoint** blocks or an index table) and run alpha E2E per **lsai_e2e.md**. Full pattern: **lsai_subagents.md** § Document Structure — **Layered implementation and per-layer E2E checkpoints**.

**Routers.** For router usage, building, architecture, and both router types, see **lsai_superagent.md** § Router Architecture and Builder. **Recipe reuse:** **`l345_router.md`** § **Recipe index (canonical)** lists every shipped recipe—scan before authoring or inlining steps. For a **high-level system narrative** (papers, external communication, onboarding) without REST/CLI implementation detail, see **lsai_superagent.md** § **(a) Design Section** — **SuperAgent System View for Release to Outside World**.

**Expert pushback.** User may be a domain expert; **still assume non-expert for this stack** and push back before acting—**hardest at requirements**, less in design, least in execution. **Recipe of Recipes** → **Expert pushback (mandatory — agent is the expert)**.

**Project interaction log.** Every turn, prepend a turn block to **`~/data/{project_slug}/runs/{run_slug}/interaction_log.md`** (newest first) per **lsai_superagent.md** § **### Recipe — Project interaction log (every turn)** and **repo_overview.md** § **Active run**. **Question** = verbatim; **Response** = summary. Resolve **`{run_slug}`** per **Recipe of Recipes** → **Run slug identification**.

---

### SuperAgent outside-world narrative (pointer)

The **high-level** SuperAgent / OmMeGo story for papers, external communication, and onboarding lives in **lsai_superagent.md** (**Core ideas (teaching summary)** + **Router Architecture and Builder** → **Further reading (public)**). **This** file owns **sub-agent** process (recipes, MR format, layering). Add a project-specific sub-agent (for example **`edragent_subagent.md`**) when you track design and MRs for product code in this repo; keep vendor-internal paper runbooks out of this minimal bundle unless you intentionally add them.

---

# Recipe of Recipes

This section has three parts: **(1)** how a recipe should be structured and written so an agent can follow it—including **formal parameters**, **RSI** (recursive self-improvement / self-learning), and **self-healing**; **(2)** how to extract a set of recipes from existing agent docs and consolidate them into a canonical recipe document; **(3)** how to publish recipes (e.g. to S3).

---

## (1) How a recipe should look like

**Style:** Detailed yet crisp — **Run:** / **Verify:**, tables, code blocks; minimal prose. Example: **Recipe — Clippable MR generation (git paste)** (below).

### Structure

After **Recipe purpose**, every recipe includes (in order): **Formal parameters** · **Child recipes** *(parents only)* · **Run workspace** *(multi-stage)* · **RSI** · **Self-healing** · **Expert pushback** · numbered **Run** steps with **Verify**.

### DRY, deduplication, and modularization (mandatory)

**One canonical home per procedure.** Every repeatable workflow lives in **exactly one** `## Recipe — …` block (or one **pattern** subsection in **`lsai_e2e.md`**). Everywhere else: **cite** it—do not copy **Run:** / **Verify:** steps, parameter tables, or RSI blocks.

**Reuse before rewrite (every turn):** Before drafting or editing a recipe, scan **`l345_router.md`** § **Recipe index (canonical)** (and domain **`router.md`** when present). **Load and run** an existing recipe when it fits; **extend** it when the delta is small; **compose** via **Child recipes** when the work is multi-phase. **Push back** if the user asks to inline steps that already exist in the index.

**Modularize aggressively at recipe design (L3):** When authoring or restructuring a recipe, ask: *Can this step be its own child recipe?* Split when a sub-flow is (a) reusable elsewhere, (b) independently verifiable, or (c) >~5 **Run** steps. Parent keeps orchestration + **Child recipes** table; children own detail. **Suggest** splits to the user during requirements/design—not only at execution.

**Dedup rules:**
- **Same concern, two places** → delete the duplicate; keep the sharper canonical block; add **`… recipe quick reference:`** cites both ways (**Cited by:** in canonical doc).
- **Parent vs child** → parent **never** repeats child **Run** steps—only *when* to invoke and which params to pass.
- **Router vs agent** → routers **index** recipes; they do not embed recipe bodies. Topic clusters point at `agent.md | section: Recipe — …`.
- **Extraction (§ (2))** → moving prose into a canonical recipe doc **is** the DRY pass; trim sources per scenarios (i)–(iv).

**Verify:** New recipe has no overlapping **Run** steps with an indexed recipe unless it **calls** that recipe as a child. Router index updated when adding or renaming `## Recipe — …`.

### Formal parameters (L4-defined)

**L4/L3** declare the parameter table per sub-agent. Required block:

| Parameter | Type | Required / Optional / Default | Description |
|-----------|------|-------------------------------|-------------|
| `<name>` | string / path / enum | **Required** \| **Optional** \| **Default:** `…` | Source: prompt, notes, **repo_overview**, prior step |

**Before Run:** infer **Required** from user notes → apply **Default** when silent → record bindings in **`runs/{run_slug}/meta.json`** → **push back** if still missing (name the param and expected value; do not proceed).

### Expert pushback (mandatory — agent is the expert)

**The user may be an expert** (domain, code, product). **For this stack—assume they are not:** recipes, run slugs, CoT backtrack, MR preflight, log rules. **You** own that fluency. Push back **aggressively** before edits anyway—expert users get precision; non-experts need it. Do not defer because the prompt sounds confident.

**Ambiguity gradient (pushback intensity):** Ambiguity is **highest in requirements**, lower in **design**, **lowest in execution**. Push back **hardest** before spec is stable; relax only as prior stages lock decisions.

| Stage | Ambiguity | Pushback |
|-------|-----------|----------|
| **Requirements / spec** | Highest — goals, scope, acceptance criteria often vague | **Aggressive.** No design or execution until spec gaps are named and resolved or explicitly waived in `S*` CoT. |
| **Design** | Medium — constrained by spec | Push back on contract gaps vs `spec.md`; do not re-litigate settled `S*` without backtrack. |
| **Execution** | Lowest — constrained by spec + design | Push back on branch/track/contract violations; otherwise proceed when `depends_on` is satisfied. |

**Stop when:** missing params / `{run_slug}` · skipped stages · conflicts with log/CoT/git rules · unclear branch or MR scope · shortcut breaks backtrack · **spec layer incomplete but user wants design/execution/code**.

**How:** **Stop** writes → **Name** issue + recipe cite → **Recommend** expert default → **One question** only if user must choose (resume vs new run). Not “just do it.”

**Verify:** Non-trivial turn ends with explicit bindings **or** named pushback. **Requirements-stage:** `spec.md` has testable acceptance criteria **or** pushback—not “we’ll figure it out in code.”

### Run workspace (`~/data/{project_slug}/runs/{run_slug}/`)

One **run** = one folder: `meta.json`, `interaction_log.md`, stage **CoT** + artifacts, optional MR layer tree (`specification/`, `design/`, `execution/`, `merges/`, `rsi/`).

| Stage | CoT (flat or nested) | Artifact |
|-------|----------------------|----------|
| Spec | `requirements.cot.md` / `specification/cot.md` | `spec.md` |
| Design | `design.cot.md` / `design/cot.md` | `design.md` |
| Execution `<track>` | `execution_<track>.cot.md` / `execution/<track>/cot.md` | `steps.md` |

**Rules:** data only under `runs/` · CoT **append-only** · never paste CoT into review/MR export · `meta.json`: `run_slug`, `status`, bound params.

**Run:** `mkdir -p …/runs/{run_slug}`. **Verify:** `meta.json` + `interaction_log.md` exist.

### CoT step headings and backtrack

File title: `# Chain of thought — <layer>`. Each decision slice:

```markdown
## CoT — <step_id>: <short title>
- **Artifact:** <path>#<section>
- **depends_on:** S2, D1, …
- **Decision:** …
- **Alternatives rejected:** …
```

| Stage | Id | Aligns with |
|-------|-----|-------------|
| Spec | `S1`, `S2`, … | `spec.md` |
| Design | `D1`, `D2`, … | `design.md` |
| Execution `<track>` | `E<track>-1`, … | `steps.md` **Step k** |

**Backtrack:** find block for the tweak → walk **`depends_on`** transitively → revise from shallowest affected layer (spec change may invalidate `D*` and `E*-*`) → mark superseded or `## CoT — Sk (rev 2)`; bump layer/manifest `version` when spec/design forces rework.

**Ambiguity:** Requirements **`S*`** CoT should record open questions until closed; design/execution add detail—they do not invent scope the spec never decided.

### Run slug (`{run_slug}`) identification

**Default:** `{username}_{run_stem}_{run_started}` — `run_stem` = 3–6 words from problem; `run_started` = `yyyyMMdd-HHmmss` at folder creation (stable).

**Pick (in order):** (1) user-named slug → (2) **repo_overview** § **Active run** on resume → (3) sole `status: active` in `runs/` → (4) new run on new problem / “new run” → (5) ambiguous → **push back** with candidates.

**Legacy:** `{mr_slug}` = `{run_slug}`. New run → new folder + log; resume → **never overwrite** log or CoT.

### Parent and child recipes (composition)

**Design-time:** For every new parent recipe, produce a **Child recipes** table during **requirements**—do not wait until execution. If a step maps to an indexed recipe, **reference the child** instead of inlining. Propose **new** child recipes when a slice is reusable (name them `## Recipe — …` in the owning agent doc).

| Child recipe | When invoked | Params passed (from parent) |
|--------------|--------------|-----------------------------|
| `Recipe — …` | Trigger condition | `{param}` bindings |

**Run-time:** **Bind parent params** → pass through to children → **defaults cascade** → run children **in order** → read child output from **`runs/{run_slug}/`**, not chat. Parent **Run** steps are orchestration only (mkdir, meta, invoke child, merge artifacts).

**Verify:** Each child done or waived in `meta.json` / `merges/`; parent doc has **no** duplicated child **Run** / **Verify** prose.

### Interaction log on resume (never overwrite)

Per run: **`runs/{run_slug}/interaction_log.md`**. Full recipe: **lsai_superagent.md** § **Recipe — Project interaction log**.

**Never overwrite** — prepend turns, refresh **Last updated** only. New run → new slug + new log. Reset → new slug or archive run (`status: closed`).

**Prepend algorithm:** **lsai_superagent.md** § **Recipe — Project interaction log (every turn)** → **Prepend algorithm (mandatory — do not truncate)** — read entire log before write; do not truncate.

### RSI — recursive self-improvement (one type per recipe)

**One** type per recipe. Internal constants: `_RSI_TYPE`, `_RSI_MAX_ROUNDS`, `_RSI_STOP_CONDITION`, `_RSI_ARTIFACT_DIR`.

| Type | Id | Stop when |
|------|-----|-----------|
| Error-log | `error_log` | No matching error patterns in named logs |
| Test-suite | `test_suite` | Suite green (exit 0) |
| External-metric | `external_metric` | `_RSI_STOP_CONDITION` on metric / other recipe output |

**Pick:** logs → (a); tests → (b); KPI/visual/cross-recipe → (c). **Loop:** run → check stop → evidence in `_RSI_ARTIFACT_DIR` → repeat or push back at max rounds.

*(Authoring RSI in **lsai_superagent.md** § Base L345 refresher is separate—markdown edits from telemetry, not runtime (a)/(b)/(c).)*

### Self-healing

**Drift** (skipped step, wrong file, Verify ignored) → **Stop** → **Assess** vs recipe state → **Diagnose** one cause → **Recover** with recipe-specific steps or **push back**.

Each recipe: **`#### Self-healing`** with symptom → assess → recover bullets for **this** recipe’s artifacts and RSI type.

## Recipe — Slice-first performance gate (data pipelines)

**Purpose:** Before any full-corpus or multi-month batch job, profile on a **small slice**, fix hot paths, then scale. Applies to ingest, keyword fill, backtest, RSI, and any loop over 10k+ rows.

**Child recipes:** Domain parents (e.g. **aitrader_subagent.md** § prediction backtest) cite this recipe and add **domain budgets** only—do not duplicate the gate steps.

### Formal parameters

| Parameter | Type | Required / Optional / Default | Description |
|-----------|------|-------------------------------|-------------|
| `{slice_size}` | int | **Default:** problem-specific (see parent) | Rows, months, or articles in probe |
| `{slice_budget_sec}` | number | **Default:** `60` | Max wall time for probe before abort + diagnose |
| `{full_budget_sec}` | number | **Optional** | Abort full run if exceeded after probe passed |

### Run

1. **Count** — print corpus size, loop cardinality (e.g. articles × inner work), and expected iterations **before** starting the full job.
2. **Probe** — run the same code path on `{slice_size}` (e.g. 3 months, 10 articles, 1 sector); log **per-step** timings (not only phase totals).
3. **Extrapolate** — if probe × scale > `{slice_budget_sec}` or obvious O(n²), **stop**; do not launch the full batch.
4. **Fix** — remove redundant work (reuse cached models, aggregate by day not row, bisect timelines, cap window reads, parallelize only after slice is green).
5. **Re-probe** — repeat until probe completes under budget with correct outputs.
6. **Full run** — only then run the full dataset; keep **RunProgress** / `pipeline_status.json` on every long phase.

**Verify:** Probe log shows dominant step and post-fix probe is ≥10× faster or under `{slice_budget_sec}`; full run finishes without silent multi-hour stalls.

#### Self-healing

| Symptom | Recover |
|---------|---------|
| Progress stuck at same fraction >2× probe extrapolation | Kill run; return to step 2 with smaller slice; print per-iteration timing |
| “Walk-forward slow” but loop count is small | Profile **downstream** phases (often a second loop over all rows, not the walk-forward itself) |
| Full run still slow after probe | Probe was unrepresentative—increase slice until hot path matches production cardinality |

### Content style (crisp and actionable)

- **Bold for labels** — Use bold for category labels, step titles, and key terms. Example: **Run:**, **Verify:**, **Purpose:**.
- **One line when possible** — Keep bullets and sub-bullets concise; avoid long paragraphs unless necessary.
- **Cluster related items** — Group related steps under logical sub-headers; do not scatter similar content.
- **Focus on what to do** — Emphasize commands, paths, and concrete actions; minimize explanatory prose.
- **Run / Verify pattern** — For test cases or verification steps: **Run:** exact command or steps; **Verify:** what to check to confirm success. Be specific and actionable.
- **Code blocks for commands** — Put shell commands, paths, and JSON snippets in code blocks. Use placeholders (e.g. `<app>`, `<stage>`) where values vary.

### What to avoid

- Redundant or philosophical prose
- **Duplicating** an indexed recipe’s steps in another doc—cite or compose as a child instead
- **Monolithic** recipes that should be parent + children (split at design time)
- Vague instructions ("run the appropriate command")
- Mixing multiple concerns in a single bullet
- Missing prerequisites (credentials, paths, virtualenv) when they are required

### Published recipe format (S3-stored recipes)

**Not used in portable stack.** Experimental KPI publish: metadata block (`recepie name`, `version`, `last_updated_utc`, `titie`, `desription`) must match S3 key. See org KPI agent when present.

### Reference

Existing recipes in `lsai_e2e.md` follow this pattern. Use them as examples when drafting a new recipe.

---

## (2) How to extract a set of recipes from existing agents

**Portable stack:** L3 operator pass — DRY enforcement. Full methodology: snapshot at **`~/data/agents_orig`**, classify sources **(i)–(iv)**, bidirectional cites, update **`l345_router.md`** recipe index.

**Quick checklist:** (0) snapshot · (1) list Sources · (2) read from snapshot · (3) classify · (4) edit live `.cursor/context/` + reverse cite · (5) recipe doc: remove Sources line numbers, add **Cited by:**

| Type | Action |
|------|--------|
| **(i)** High-level only | Delete source body; section-level cite |
| **(ii)** Fragment | Delete; cite specific subsection |
| **(iii)** Full section pointer | Delete; cite + what to look for |
| **(iv)** No 1:1 map | Keep source; add cite |

---

## (3) How publishing works

**Portable stack:** **Skip** — experimental S3/KPI pipeline only. When org runs it: edit canonical recipe → publish to `s3://{BUCKET}/kpi_recipes/<name>` → verify metadata. See **`{COMPANY_DOC_PREFIX}kpi.md`** when shipped.

---

## Recipe — Agent brain map HTML producer

**Recipe purpose:** HTML outline viewer for sub-agent `.md` (before § (b)). **Implementation:** **Not included in the portable stack.** This recipe requires **`brain_map_produce.py`** and **`brain_map_template.html`**, which are not shipped under **`.cursor/context/`**. **Skip** unless the user adds those scripts to the repo locally.

1. **Run:** From the repo root, invoke the producer with **`python3`** (path to **`brain_map_produce.py`** in your repo). Pass **`-i .cursor/context/<agent>.md`** and **`-o`** to an HTML path under your data directory. If the script is missing, stop here.
2. **Cursor handoff (optional):** Paste the printed **`file://`** URL into chat so **Cmd+click / Ctrl+click** works inside Cursor. Resolve **`~`** with `realpath` / `readlink -f` before building the URI if needed.
3. **Verify:** Open the HTML; confirm outline navigation and highlights behave as documented in the script’s **`--help`** output (if shipped).
4. **MR cut line:** The producer typically stops at the first heading whose text includes **`(b) Project MR Tracking`**. If your agents use a different MR heading, adjust the script’s heading regex in your local copy of the producer.
5. **Cluster semantics:** Clusters are **heading-derived** from the markdown outline; rebuild after outline edits.

**lsai_superagent.md recipe quick reference:** **§ (c) Design Email Tracking — 2025 carry-forward** lists scheduling ownership for this viewer on the SuperAgent roadmap.

---

# Agentic merge (pointer)

**Recipe — Agentic merge (agent .md conflicts):** **`agentic_merge.md`** — full workflow (preserve secondary under `~`, no `git add`/commit by agent). **l345_router.md** topic **agentic merge**.

---

# How to clean up MR section AFTER the release is ready to ship: user can ask for "close out MR"

Use when retiring the shipping **Open MR** checklist (often after **Recipe — Clippable MR generation (git paste)**). Follow **Document Structure — (b) Project MR Tracking** here and **git_mr_guidelines.md**. **Unless the user says otherwise, complete Phase A before Phase B.** Long **Layer / Step** tables and merge gates will live only in **git history** once pared—**fold anything readers still need from § (b) into § (a) (or the short Merged MR blurb) before deleting bulk from (b)**.

**Phase A — Update § (a) Design from the MR (do this first)**

1. Read the full shipping **§ (b)** block: every **Done** item and **global Layer L, Step k** (**Document Structure — Layered Implementation sequence — Global layer numbering (releases, layers, and steps)**; **Layer L** is project-wide, not a per-release counter). Use **`git diff <base>...HEAD`** (and logs) when **§ (b)** omits paths, flags, or contracts the design must carry.
2. For each completed item, promote **operator / regression** truth into **§ (a)** if missing: CLI options, env vars, scratch paths, admin job inputs, redaction rules, harness commands, acceptance boundaries. **Keep reusable verification** in **§ (a)** or **Related Files** when a script, harness, or standing alpha/beta/gamma case remains the ongoing contract for humans or CI; drop only **MR-only** one-off checks with no lasting runner. Skip **experiments/** one-off migrations and pure bugfix trivia unless the **framework** contract changes. **§ (a)** must read as the framework **after** merge.
3. **Fold closing MR into § (a) without release-version design prose:** Incorporate shipped MR facts into **§ (a)** as **capability / feature** narrative—**not** as a **Release R** changelog inside the design section. **That “no release label spray in prose” rule applies only to § (a)** for **already shipped** work (and use **one** compact **global layer span** line or pointer where the doc tracks monotonic layers). **Do not** strip **Release R** from: not-yet-implemented § (a) copy, any **§ (b)** (**Open MR** or **Merged MR** narrative), roadmap bullets that name **Release R**, **TODO Next release** / **TODO Future release**, or global backlog indices.
4. After renames, **grep** the sub-agent (and any cited router/context files) for stale **§** / anchor strings; update cross-references so closeout does not strand links.

**Phase B — Clean § (b) (only after Phase A)**

1. Remove completed **Layered Implementation** / **Details** bulk for **Release R** (already digested in Phase A and/or summarized in the merged blurb below).
2. **TODO** / **TODO Next release** / **TODO Future release** / pending migrations: **do not** remove—leave for the next cycle (**R+1** / **R+2** ordinals per **Clippable MR** **Release-order guard**).
3. Replace **Open MR — Release R** with **Merged MR (Release R — closed)** per sub-agent pattern: **short** narrative, MR link, pointer to **§ (a)** + **git history** for old layer tables. **Keep** **Release R** on that merged title line; **keep** titles and bodies of **next** / **future** open MRs intact.
4. If **`.cursor/context/MR.md`** exists (clippable scratch), delete it — gitignored, not authoritative; avoids mistaken reuse.

**lsai_e2e.md recipe quick reference:** For clean/init/build/deploy vocabulary and alpha/beta templates, see **Build phases (generic pattern)** and **Org template — plug in your alpha harness**.

# Language-specific conventions (see coding_standards.md)

For Python packaging, virtualenv layout, TypeScript/Angular rules, timestamps, and generated files, use **`coding_standards.md`** in **`.cursor/context/`**—do not fork a second copy here.

# How to update MR section of a sub-agent

If the user is asking to **update the MR** (edit the sub-agent doc in-repo), update the **§ (b) Project MR Tracking** section of the project sub-agent file the user names, using the same field structure as **Document Structure — (b) Project MR Tracking** in this file and the full git MR layout in **`.cursor/context/git_mr_guidelines.md`**. Include Details, More Details, TODO, TODO Next release, TODO Future release, Alpha / Beta / Gamma testing as appropriate. Keep wording detailed yet crisp for code review.

Do **not** confuse this with **Recipe — Clippable MR generation (git paste)** (below), which **pastes** a review body for the git host without necessarily editing the sub-agent doc.

---

## Recipe — Clippable MR generation (git paste)

**Recipe purpose:** When the user asks for a **clippable MR**, **paste-ready review body**, or similar, produce Markdown they can paste into the **remote review description** on their **git host** **without asking whether to copy to the clipboard**—run the clipboard step as part of this recipe whenever the environment can run it (see step 7). Host choice (GitHub, GitLab, etc.) comes from **`repo_overview.md`** § **Git and review context**—recipes use **git** only.

**Normative MR shape (two layers—apply both):**

*Here **two layers** means two normative **documentation** sources (not **global Layer** indices **L** from **§ Document Structure — Global layer numbering** below).*

1. **`.cursor/context/git_mr_guidelines.md`** — Title convention; section order (**Layered Implementation Sequence**, **Details**, **More Details**, **TODO**, **TODO Next release**, **TODO Future release**, **Alpha / Beta / Gamma Testing**); **global layer** numbering rules; tone.
2. **This file — Document Structure — § (b) Project MR Tracking** — What each subsection is for in a sub-agent–backed project (how **Details** relates to completed work, how **TODO** blocks merge, alpha case specificity, interstitial run subsections when applicable).

**Preflight (mandatory):** Three tiers in **git_mr_guidelines.md** § **Clippable MR export (preflight — mandatory)** — **Tier A** slug pack (if used), **Tier B** § **(b)** shape, **Tier C** export composition. In short for **Tier B:** (1) locate **`## (b) Project MR Tracking`**; (2) validate against **git_mr_guidelines.md** § **Sections** and this file § **(b) Project MR Tracking**; (3) if fail → **STOP**—no `MR.md`, no clipboard.

**Source of truth for *content* when composing or refreshing the MR from the branch (critical):**

- **Primary:** The **entire diff of the current branch compared to the integration branch**, not only bullets already written under a sub-agent’s **Layered Implementation Sequence**. Use at least:
  - `git fetch` if needed, then `git diff --stat <base>...HEAD` and `git diff --name-status <base>...HEAD` (or equivalent).
  - `git log --oneline <base>..HEAD` when a narrative commit list helps reviewers.
- **Default base branch:** **`{git_default_branch}`** from **`repo_overview.md`** § **Git and review context** (e.g. `main`, `master`). Use **`origin/<branch>`** when the local tracking branch is stale.
- **Secondary (merge, do not replace the diff):** If the branch tracks formal layers in a sub-agent **§ (b) Project MR Tracking** (e.g. **`lsai_superagent.md`** Release **1.3**, global layers **4–9**), **fold that text in**—especially **Layered Implementation Sequence**, release title, and merge gates—**and** add a **Details** (or **More Details**) subsection for **branch-wide** changes that the formal MR table does not mention (extra scripts, unrelated docs, assets, config).
- **CRITICAL — do not use stale `.cursor/context/MR.md` for content:** That path is a **temporary, gitignored** scratch file. **Never** treat an existing `MR.md` on disk as authoritative. Always **recompute** MR body from git + sub-agent docs for this request.

**Steps:**

1. **Load format:** Open **git_mr_guidelines.md** and **this file** § **(b) Project MR Tracking**; build the section skeleton (title line + headings) accordingly.
2. **Inventory the branch:** Compare **HEAD** to **`<base>...`**; group changes by area (product, `LSAICommon`, `.cursor/context`, experiments, etc.). Mention notable paths, scripts, and generated artifacts (and **out-of-repo** build outputs if the diff only adds recipes pointing to them).
3. **Compose the MR body:** Fill **Details** (and optional **More Details**) from the **full** inventory. Align **Layered Implementation Sequence** with the sub-agent **§ (b)** when it exists for this release. **Layer** headings must use the project’s **global layer** indices (**Layer L**) and, inside each layer, **Step 1, 2, 3…** restarting per layer—per **git_mr_guidelines.md** and **§ Document Structure — Global layer numbering (releases, layers, and steps)** below (not per-release **Layer 1** resets). If there is no formal layer table, omit that section or write a short ordered list of logical slices derived from commits—still follow **git_mr_guidelines.md** for headings.
4. **TODO / testing:** Set **TODO** / **TODO Next release** / **TODO Future release** / **Alpha** / **Beta** / **Gamma** from facts in the diff and from **§ (b)** merge gates; use **“Not applicable”** with reason when **git_mr_guidelines.md** expects it.
   - **Release-order guard for TODO Next / TODO Future (mandatory when the sub-agent has a versioned release roadmap):** Do **not** choose “next” by technical affinity, cross-references inside the current MR, or “the follow-on MR we talk about most.” **TODO Next release** must summarize **only** the **numerically next** release the same sub-agent documents (if this MR ships **Release 1.4**, the next cycle is **Release 1.5**, not **1.6**, unless **§ (b)** or MR **Details** explicitly reprioritize). **TODO Future release** starts at **Release R+2** and later (and other long-horizon backlog)—do **not** use **None** there when the roadmap already defines a concrete **R+2** (e.g. **1.6** after **1.5**). Before writing those subsections, read the sub-agent’s **Release Roadmap** / **Open MR — Release N** blocks (e.g. **`lsai_superagent.md`**) and align bullets to that **ordinal** order; add one line in **Details** if product order diverges from numeric order.
5. **Preflight** the MR block (same checks as **Preflight** above) before writing the scratch file.
6. **Write scratch file:** Write **only** the MR Markdown to **`.cursor/context/MR.md`** (overwrite). Use the workspace root that contains **`.cursor/context/`** (typically the repo root).
7. **Copy to clipboard (mandatory when possible):** From repo root, run one of:
   ```bash
   pbcopy < .cursor/context/MR.md          # macOS
   xclip -selection clipboard < .cursor/context/MR.md   # Linux X11
   wl-copy < .cursor/context/MR.md         # Wayland
   ```
   If no clipboard tool exists, paste the full MR body into the assistant reply—**do not** stop after writing `MR.md` without clipboard success or inline paste.
8. **Delete scratch:** Remove **`.cursor/context/MR.md`** immediately after a successful clipboard copy (or after inline paste if clipboard failed).
9. **Confirm:** Tell the user the MR was generated from **`<base>...HEAD`**, that format follows **git_mr_guidelines.md** and **this file** § **(b) Project MR Tracking**, and whether the clipboard step succeeded. If you also pasted the body in chat, say so.

**Paste-only shortcut:** If the MR section is **already** written in **§ (b)** and preflight-clean, you may skip steps 2–4 and export from the existing text only; still run **Preflight**, then steps 6–9.

**Related:** **How to clean up MR section AFTER the release is ready to ship** (closeout) above; **How to update MR section of a sub-agent** above; **Recipe — Layered MR slug pack** (below) for multi-layer spec/design/execution under **`~/data/{project_slug}/runs/{run_slug}/`**.

---

## Recipe — Layered MR slug pack

**Recipe purpose:** Materialize **`~/data/{project_slug}/runs/{run_slug}/`** with **Specification**, **Design**, **Execution** layers + **CoT step ids** (`S*` / `D*` / `E<track>-*`). Parallel tracks, gzip handoff, branch gate, agentic merge. **Ship:** sync to § **(b)** → **Clippable MR (git paste)**. Legacy direct § **(b)** + export still valid at ship time.

### Formal parameters

| Parameter | Type | Required / Optional / Default | Description |
|-----------|------|-------------------------------|-------------|
| `{project_slug}` | string | **Required** | Workspace id (e.g. `myproject`). **repo_overview.md** § **Project interaction log**. |
| `{problem_statement}` | string | **Required** | User’s problem in their words (verbatim). Seeds Specification layer. |
| `{run_slug}` | string | **Optional** | Run folder under `runs/`. **Default:** `{username}_{run_stem}_{run_started}` per **Run slug identification**. |
| `{mr_slug}` | string | **Optional** | **Legacy alias** for `{run_slug}` (same value in `manifest.json`). |
| `{username}` | string | **Default:** `whoami` | Owner creating the pack. |
| `{git_branch}` | string | **Required** | Branch where code for this problem is (or will be) developed. Recorded in manifest; helpers **must** match before execution. |
| `{git_base_branch}` | string | **Default:** `{git_default_branch}` from **repo_overview.md** § **Git and review context** | Integration branch for diff / MR target. |
| `{git_commit}` | string | **Optional** | HEAD at pack creation; refreshed on publish. |
| `{execution_tracks}` | list | **Default:** `["ui", "backend"]` | Independent execution sub-layers under `execution/`. Add tracks (e.g. `infra`, `mobile`) when Design warrants. |
| `{helper_username}` | string | **Optional** | Set when handing off; recorded in manifest `helpers[]`. |

**Pushback:** Do not create the pack without `{problem_statement}`, `{project_slug}`, and `{git_branch}`. If `{git_branch}` does not exist locally, ask whether to create it or record a **planned** branch name before proceeding.

### RSI — recursive self-improvement

**Internal constants:**

| Constant | Value |
|----------|--------|
| **`_RSI_TYPE`** | `external_metric` |
| **`_RSI_MAX_ROUNDS`** | `5` |
| **`_RSI_STOP_CONDITION`** | `manifest.json` validates; required layer files exist; current `git branch --show-current` equals `manifest.git_branch` (or user explicitly waives with reason in `merges/`) |
| **`_RSI_ARTIFACT_DIR`** | `~/data/{project_slug}/runs/{run_slug}/rsi/` |

**Metric:** Pack integrity checklist—every required path present, JSON parseable, CoT non-empty for layers marked **complete**.

### Self-healing

- **Symptom:** Helper runs on wrong branch → **Stop** → **Recover:** print `manifest.git_branch`; do not edit execution until `git checkout` confirmed; log waiver in `merges/` if intentional.
- **Symptom:** Two editors changed `design/` concurrently → **Stop** → **Recover:** run **§9 Agentic merge (slug pack)**; publish new tarball; notify all assignees.
- **Symptom:** Execution track drift (UI assumes API that Design dropped) → **Assess:** `shared/state.json` vs `design/design.md` → **Recover:** update Design + shared state before more execution steps.
- **Symptom:** Stale gzip handed back → **Recover:** compare `manifest.last_updated` in tarball vs local; reject if older unless merge workflow requested.

---

### Slug pack layout (normative)

**Root:** `~/data/{project_slug}/runs/{run_slug}/`

```
{run_slug}/
  meta.json
  interaction_log.md
  manifest.json
  MANIFEST.md
  specification/
    cot.md
    spec.md
    meta.json
  design/
    cot.md
    design.md
    meta.json
  execution/
    tracks.json
    shared/
      state.json
    <track>/
      cot.md
      steps.md
      meta.json
  merges/
  rsi/
```

**`manifest.json` (required fields):**

```json
{
  "project_slug": "myproject",
  "run_slug": "alice_auth-fix_20260528-161500",
  "mr_slug": "alice_auth-fix_20260528-161500",
  "problem_title": "short title",
  "owner": "alice",
  "helpers": [],
  "git_branch": "feature/auth-fix",
  "git_base_branch": "main",
  "git_commit": "",
  "created_at": "yyyy-mm-dd:hh:mm:ss",
  "last_updated": "yyyy-mm-dd:hh:mm:ss",
  "version": 1
}
```

**CoT:** **Recipe of Recipes** → **CoT step headings and backtrack** (`## CoT — S|D|E<track>-n`, `depends_on`). Not for review paste.

---

### 1. Initialize pack from problem

**Run:**

1. **Pushback** formal parameters (above).
2. `mkdir -p ~/data/{project_slug}/runs/{run_slug}/{specification,design,execution/shared,merges,rsi}`; create `interaction_log.md` (full header) and `meta.json` with `run_slug` + `"status": "active"`; update **repo_overview** § **Active run**.
3. Write `manifest.json` + `MANIFEST.md` (include gzip command template).
4. Create `execution/tracks.json` from `{execution_tracks}`; `mkdir` each `execution/<track>/`.
5. Seed `specification/spec.md` with problem statement and **Goals / Non-goals / Open questions** headings.
6. Initialize each `cot.md` with file title `# Chain of thought — <layer>` only (no step blocks until work starts).

**Verify:** `manifest.json` lists correct `git_branch`; all track folders exist.

---

### 2. Specification layer

**Pushback gate:** Most ambiguity lives here—**expert pushback is mandatory** before design or execution. Do not advance layers until spec is stable or user **explicitly waives** named gaps in an `S*` CoT block.

**Run:**

1. For each spec edit, append **`## CoT — S<n>: <title>`** to `specification/cot.md` (see **CoT step headings and backtrack**); set **`depends_on`** to prior `S*` steps; leave **`Open questions:`** populated until resolved.
2. Update `specification/spec.md`: requirements, acceptance criteria, constraints, out-of-scope; cite **`Artifact:`** in the matching CoT block.
3. Set `specification/meta.json`: `{ "status": "draft|complete", "editor": "<username>", "version": 1 }` — **`complete` only** when acceptance criteria are testable and no blocking open questions.

**Verify:** Testable acceptance criteria; every major decision has `S*` CoT; **push back** if user jumps to design/execution/code with a draft spec.

---

### 3. Design layer

**Pushback:** Ambiguity lower than spec—push back on gaps vs **`spec.md`**, not on renegotiating settled requirements unless backtracking `S*`.

**Run:**

1. Read `specification/spec.md`; for each design decision append **`## CoT — D<n>: <title>`** to `design/cot.md` with **`depends_on`** including relevant `S*` (and prior `D*`).
2. Update `design/design.md`: architecture, data flow, interfaces between execution tracks, global layer mapping (ties to **git_mr_guidelines.md** global **Layer L** when known).
3. Update `execution/shared/state.json` with contracts both tracks must honor (API shapes, feature flags, shared types).
4. Update `design/meta.json` status.

**Verify:** Each execution track in `tracks.json` has at least one bullet in Design assigning its scope.

---

### 4. Execution layer (independent tracks)

**Purpose:** **UI** and **backend** (and other tracks) proceed **in parallel** with **minimal shared state**—only `execution/shared/state.json` and Design—not each other’s `steps.md`.

**Pushback:** Lowest ambiguity—proceed when `spec.md` + `design.md` + `depends_on` are satisfied; push back on branch mismatch, track scope drift, or contract breaks only.

**Run (per track):**

1. Work only under `execution/<track>/`.
2. For each **Step k** in `steps.md`, append matching **`## CoT — E<track>-k: <title>`** to `execution/<track>/cot.md` with **`depends_on`** on `D*` / `S*` as needed (step index **k** aligns with **Step k** in the artifact).
3. Update `execution/<track>/meta.json` (`assignee`, `status`).
4. On contract change → **stop track** → update **Design** + **shared/state.json** → publish slug bump (§8) so other tracks merge.

**Verify:** Steps reference `spec.md` / `design.md` paths; no duplicate spec/design prose.

---

### 5. Legacy shippable MR (slug → § (b) → git paste)

**Purpose:** Connect the **slug pack** (collaboration workspace) to the **legacy shippable MR** (reviewer-facing body on your **git host**). CoT and handoff artifacts stay in the slug; only the **§ (b)**-shaped body is exported for paste.

**Two pipelines (do not conflate):**

| Phase | Where work lives | Who reads it |
|-------|------------------|--------------|
| **Collaboration** | `~/data/{project_slug}/runs/{run_slug}/` — spec, design, execution, CoT, interaction log | You, helpers, parallel track owners |
| **Ship / review** | Sub-agent **`## (b) Project MR Tracking`** + remote review on git host | Reviewers |

**Mapping slug → § (b) (when layers are stable enough to ship):**

| Slug source | § (b) / review section |
|-------------|------------------------|
| `specification/spec.md` — goals, acceptance criteria | **Details** (summary bullets); informs **Title** / release scope |
| `design/design.md` — architecture, global **Layer L** | **Layered Implementation Sequence** (Approach + per-layer steps) |
| `execution/<track>/steps.md` — completed work | **Details** / **More Details** (group by area or layer) |
| `execution/shared/state.json` — contracts | Cross-reference in **Details**; not pasted verbatim if internal |
| Alpha/beta/gamma plans from design + execution | **Alpha Testing** / **Beta Testing** / **Gamma Testing** (single global sections each) |
| Open work from spec or tracks | **TODO** / **TODO Next release** / **TODO Future release** |

**Run:**

1. Confirm `manifest.git_branch` matches your working branch (`git branch --show-current`).
2. **Sync:** Copy mapped content into the project sub-agent **`## (b) Project MR Tracking`** following **git_mr_guidelines.md** § **Sections** (heading order, global layers, guardrails).
3. **Preflight:** **git_mr_guidelines.md** § **Clippable MR export** — **Tier A** (slug) if applicable, then **Tier B** on **§ (b)**.
4. **Export:** Run **Recipe — Clippable MR generation (git paste)** — **Tier C** preflight, then **`git diff <base>...HEAD`** plus **§ (b)**; writes scratch **`MR.md`**, copies to clipboard, deletes scratch.
5. **Paste** into the remote review description on your git host (or use **`{git_review_cli}`** from **repo_overview.md** when configured).
6. Optional: note review URL in `merges/<timestamp>_shipped.md` inside the slug pack for traceability.

**Verify:** Review body matches **§ Sections**; slug CoT files were **not** pasted; branch diff is reflected in **Details**.

**Shortcut:** If you never used a slug pack, **Clippable MR (git paste)** alone still works from branch + **§ (b)** as today.

---

### 6. Export slug pack (share)

**Run:**

```bash
cd ~/data/{project_slug}/runs
tar -czf {run_slug}.tar.gz {run_slug}/
```

**MANIFEST.md must include:** `project_slug`, `run_slug`, `owner`, `last_updated`, **`git_branch`**, unpack path, and helper checkout instruction.

**Verify:** Tarball extracts to same tree; `manifest.json` intact.

---

### 7. Helper install + branch gate

**Run (helper):**

1. Unpack under `~/data/{project_slug}/runs/`.
2. Read `manifest.json` → **prompt user:**
   ```text
   This slug pack requires git branch: <git_branch>
   Base branch: <git_base_branch>
   Run: git fetch && git checkout <git_branch>
   Confirm when on that branch before continuing.
   ```
3. **Pushback:** If branch mismatch and no waiver → **stop**; no execution edits.
4. Record helper in `manifest.helpers`; bump `last_updated`.

**Verify:** `git branch --show-current` matches before execution work.

---

### 8. Helper publish updated slug

**Run:**

1. Helper updates track CoT/steps/meta; refresh `manifest.last_updated`; increment `manifest.version` if spec/design touched.
2. Re-tar pack → return to owner; log summary in `merges/<timestamp>_helper_<username>.md`.

**Verify:** `git_branch` unchanged unless owner agreed.

---

### 9. Agentic merge (slug pack)

**When:** Owner receives helper tarball **or** parallel editors diverged on **specification/** or **design/**.

**Run:** Adapt **§ How to do Agentic Merge when there is conflict in Agents .md while merging** for slug files:

1. One file at a time (`spec.md`, `design.md`, `execution/<track>/steps.md`, `shared/state.json`).
2. Owner pack = **primary** unless user overrides.
3. Preserve secondary under `merges/secondary_<stem>_<suffix>.*`
4. Clustered diff tables for optional fold-in (spec/design).
5. Update `manifest.last_updated`, `merges/<timestamp>_merge.md`, increment `version`.

**Verify:** If spec/design merged, run §10 broadcast.

---

### 10. Broadcast after spec/design merge

**Run:** When Specification or Design changes after parallel work started:

1. Bump `manifest.version`; export new tarball; notify assignees.
2. Each assignee **agentic-merges** (§9) before resuming execution track.
3. Set `execution/<track>/meta.json` → `design_version` / `spec_version` ≥ current manifest version.

**Verify:** No track resumes on stale spec/design version.

---

### Related

- **git_mr_guidelines.md** § **Sections** — remote review body at ship time.
- **Recipe — Clippable MR generation (git paste)** — export after §5 sync.
- **§ How to do Agentic Merge when there is conflict in Agents .md while merging** — merge discipline.
- **repo_overview.md** § **MR slug packs** — paths for this workspace.

---

# LSAI Subagent Documentation Template

This document describes the template format for documenting subagent projects. Each subagent should have its own documentation file following this structure.

VERY IMPORTANT:
- NOT ALL PROJECTS will require the sub-agent to have all the sections
- **Python / monorepo venvs (optional):** The mapping below is a **legacy OmMeGo / Lightsphere-style** convention for large multi-product trees with **`~/.virtualenvs`** and a central build server layout. **Ignore it** when this workspace has no Python runtime or those paths do not exist; use whatever toolchain your project documents (`npm`, `cargo`, system `python3`, etc.).

**Legacy venv map:** Org-specific (`~/.virtualenvs/<product>`) — **ignore** in portable/python-free workspaces. **KPI recipes:** experimental; skip unless **`{COMPANY_DOC_PREFIX}kpi.md`** exists.

## Document Structure

Sub-agent file: **`<project>_subagent.md`** under **`.cursor/context/`**. **Not every project needs every subsection.**

### Header

`# <Project Name>: <Brief Description>` · `Last updated: MMM DD YYYY`

### (a) Design Section

**Purpose:** Architecture — **no release numbers** in Design (releases live in § (b) only).

| Subsection | When | Min content |
|------------|------|-------------|
| **Overview** | Always | Problem + approach (1 para) |
| **Core Design Decisions** | Always | 3–7 numbered (rationale, approach, benefits) |
| **Technical Implementation Details** | Usually | Data structures, integration, errors |
| **Key Components** | If multi-module | Classes/paths table |
| **Layered Implementation sequence** | Complex work | Global layers — see **Global layer numbering** below |
| **Layered implementation and per-layer E2E** | Testable slices | Extend primary suite per layer — **lsai_e2e.md** |
| **Related Files** | Always | Paths + **bidirectional Cited by** |

#### Global layer numbering (releases, layers, and steps)

**Canonical detail** — MR summary: **git_mr_guidelines.md** § **Global layer numbering (read first)**.

- **Release** — MR title version (what ships); **not** a layer index.
- **Layer** — **Global** monotonic index (never resets per release). Reference **Layer L, Step k**.
- **Step** — Restarts at 1 inside each layer; not hierarchical (no 1.1).

#### Updating Step Status

Compare branch vs integration branch; mark steps `[completed|started|pending]`.

#### Alpha test cases (authoring)

**lsai_e2e.md** for Run/Verify templates. **Manual cases** must specify: (1) identity/roles (2) surface (3) product if multi-app (4) happy Run/Verify (5) negative path (6) no cross-tenant leakage (7) evidence path. Tag **Layer L, Step k**.

---

### (b) Project MR Tracking

**Purpose:** Follow git MR/PR format (**git_mr_guidelines.md**) for tracking project progress and testing requirements.

**Reference:** See `.cursor/context/git_mr_guidelines.md` for full MR format specification.

**Hard guardrails + anti-patterns:** **git_mr_guidelines.md** § introduction **Do NOT do these** and § **MR structure guardrails** — normative. This § (b) follows that scaffold exactly.

#### Title
- Format: `<Platform scope>: Release X: <Project title>`
- Examples: `Server Only: Release 1: LSAI Chat Testing with Conversation History Injection`
- Use major version (X) for initial release, X.1, X.2 for follow-ups

#### Layered Implementation Sequence
- Sequence in which layer steps ship; copy **global layer numbers** and names from the Design doc **Layered Implementation sequence** (must match). **Step 1, 2, 3…** restarts within each **global** layer. See **§ Document Structure — Layered Implementation sequence — Global layer numbering (releases, layers, and steps)** for **Release** vs **global layer** vs **Step**.

#### Details
- Itemized bullet list using Markdown with at most two levels
- Group related changes under bold category headers
- Move completed TODO items here once finished
- Be specific about what was added/modified/deleted
- Include function names, file paths, and key implementation details

## More Details
- For deeper details for layered steps you can put more details if needed here


#### TODO
- List everything blocking the MR from merging right now
- When an item is completed, relocate it to `Details`
- If none, state "None"

#### TODO Next release
- Items intentionally deferred to the next release cycle
- If none, state "None"

#### TODO Future release
- Longer-term backlog items
- Ideas for future enhancements
- Technical debt considerations

#### Alpha Testing
- **lsai_e2e.md recipe quick reference:** For layered interstitial iteration loop (3-step, when to commit, stop server), see Section 2(e). For per-run evidence artifacts (interstitial_fixes, local_error_log), see Section 2(f). For alpha test design template (Run/Verify, numbering, edge coverage), see Section 2(g).
- **Manual test authoring:** See **§ Document Structure — Alpha test cases (authoring)** — identity, surface, product, happy + negative paths, evidence; security flows need **no-leak** wording.
- Numbered list of manual test cases (each entry must satisfy the specificity rules above)
- alpha tests should map to layered implementation sequence with testing for each layer as the group for tests
- format can be either: (a) a flat numbered list, or (b) layer-grouped headings (for example `Layer 2`, `Layer 5`) with tests under each heading
- When interstitial logs exist for a layer, add a dedicated subsection in MR alpha testing using this title format:
  - `Release <N>: Layer<K> Interstitial E2E Tests`
- Under that subsection, document every interstitial run as numbered entries:
  - `Interstitial Run 1`, `Interstitial Run 2`, ... in execution order
  - Include 1-2 sub-bullets per run: (a) what was tested/changed, (b) outcome and gate result (pass/fail/blocked)
- Each run entry should include the mapped interstitial identifier (for example `Local test sequence no.`) and any custom alpha test IDs (for example `L2-S3-03`) used as evidence
- If a run was blocked or retried, record the reason and how closure was achieved in a later run

#### Beta Testing
- **lsai_e2e.md recipe quick reference:** For beta stage evidence and "new error" semantics (release no. + timestamp), see Section 3(d).
- Fill only for beta deployments (currently applies to OMG project)
- usually good for end-to-end testing with the moble/web app + backend. Pick this according to the code changes
- If not applicable, state "Not applicable" with brief reason
- Optional concession: inside the single global **Beta Testing** section, evidence may be grouped by layer headings when tracks differ; if the same plan applies to all layers, use one block and a **Scope** line—do not repeat identical per-layer blocks.

#### Gamma Testing
- Use when code is deployed on prod one-box for pre-merge validation
- Useful for scenarios hard to test on beta or when beta unavailable
- If not applicable, state "Not applicable" with brief reason

---

### (c) Design Email Tracking

**Purpose:** Capture design-level bullet points for email communication. Keep crisp and clustered by major categories.

**Format Guidelines:**
- Use bold for category labels followed by colon
- Keep bullets concise (one line when possible)
- Cluster related items under logical categories
- Focus on design decisions, not implementation details
- Use consistent terminology throughout

#### Typical Categories (adjust as needed):
- **Core Architecture Changes:** Major structural modifications
- **Integration Points:** How it connects with other systems
- **Data Flow:** How data moves through the system
- **Performance Considerations:** Speed, scalability, resource usage
- **Error Handling:** Failure modes and recovery strategies
- **Configuration:** Settings, parameters, environment variables
- **Testing Infrastructure:** How the feature is tested
- **Code Quality and Maintainability:** Best practices, documentation, reusability

**Example Structure:**
```text
Core Architecture Changes
- <Feature name>: brief description of architectural change
- <Another feature>: brief description

Integration Points
- <System/Component>: how integration works

<Additional Category>
- <Item>: description
```

---

## Usage Guidelines

1. **When to create:** Create a new subagent doc when starting a new subagent project or major enhancement
2. **When to update:** Update the "Last updated" date whenever significant changes are made
   - IMPORTANT: ALWAYS FOLLOW THE LATEST SUB-AGENT template in this file when updating a sub-agent NOT the old format of the sub-agent whenever there is a format contradiction
   - IMPROTANT: if there are TODOs section already in the MR section of the project subagent, DO NOT MODIFY the points in these sections 
     unless the user is expilicity asking for specific changes, else leave them unchanged 
   - Last updated should ALWAYS be today's date - you can use a shell command to look it up. DO NOT guess this date.

3. **How to generate:**
   - Use `git diff <base_branch>` to identify all changes
   - Review code changes to extract design decisions
   - Follow the three-section structure (Design, MR Tracking, Design Email)
   - Include additional sections as needed based on sub-agent complexity:
     - **Key Components**: Always include if the sub-agent has multiple classes/modules
     - **Type Definitions**: Include if enums or type mappings are central to functionality
     - **Processing Flows**: Include for complex multi-step operations
     - **Data Schemas**: Include if data structures are non-trivial or need documentation
     - **Error Handling**: Include if error handling is complex or provider-specific
     - **Configuration**: Include if multiple credentials or config files are required
     - **Workflow Integration**: Include if the sub-agent integrates with workflow system
     - **Data Storage**: Include if data is stored in user profiles or complex structures
     - **Security Considerations**: Include if security measures are important
     - **Testing Infrastructure**: Include if special testing approaches are used
     - **Limitations**: Always include to document known constraints
     - **Related Files**: Always include for reference
   - Reference `git_mr_guidelines.md` for MR format
   - **Git paste (clippable MR):** Do **not** use this bullet list alone—follow **Recipe — Clippable MR generation (git paste)** (branch diff vs base + format + clipboard).
4. **Maintenance:** Keep the document current as the project evolves
5. **Accessibility:** Store in `.cursor/context/` so it ships with the repo and is available to Cursor agents
6. **Completeness:** The documentation should be comprehensive enough that someone new to the codebase can understand the sub-agent's architecture, usage, and limitations

## Example References

Add **`{your_project}_subagent.md`** under **`.cursor/context/`** as your canonical example once it exists; this minimal bundle does not ship sample product sub-agents.

