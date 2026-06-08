# Merge Request / Pull Request format (full detail)

Last updated: 2026-05-05

We follow this format for **every remote code review** (merge request, pull request, or your host’s equivalent) and for in-repo **`## (b) Project MR Tracking`** blocks inside project sub-agent docs—the canonical shape, guardrails, and field meanings are under **§ Sections** below. **Which git host and UI labels you use** (GitHub, GitLab, etc.) is **project context** — see **`repo_overview.md`** § **Git and review context**; recipes stay **git-native** (`git diff`, branches, remotes) and do not hard-code a vendor.

**Cited by:** `coding_standards.md`, `repo_overview.md`, `lsai_subagents.md` (§ (b) guardrails cite here), `l345_router.md`, `lsai_superagent.md`, `agentic_merge.md`, and other agents that reference MR discipline.

Set **`{CONTEXT_DIR}`** and **`{COMPANY_DOC_PREFIX}`** the same way as in **`coding_standards.md`** / **`repo_overview.md`** (doc prefix may be empty).

Use this order for the **remote review description** (paste field on your git host) and for subsection headings under **`(b) Project MR Tracking`** in sub-agent docs: **Title** → **Layered Implementation Sequence** → **Details** → **More Details** → **TODO** → **TODO Next release** → **TODO Future release** → **Alpha Testing** → **Beta Testing** → **Gamma Testing**. (Read-only **Layer** / **Step** / **Status** matrices: **§ Recipe — Layer/step status table**.)

### Do NOT do these (common MR failures)

- Do **not** leave old shipped release blocks open as active scope.
- Do **not** track bugs in Design; keep bug tracking in MR release sections.
- Do **not** create multiple **Layered Implementation Sequence** sections.
- Do **not** treat layer numbering as local per release; layers are global slices.
- Do **not** model layer internals as “tasks”; use ordered **steps**.
- Do **not** omit **Status tracker:** on any LIS **Step**, put dates on that line, or park status-only prose outside the step list (Approach, layer intros, duplicate norms).
- Do **not** fragment planning into many single-step layers without explicit rationale.
- Do **not** put alpha unit/integration test definitions inside layer bodies.
- Do **not** create separate per-layer alpha sections **outside** the single global **Alpha Testing** section; if grouping by layer, keep those groups **inside** global **Alpha Testing**.
- Do **not** create separate per-layer beta sections **outside** the single global **Beta Testing** section; if grouping by layer, keep those groups **inside** global **Beta Testing**.
- Do **not** create multiple **Alpha Testing** or **Beta Testing** sections.
- Do **not** place **Alpha/Beta/Gamma** testing sections outside the MR / **`(b)`** block.
- Do **not** rename, qualify, or extend the **Alpha Testing** or **Beta Testing** heading (e.g. `Alpha Testing (Release 2.3)` or `Beta Testing — async track`); use body text or bold under the heading for scope.
- Do **not** add a second markdown heading that competes with those titles (e.g. `##### Release …` as a section head immediately under **Beta Testing**); use bold lead-ins or bullets instead.
- Do **not** tuck a second **Alpha Testing** (or beta) block under **Layered Implementation Sequence** as if it were another top-level MR subsection.

Templated sections for the MR start from here; when creating an MR, create these sections and content following the guidelines below **exactly in this order**.

---

## Sections

Normative **review body scaffold** for git-host paste and for **`## (b) Project MR Tracking`** blocks. Use the following **`##` / `###` headings** in the **order** given in the introduction above (**Title** → **Layered Implementation Sequence** → … → **Gamma Testing**). Other agents and **`l345_router.md`** cite this file as **`git_mr_guidelines.md` | section: Sections** when they mean this scaffold.

---

## Title

- Format: `<Server Only/Android/iOS/Web/etc>: Release X: <Project title>` (same pattern as platform scope in the MR body).
- The title repeats across multiple MRs for the same project. **Release** uses **version-style** numbering: **minor** bumps for smaller changes (e.g. `1.5`, `1.6`), **major** bumps for large deltas (e.g. `2.0`, `3.0`). Initial vs follow-up: use major **X** for the first release of a line; **X.1**, **X.2** for follow-ups when that convention fits the project.
- Example: `Server Only: Release 1: Chat testing with conversation history injection` (replace with your product name).

---

## Global layer numbering (read first)

**Three separate numbering systems** — do not mix them:

| Name | What it is | How it counts |
|------|------------|----------------|
| **Release** | What ships in **this** MR; appears in the MR **Title** (`Release 1.5`, `Release 2.0`, …). | Version-style only (`1.5`, `1.6`, `2.0`). **Not** a layer index. |
| **Layer (global)** | One **logical implementation slice** in the product’s **single ordered backlog** across **all pending releases**. | **One global counter per project** — **never restarts** when a new release MR opens. Say **“Layer 12”** without naming a release; agents and humans use **one** index. Layers **can move** to a different release MR without renumbering. |
| **Step** | One implementable unit **inside** a layer’s **Detailed Requirements/Design**. | **Step 1, 2, 3…** **restarts at Step 1** for **each** layer. Plain ordinals — **not** `1.1` / `2.3`, **not** one run-on count across layers. Cross-reference **Layer L, Step k**. |

**Why global layers:** References stay stable when scope **shifts between releases**; you do not need to say “which release” for **Layer 14** — the number is enough.

**Canonical detail** (edge cases, examples, E2E, alpha mapping): **`{CONTEXT_DIR}/{COMPANY_DOC_PREFIX}subagents.md`** § Document Structure — **Layered Implementation sequence** — **Global layer numbering (releases, layers, and steps)**.

---

### Layered Implementation Sequence (for complex projects)

- Ordered list of implementation **steps** to execute one-by-one (use ordered **steps** inside each layer—do **not** model layer internals as ad-hoc “tasks”).
- List layers by **global layer number** (e.g. **Layer 8**, **Layer 9**), not “Layer 1 of this release.” Each layer has **Approach** (high-level bullets) and **Detailed Requirements/Design** with **Step 1, 2, 3…** per layer. Copy **global layer numbers** and names from the Design doc **Layered Implementation sequence** (must match).
- **Release vs layer vs step:** The MR **Title** carries the **release** label (what ships). **Layer** indices name implementation slices and are **independent of the release number** — scope can move between releases. **Steps** restart at **Step 1** for each layer. Use **Layer L, Step k** when cross-referencing (see **`{COMPANY_DOC_PREFIX}subagents.md`** § Document Structure — **Layered Implementation sequence — Global layer numbering (releases, layers, and steps)** and **Releases, layers, and steps (numbering)**).
- **One section only:** Keep exactly one **Layered Implementation Sequence** block per MR block. Do not duplicate this heading under releases or append alternate copies later in the file.
- **Per-step status:** Each **Step** has one nested **Status tracker:** line: **Not started** · **In progress** · **Complete** · **N/A** only (no dates). Keep it only under that step—no status-only paragraphs elsewhere. User-facing roll-up of layers/steps/statuses: **§ Recipe — Layer/step status table**.
- **Layer quality bar:** Avoid creating many tiny one-step layers. Each layer should represent a meaningful slice (usually multiple related steps) unless a single-step layer is explicitly justified by risk/isolation.
- **UX:** Early layers can ship UX with fake data for human verification before wiring real data.
- **API / endpoints:** Add **per-layer E2E checkpoints** as needed (which test file was extended after which layer); see **`{COMPANY_DOC_PREFIX}subagents.md`** § Document Structure — **Layered implementation and per-layer E2E checkpoints**.

### MR structure guardrails (hard requirements)

- Keep **exactly one active release** scope for current work: **one** clear release title / block; close out **stale shipped** release blocks so old releases do not linger as active.
- Keep bugs out of **Design**: bug tracking belongs in MR sections (`TODO`, `TODO Next release`, `TODO Future release`), not in Design architecture text.
- Keep exactly **one** **Layered Implementation Sequence** section per MR block.
- **Layer** numbers are **global** implementation slices; they do **not** reset per release label.
- Use **steps** inside layers; do not model layer contents as separate “tasks.”
- Keep unit/integration **alpha** test definitions in the **global Alpha Testing** section, not inside each layer body. Layers may reference checkpoint IDs; canonical test definitions live under **Alpha Testing**.
- Keep exactly **one** global **Alpha Testing**, **one** **Beta Testing**, and **one** **Gamma Testing** section **inside** the MR / **`(b)`** block — do not place them elsewhere in the sub-agent doc.
- The markdown heading for each must be titled **exactly** `Alpha Testing`, `Beta Testing`, or `Gamma Testing` — no extra words, release suffixes, or subtitles **in the heading line**. Scope, release, or “restored from…” notes belong in **body** text or **bold** lines under the heading.
- Do not create duplicate alpha/beta/gamma sections.
- **Allowed (alpha):** Inside the **single** **Alpha Testing** section, tests may be grouped by layer headings (e.g. `Layer 2`, `Layer 5`) with cases nested under each layer — optional; a flat numbered list is also fine.
- **Allowed (beta):** Inside the **single** **Beta Testing** section, evidence may be grouped by layer when tracks genuinely differ. If the **same** artifact, run/verify, and accounts apply to **every** layer, **deduplicate**: one block plus a short **Scope** line.

### Details

- Itemized bullet list using Markdown with at most two levels (host-agnostic).
- Group related changes under bold category headers.
- Completed TODO items move here once finished.
- Be specific: what was added/modified/deleted; function names, file paths, key implementation details.

### More Details

- Optional deeper detail for layered steps when the **Details** list would become unwieldy.

### TODO

- Everything blocking merge **right now**.
- When an item is completed, move it to **Details**.
- If none: **None**.

### TODO Next release

- Intentionally deferred to the next release cycle.
- If none: **None**.
- **Versioned products (clippable MR generation):** For an MR that ships **Release R**, this subsection should track **Release R+1** per the project sub-agent’s **Release Roadmap** / **Open MR** ordering—not the next “big” technical chunk if that skips a documented intermediate release. Full rule: **`{COMPANY_DOC_PREFIX}subagents.md`** § **Recipe — Clippable MR generation (git paste)** — step 4, **Release-order guard**.

### TODO Future release

- Longer-term backlog, ideas, technical debt.
- If none: **None**.
- **Versioned products:** After **TODO Next release** holds **R+1**, use this subsection for **R+2** onward (and other deferred arcs). Do **not** leave **None** when the roadmap already lists a concrete **R+2**. Same citation as **TODO Next release** above.

### Alpha Testing

- **Purpose of this section:** Numbered manual test cases: **Run:** (exact command or steps) and **Verify:** (what confirms success). Keep **exactly one** **Alpha Testing** heading in the MR (see **MR structure guardrails** and **Do NOT do these** above).
- **Layer cadence:** You may order or group cases by **global layer** (bold lines or small headings like `Layer 5`) **inside** this section only — organizational, not a second outline-level alpha block.
- **Agentic / iterative sweeps:** Per-round notes go in **interstitial logs, test JSON, or MR Details**; **batch-update** curated **`{CONTEXT_DIR}/*.md`** only when the iteration **stops** — **`{COMPANY_DOC_PREFIX}superagent.md`** § **Router Architecture and Builder — Recipe documentation cadence**.

**Authoring and evidence (quality bar — not alternate MR headings)**

- **E2E recipes:** Layered interstitial loop, evidence files, **Run/Verify** shape — **`{COMPANY_DOC_PREFIX}e2e.md`** (your org’s E2E / environments agent).
- **Manual case specificity** (identity, surface, product, happy/negative, evidence, no-leak where relevant): **`{COMPANY_DOC_PREFIX}subagents.md`** § Document Structure — **How to generate Alpha test cases** — **Manual test cases — required specificity**.
- **Interstitial evidence in the MR:** When logging interstitial runs for a layer, you may add a **body** subsection (not a competing `##`/`###` MR title) using this label: `Release <N>: Layer<K> Interstitial E2E Tests`. Under it, numbered **`Interstitial Run 1`**, **`Interstitial Run 2`**, … in order; 1–2 sub-bullets each: what changed/tested, outcome (pass/fail/blocked).

### Beta Testing

- **Purpose:** Beta deployment evidence; keep **exactly one** **Beta Testing** heading (see guardrails above).
- **Layer cadence:** Same as in **MR structure guardrails** — optional layer grouping **inside** this section; deduplicate when one plan applies to all layers.
- Fill only when the release uses a **beta / staging** track (which products use beta is org-specific).
- If not applicable: **Not applicable** + brief reason.
- **Iterative fixes:** Same curated-doc vs per-iteration data rule as Alpha — **`{COMPANY_DOC_PREFIX}superagent.md`** § **Recipe documentation cadence**; **`{COMPANY_DOC_PREFIX}e2e.md`** (beta / remote sections when present).

### Gamma Testing

- Use when the branch is on a **prod one-box** before merge, or when beta cannot cover the scenario.
- If not applicable: **Not applicable** + brief reason.

Always use clear, crisp language throughout the MR.

---

## Clippable MR export (preflight — mandatory)

Some workflows copy the sub-agent **`## (b) Project MR Tracking`** block into a disposable **`{CONTEXT_DIR}/MR.md`** (or similar scratch path) for pasting into the **remote review description** on your git host — see **`{COMPANY_DOC_PREFIX}subagents.md`** § **Recipe — Clippable MR generation (git paste)**. Export must **not** run until preflight passes.

**Three tiers (run in order when a slug pack is in use):**

### Tier A — Slug pack (when using **Recipe — Layered MR slug pack**)

Run **before** syncing slug → **§ (b)** or exporting paste. Source: **`~/data/{project_slug}/runs/{run_slug}/`**.

| Check | Rule |
|-------|------|
| **Manifest** | `manifest.json` parses; `project_slug`, `run_slug` (or legacy `mr_slug`), `owner`, `git_branch`, `last_updated` present |
| **Branch** | `git branch --show-current` equals `manifest.git_branch` (or documented waiver in `merges/`) |
| **Layers** | `specification/spec.md`, `design/design.md`, and each track in `execution/tracks.json` have `steps.md` |
| **CoT boundary** | Confirm export will **exclude** all `cot.md` files and slug handoff metadata from the PR body |
| **Sync readiness** | Spec has acceptance criteria; design assigns scope per execution track (or explicit N/A) |

**If Tier A fails:** **Stop.** Fix slug pack or branch; do not sync or paste.

### Tier B — § (b) block shape (always — legacy shippable MR)

Read the MR block in the sub-agent file (typically **`## (b) Project MR Tracking`** through end of that section—including **Alpha / Beta / Gamma** and **TODO Next / Future** when present). Confirm it matches **§ Sections** above:

- Heading order: **Title** → **Layered Implementation Sequence** → **Details** → … → **Gamma Testing**
- **Release / Layer / Step** rules when **Layered Implementation Sequence** is used
- **Details** / **TODO** / **Alpha** / **Beta** / **Gamma** present or explicit **Not applicable**
- **Do NOT** list and **MR structure guardrails** satisfied
- One LIS only; **global** layer numbers; every LIS **Step** has **Status tracker:**
- No bug-tracking in Design (§ **(a)**); alpha/beta/gamma once and only inside **`(b)`**
- **Alpha Testing** / **Beta Testing** / **Gamma Testing** heading lines exactly those titles
- Alpha definitions centralized under **Alpha Testing** (flat or layer-grouped inside that section)

**Slug sync consistency (when Tier A ran):** After slug → **§ (b)** mapping (**lsai_subagents.md** slug recipe §5), spot-check that **Layered Implementation Sequence** and **Details** reflect `design/design.md` and completed `execution/<track>/steps.md`—no orphan slug-only content left unstated in **§ (b)**.

**If Tier B fails:** **Stop.** Do not create `MR.md` or copy to clipboard. Push back with **named** fixes (Recipe of Recipes pushback style — specific bullets, not “fix the MR”).

### Tier C — Export composition (Clippable MR git paste)

Before scratch write / clipboard:

| Check | Rule |
|-------|------|
| **Diff source** | Recompute from **`git diff <base>...HEAD`** — never treat stale **`.cursor/context/MR.md`** as authoritative |
| **Base branch** | Use **`{git_default_branch}`** from **`repo_overview.md`** § **Git and review context** (detect via `git symbolic-ref refs/remotes/origin/HEAD` or project table; common values: `main`, `master`) |
| **Paste target** | Markdown body for your host’s review UI; optional host CLI from **`{git_review_cli}`** when set (e.g. `gh`, `glab`) — **never required**; clipboard paste always valid |
| **Formal parameters** | Clippable MR recipe formal params bound — push back if ambiguous per **lsai_subagents.md** § **Recipe of Recipes** → **Formal parameters** |

**If Tier C fails:** **Stop** before clipboard.

---

**Order of operations (summary)**

1. **Tier A** (if slug pack) → **Tier B** → sync slug → **§ (b)** if needed → re-run **Tier B**
2. **Tier C** → **Recipe — Clippable MR generation (git paste)** steps 2–9
3. Paste into your git host’s review description (or open review via **`{git_review_cli}`** when configured)

If the user asks for a **layer/step/status table** only, use **§ Recipe — Layer/step status table** (read-only; does not bypass Tier B when exporting paste).

---

## Recipe — Layer/step status table

Use when the user wants a **read-only** matrix of **Layer**, **Step**, short **detail**, and **Status tracker** from a project **`(b) Project MR Tracking`** file (not for authoring MR body paste).

1. Open the authoritative **`(b)`** doc (path from context—e.g. **`{CONTEXT_DIR}/<your-project-b-agent>.md`** for the release you are rolling up).
2. Locate **`#### Layered Implementation Sequence`** or a release-scoped **`##### Layered Implementation Sequence (…)`**; stay inside the requested **release** / layer range.
3. For each **Layer N** in scope, take **Detailed Requirements/Design** **Step** bullets only (skip **`##### … completion record`** / checklist-only blocks unless they are the sole step list). **Detail** = one summary sentence per step; **Status** = the nested **`Status tracker:`** value (**Not started** / **In progress** / **Complete** / **N/A**); if missing, mark **missing** in the table.
4. Output one markdown table per layer: **Step | Detail (summary) | Status**; one footer line with source path.

---

## Slug pack → shippable MR (Layered MR slug pack)

When using **`lsai_subagents.md`** § **Recipe — Layered MR slug pack**, collaboration artifacts live under **`~/data/{project_slug}/runs/{run_slug}/`**. The **shippable** reviewer-facing body still follows **§ Sections** above.

**Flow:** slug spec/design/execution → sync into sub-agent **`## (b) Project MR Tracking`** → preflight (**§ Clippable MR export**) → **Recipe — Clippable MR generation (git paste)** → paste into remote review on your git host.

CoT files (`cot.md`) and slug handoff metadata **do not** go into the PR body. See slug recipe **§5 Legacy shippable MR** for the mapping table.

---

## Related Files

- **Layer/step/status roll-up recipe:** **§ Recipe — Layer/step status table** (this file).
- **Repo overview:** **`{CONTEXT_DIR}/repo_overview.md`** — Top-level layout, build/test commands, sub-agent mapping.
- **Coding standards:** **`{CONTEXT_DIR}/coding_standards.md`** — When your tree includes them: Python, TypeScript, cross-cutting rules.
- **Sub-agent workflow:** **`{CONTEXT_DIR}/{COMPANY_DOC_PREFIX}subagents.md`** — **Recipe — Layered MR slug pack** (portable spec/design/execution packs), Clippable MR recipe, layered design, alpha test authoring. **MR shape and guardrails** are defined in **this file** (**§ Sections**).
- **L345 router:** **`{CONTEXT_DIR}/l345_router.md`** — L3/L4/L5 agentic work; use when creating or modifying agents, recipes, or routers.
- **Router documentation:** **`{CONTEXT_DIR}/{COMPANY_DOC_PREFIX}superagent.md`** § Router Architecture and Builder — Router usage, building, architecture, and both router types.
