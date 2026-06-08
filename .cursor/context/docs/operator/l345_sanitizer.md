# Recipe — Base L345 agents refresher (sanitization workspace)

**Cited by:** `lsai_superagent.md` (stub pointer), `l345_router.md` (recipe index, topic **base l345 agents refresher**).

**Portable stack:** Skip unless sanitizing for `base_l345/` publish.

**Purpose:** For each basename in turn, **read** the **original** internal agent under **`{REPO_ROOT}/.cursor/context/`**, **sanitize** into **`{REPO_ROOT}/OAIRuntime/sa_install/base_l345/`** (overwriting any prior **`base_l345`** copy — **do not** use old **`base_l345`** files as input or diff baseline), then **compare** that **fresh** sanitized file **only** to the **same** **original** path you sanitized **from**, and obtain **one** user approval before the next basename. Outputs are **Apache-2.0–friendly** for **`l345_base` / `base_l345`** / installer fallbacks (**§ Release 1.6 — (f)**; **Layer 27**). Follow **lsai_subagents.md** § **(1) How a recipe should look like** (numbered steps, **Run:** / **Verify:**, crisp tables).

**Prerequisites**
- **`{REPO_ROOT}`** is the checkout root that contains **`.cursor/context/`** and **`OAIRuntime/sa_install/base_l345`**.
- **Run:** `mkdir -p ~/data/superagents/sanitizer`
- **Verify:** **`~/data/superagents/sanitizer/`** exists (flat root only — **no** `reviews/`, `cleaning_logs/`, `review_corrections/` subdirectories).

**Paths (normative)**

Let **`stem`** be basename **`B`** with the trailing **`.md`** removed (e.g. `coding_standards.md` → **`coding_standards`**). **Suffix notation:** all sanitizer artifacts are **only** files in **`~/data/superagents/sanitizer/`** named **`{stem}.<suffix>.md`** (plus **`selected_files.txt`**). **Do not** create **`checker_why.log`** or other parallel log files; checker failures and stop reasons go into **`{stem}.corrections.md`** (see Steps 2, 4, 6).

| Role | Path |
|------|------|
| **Sanitization workspace (outputs)** | **`{REPO_ROOT}/OAIRuntime/sa_install/base_l345`** |
| **Optional promote target** | **`{REPO_ROOT}/OAIRuntime/sa_install/l345_base`** |
| **Original sources (read-only; diff left-hand side)** | **`{REPO_ROOT}/.cursor/context/`** (per Step 2 — e.g. **`~/pr/.cursor/context/{B}`** when **`{REPO_ROOT}`** is **`~/pr`**) |
| **Input list** | **`~/data/superagents/sanitizer/selected_files.txt`** |
| **Optional pass header (mode / release id)** | **`~/data/superagents/sanitizer/sanitizer.pass.md`** — if absent, default **Mode B** |
| **Per-file cluster table (Step 5)** | **`~/data/superagents/sanitizer/{stem}.reviews.md`** |
| **Accepted changelog (Steps 6 / 6B)** | **`~/data/superagents/sanitizer/{stem}.cleaning.md`** |
| **Audit trail, checker failures, session accept (Steps 2, 4, 6, 6B)** | **`~/data/superagents/sanitizer/{stem}.corrections.md`** |
| **L345 bundle cross-reference cleanup log (Step 7 — mandatory)** | **`~/data/superagents/sanitizer/ref_cleanup.md`** — **one file per pass**, append or replace per operator convention (see **Step 7** below) |
| **RSI disk mirror (optional, Step 9)** | **`~/data/superagents/sanitizer/sanitizer.rsi.md`** |

**Interstitial discipline:** Write artifacts under **`~/data/superagents/sanitizer/`** as you work (**alpha** spirit: **lsai_e2e.md** — **Per-run evidence** and **Beta / remote evidence files**). **Recipe documentation cadence:** batch-edit **this** subsection in **`lsai_superagent.md`** only when **policy** changes—not after every basename.

**Execution modes (declare in `sanitizer.pass.md` or chat before Step 1)**
- **Mode A — MR / external reviewer:** Use **Step 6** (multi-round review allowed); after **Step 7** and **Step 8**, run **Step 9** when a **separate human reviewer** must sign off and MR evidence is required.
- **Mode B — Session operator (default for tool-using agents):** Use **Step 6B** instead of **Step 6**; run **Step 8** (router alignment—mandatory); **omit Step 9 by default.** **RSI** in this recipe means **recursive self-improvement of the recipe text** (Step 9) and the **multi-round external review loop** in Step 6—Mode B **excludes** Step **9** so a single session can complete sanitization without editing **`lsai_superagent.md`** from pass telemetry.
- **Explicit Step 9 after Mode B:** If the **session owner explicitly requests Step 9** after **Step 8** (e.g. “run RSI”), execute **Step 9** anyway; state the override in the header of **`~/data/superagents/sanitizer/sanitizer.rsi.md`** so MR evidence matches chat intent.

**Comparison contract (mandatory)**
- **Original:** The file at the **Step 2** resolved path under **`.cursor/context/`** — **unchanged** by this recipe; it is the **only** “before” side for review.
- **Sanitized:** **`{REPO_ROOT}/OAIRuntime/sa_install/base_l345/{B}`** after Steps **3–4** — **overwrite** any existing file at that path; **ignore** stale **`base_l345`** content from earlier runs when reasoning or diffing.
- **When to compare:** **Only after** the current basename has been sanitized and checker-green. **Do not** diff or approve using pre-sanitization **`base_l345`** snapshots.
- **Per-loop scope:** **Exactly one** basename per approval cycle: show **original vs sanitized** for that **`B`**, then cluster table (Step 5), then acceptance (Step **6** / **6B**), then advance to the **next** line in **`selected_files.txt`**.
- **Authoring inputs (hard guard):** When **writing** **`SAN`** in Step **3**, **do not** treat any of the following as a **source of body text** to copy, merge from, or “refresh against”: the **on-disk** file **`{REPO_ROOT}/OAIRuntime/sa_install/base_l345/{B}`** before you overwrite it; **`git show`**, **`git show HEAD:`**, or **any Git revision** of **`base_l345/{B}`**; **prior** **`~/data/superagents/sanitizer/{stem}.cleaning.md`**, **`{stem}.reviews.md`**, **`{stem}.corrections.md`**, or other **sanitizer outputs** from an earlier pass. Those exist only for **Step 4a** (diff **`ORIG` ↔ fresh `SAN`**), **Step 5–6B** evidence, and **audit**—not for **re-hydrating** **`SAN`**. **Step 3** content comes **only** from **Step 2 `ORIG`** plus the edits this recipe requires (including **S1–S3** when **`B`** is **`lsai_superagent.md`**). If the operator asked to **overwrite** **`base_l345`**, assume the previous **`base_l345/{B}`** is **wrong until replaced**; do **not** open it to decide what to ship.

**Ordering (mandatory)**
- **Run:** Process **`selected_files.txt` from first line to last**. For **each** basename, complete **Steps 2 → 3 → 4 → 4a → 5 → 6** (or **→ 6B**) before opening the next line.
- **Verify:** You never batch “sanitize every file, then compare every file”; each basename is one closed pipeline ending in **approval** before the next basename starts.

---

**Step 1 — Build `selected_files.txt`**
- **Run:** Create or overwrite **`~/data/superagents/sanitizer/selected_files.txt`**: **one basename per line** (e.g. `coding_standards.md`) for outputs under **`base_l345`** in scope this pass.
- **Verify:** File is non-empty; **no blank lines**; each line is a single **`*.md`** basename.

**Step 2 — Resolve internal source**
- **Default:** For basename **`B`**, read **`{REPO_ROOT}/.cursor/context/{B}`**.
- **Known basename mismatch (extend in MR Details when new pairs appear):**

| `base_l345` basename | Internal source |
|----------------------|-----------------|
| `git_mr_guidelines.md` | **`{REPO_ROOT}/.cursor/context/gitlab_mr_guidelines.md`** |
| `repo_overview.md` | **`{REPO_ROOT}/.cursor/context/people_ranker_overview.md`** — internal proprietary basename (**Lightsphere AI** `-pr-` monorepos); **public / catalog-facing** output basename is **`repo_overview.md`** in **`base_l345`** (see **Step 7a**). |

- If internal source is **missing** and not in the table → **stop** for **`B`**; write **`~/data/superagents/sanitizer/{stem}.corrections.md`** with timestamped **Stop** (name, expected path, action); **do not** write blind **`base_l345/{B}`**.
- **Verify:** You have the full internal document for **`B`** before Step 3.

**`lsai_superagent.md`-only supplements (run after Step 2, integrated into Step 3 before you freeze `SAN`)**

These steps apply **only** when **`B`** is **`lsai_superagent.md`**. They refine the **customer-facing** **`base_l345`** body; they do **not** replace Step **3** bullets **(a)–(f)**—run them **as part of** Step **3** authoring, then continue with Step **4** as usual.

| ID | **Run** | **Verify** |
|----|---------|------------|
| **S1 — Exclusion list (admin template)** | In **`SAN`**, the **Router Builder — Exclusion List** must **not** ship a fixed internal enumerate of proprietary basenames. Replace with **templated instructions**: the organization’s **platform admin** (or routing operator) **maintains** the list of **`.md`** files to **skip** for **domain** router topic indexing; provide **placeholder examples** only (e.g. `scratch_notes.md`, `local_MR_export.md`) and explicit prose: *Remove samples and add your org’s real exclusions—training docs, scratch exports, one-off experiments, etc.* | No employee-specific, monorepo-only, or **Lightsphere AI**-internal filenames appear as **normative** exclusions; **`git_mr_guidelines.md` / L345** rationale may stay as **one** educational bullet if needed. |
| **S2 — User POV guard (no backend architecture)** | Grep **`SAN`** for backend implementation markers: **`LSAIEndpoint`**, **`LSAISuperAgent`**, **`ALLOWED_ACTIONS`**, concrete **`/superagent`** action inventories beyond user-facing CLI language, **S3** object layouts, **gzip** / **tar** bootstrap wire-up, internal **Release** layer tables, **provider_id** path patterns, or other **server** design. **Rephrase or delete** so remaining technical content is **CLI**, **Cursor**, **local `sa_install/` scripts**, **`.cursor/context/`**, and **user-visible** service behavior (sign-in, org secret, session, “hosted catalog”). Router-builder **topic pipeline** may remain as **local operator tooling**, not as a description of **how the service is implemented**. | A reader without server access cannot infer **our** backend class diagram, storage tree, or deployment topology from **`SAN`** alone. |
| **S3 — Paper-aligned teaching (public band only)** | After Step **2**, pull **teaching** content from **`lsai_superagent.md`** § **SuperAgent System View for Release to Outside World — Key contributions** and (if needed) **`lsai_superagent_paper.md`** **Band A — Intent** narrative constraints—**not** **R1–R9** toolchain, **not** MR/slider/**LSAISlider** tables, **not** `experiments/paper/` paths. Add **at most one** short subsection to **`SAN`** (e.g. **Paper-aligned concepts** or expand **Core ideas**) with **pedagogy-safe** bullets: multi-level brain governance, recipes as actionable procedures, **vision** beyond a single context dump, interstitial layering, reflect-and-repair across instruction layers. Point to **`oai-public`** **`docs/`** for the **PDF** and **`CITATION.cff`**—do **not** paste manuscript build commands. | New prose is **Apache-2.0–friendly**; no duplication of **`lsai_superagent_paper.md`** recipes; **Further reading (public)** stays the canonical pointer for depth. |

**Step 3 — Sanitization pass (current basename only)**
- **Run:** **Write** (create or **overwrite**) **`{REPO_ROOT}/OAIRuntime/sa_install/base_l345/{B}`** from the Step 2 source. **Treat any prior `base_l345/{B}` as irrelevant** — do not read it for content, merge, or baseline diff. **Do not** use **`git`** history of **`base_l345`** or **old sanitizer `*.md`** under **`~/data/superagents/sanitizer/`** to assemble **`SAN`** (see **Comparison contract — Authoring inputs**).
  - **(a)** Remove or neutralize **LSAI-only proprietary** material where required.
  - **(b)** Replace internal acronyms, **literal bucket names**, **host- or monorepo-specific paths** with **`{STAGE}`**, **`{BUCKET}`**, **`{WORKSPACE_ROOT}`**, **`{PACKAGE_NAME}`**, **`{PROVIDER_ID}`**, **`{REGION}`**; add a short *set in your environment* note where helpful.
  - **(c)** Keep alpha/beta/gamma **procedure and ordering**; strip concrete internals; template paths and names.
  - **(d)** Delete narrow **implementation-specific security** pointers; keep general safe-operation guidance.
  - **(e)** Expect heavier edits for **`lsai_e2e.md`** when listed.
  - **(f)** Target tone: **Apache-2.0** / **ommego.ai** base-agent posture.
  - **(g)** **Agent brain map recipe (user-facing — preserve in full):** When **`B`** is **`lsai_subagents.md`**, the **## Recipe — Agent brain map HTML producer** block is **operator- and partner-facing**: **`brain_map_produce.py`** / **`brain_map_template.html`** under **`sa_scripts/`**, the **`Run:`** / **`Verify:`** steps (including **List**/**Fisheye** toggle and **`--no-open-browser`**), **`MR_HEADING_RE`**, and **Cursor `file://` handoff** must **ship in `base_l345` with the same substantive instructions** after sanitization—**do not** redact, fold away, or relabel it as internal-only boilerplate. **Only** change that recipe when an MR **explicitly** moves tooling or rewrites behavior and updates paths in the **same** change set.
- **Do not** bulk-delete to pass Step 4; prefer **retention + templating**.
- **Verify:** **`base_l345/{B}`** exists, is non-empty, and reflects intentional edits.

**Step 4 — Checker**
- **Run:** For this **`B`** only, pass/fail checks (scripted or manual) on **`base_l345/{B}`** (the **new** sanitized body): forbidden internal bucket/path residue outside agreed placeholders; sensible heading structure; **links** must not require VPN-only or monorepo-only access without replacement.
- **Run (fenced blocks vs headings):** Walk the file and track **` ``` `** fences. **Fail** if any line that looks like a normative markdown heading (**`## `** or **`### `** at column 0) appears **inside** an open fence—those headings are invisible to **Step 8** heading checks and to readers’ outline. Close the fence **before** the next real **`##`/`###`** you intend as document structure (common mistake: a **` ```bash `** under “Usage example” that never closes before **`## …`**).
- **On fail:** Append a **timestamped** `### Checker failure` block to **`~/data/superagents/sanitizer/{stem}.corrections.md`** (rule id, excerpt); return to Step 3 until green or MR **Details** records a **waiver** (owner + reason).
- **Verify:** Checker is green for **`B`**. **Optional:** Re-collect **`##`/`###`** only **outside** fences (same idea as **Step 8**) to confirm no swallowed headings.

**Step 4a — Compare sanitized file to original (one basename; before cluster table)**
- **Run:** With **`ORIG`** = Step 2 resolved path (under **`.cursor/context/`**) and **`SAN`** = **`{REPO_ROOT}/OAIRuntime/sa_install/base_l345/{B}`**, produce a **unified diff or side-by-side summary** of **ORIG** (original, unchanged) vs **SAN** (just sanitized). **Example:** `git diff --no-index -- "$ORIG" "$SAN"` from a shell (**document** in MR **Details** if your **`git`** build requires swapped args for “old vs new” hunk headers). **Print** the diff (or a faithful truncated summary with **explicit** “truncated” notice) **in chat for this `B` only** — so the operator approves against **original ↔ sanitized**, not against any earlier **`base_l345`** revision.
- **Verify:** The user (or Mode A reviewer) has been given **this** **`B`**’s **original vs post-sanitize** comparison **before** Step 5 runs.

**Step 5 — Cluster change summary**
- **Run:** Write **`~/data/superagents/sanitizer/{stem}.reviews.md`** with **one** markdown table — **exactly three columns**:

| **Cluster (concept)** | **Source / original — how it read (critical detail)** | **Output — what was done** |

- **Mandatory user-visible copy:** In the **same assistant turn** that writes the file, **print the full table in chat** (markdown). Operators must read clusters **without** opening files first. If the table is too large for one message, print **consecutive parts** (`part 1/N`, …); **do not** substitute a path-only pointer for the table body.
- **Empty pass:** If Step 3 made no substantive edits, still emit the table with **one row** (e.g. *No clusters — verbatim port*) and print that row in chat.
- **Verify:** Disk **`{stem}.reviews.md`** matches the table printed in chat.

**Step 6 — Human review gate (Mode A only)**
- **Run:** On first presentation of **`{stem}.reviews.md`**, create or open **`~/data/superagents/sanitizer/{stem}.corrections.md`** with header lines: `Agent: {B}`, `Release no.: <pass_id>`, optional `Opened at: <local>`.
- **Present** the **Step 4a** original-vs-sanitized comparison, **`{stem}.reviews.md`** (cluster table), and sanitized **`base_l345/{B}`** to the **external reviewer** (chat, MR, or both).
- **Do not** advance to the next basename until the reviewer **accepts** or **requests changes**.
- **On each change request:** Append a **timestamped** block to **`{stem}.corrections.md`** (ask; gap; fix; Step 4 outcome). Edit **`base_l345/{B}`**; repeat **Steps 4 → 4a → 5** (re-check, **re-diff** Step 2 **ORIG** vs **`base_l345/{B}`**, **re-print** cluster table in chat). Loop until accept.
- **First-pass accept:** Append `No audit corrections — accepted on first review.` under the header.
- **On accept:** Write **`~/data/superagents/sanitizer/{stem}.cleaning.md`**: (i) header (`Release no.`, incrementing `Sanitizer sequence no.`, `Accepted at`, `Agent`, optional `Reviewer` — **lsai_e2e.md** §2.f style); (ii) body = **final** three-column table.
- **Verify:** **`{stem}.cleaning.md`** exists before starting the next basename.

**Step 6B — Session acceptance (Mode B; no RSI)**
- **When:** Default for **Cursor / single-operator** runs.
- **Run:** After Steps **4a** and **5**, the session owner must have seen **original vs sanitized** (Step **4a**) **and** the cluster table (Step **5**). Obtain **one** explicit **accept** or **concrete edit list** from the **session owner** (same chat thread). No separate “external reviewer” role.
- **On accept:** Append to **`{stem}.corrections.md`**: `Session acceptance (Mode B): <timestamp> — single gate, no external reviewer.` Then write **`{stem}.cleaning.md`** as in Step 6 (same header + final table).
- **On concrete edits:** Apply to **`base_l345/{B}`**, repeat **Steps 4 → 4a → 5 → 6B** until accept. **Do not** run **Step 8** or **Step 9** while still inside a **single-basename** loop—**Step 8** runs **once** after **Step 7** when **all** basenames are accepted; **Step 9** only after **Step 8** in **Mode A**.
- **Verify:** Same gate as Step 6 before advancing.

**Step 7 — End-to-end completion (includes mandatory L345 bundle cross-reference closure)**

When **every** line in **`selected_files.txt`** has **`{stem}.cleaning.md`** and **`{stem}.corrections.md`**, you must **reconcile `base_l345`** and **close cross-references across the bundle** before promoting or publishing. **Optional:** copy/promote to **`l345_base`** per **§ Release 1.6 — (f)** / MR **Details**.

**7.0 — Inventory and filename hygiene (unchanged intent)**
- **Run:** Execute **Step 7a** (overview basename, stray duplicate files).
- **Verify:** **`base_l345/`** matches the **catalog-facing** basenames in **`selected_files.txt`**; no duplicate overview under two names.

**7.1 — L345 bundle cross-reference audit (mandatory; every pass)**

**Scope:** Let **`BUNDLE`** be the set of **`*.md`** basenames actually present under **`{REPO_ROOT}/OAIRuntime/sa_install/base_l345/`** after sanitization (today: **`coding_standards.md`**, **`repo_overview.md`**, **`git_mr_guidelines.md`**, **`lsai_subagents.md`**, **`lsai_superagent.md`**, **`lsai_e2e.md`**, **`l345_router.md`** — adjust if your pass adds or drops files). **Goal:** no **mutually inconsistent** pointers **among** these files: every **in-bundle** citation of another bundle agent must name a **real basename**, and every **section / heading** cited in another bundle file must **exist** in the target file (allow **parenthetical scope hints** after a real **`##` / `###` title** when the prose says so). **Do not** imply the L345 router indexes **N** agents when the text or table lists **M ≠ N**. **`router.md`** is **not** in **`BUNDLE`** but is **allowed** when describing the **domain** router (it lives under **`.cursor/context/`**).

**Run (scripted and/or manual):**
1. **Agent existence:** Scan **`base_l345/**/*.md`** for **backtick-wrapped** **`*.md`** basenames and for **Topic Router** lines of the form **`agent.md | section:`**. Any reference to **`something.md`** that is **neither** in **`BUNDLE`** **nor** the explicit allowlist **`{ router.md }`** **nor** clearly marked **scratch** (e.g. **`.cursor/context/MR.md`** export path) **nor** **placeholder-only** rows in **Exclusion List** / **template** examples must be **fixed or removed** so readers are not told to load a **non-shipped** “peer” as if it were part of the bundle. **Template / domain-router examples** that illustrate **`router.md`** behavior must **not** use **three fixed fictional basenames** as if they were normative L345 peers—use **placeholders** (“basenames from **your** **`router.md`** summary”) or **italic** illustrative names **without** implying they ship in **`base_l345`**.
2. **Heading existence:** For **each** **`agent.md | section: <title>`** in **`l345_router.md`** (and for prominent **§** / **bold** cross-cites in other bundle files), verify **`<title>`** matches a **`##`** heading in the target agent. **Router cluster lines:** **`section:`** must equal the **full** **`##`** line text in the target file—including any trailing parenthetical (e.g. **`(see **l345_router.md**)`**); do **not** shorten to a prefix. **Prose** elsewhere may still use a short § label if it clearly points at that full heading. For **`git_mr_guidelines.md`**, if the doc uses **“§ Sections”** in prose, ensure there is a **`## Sections`** (or equivalent) heading that **anchors** the scaffold so router rows citing **`Sections`** are valid. **Same rule as Step 8 — Run (2)**—fix bundle prose and router together so you do not repeat work.
3. **Count / membership consistency:** Every place that says **`l345_router.md`** is built from or loads **“the L345 agents”** must list **exactly** the **`BUNDLE`** members that participate in L345 routing (**including** **`lsai_e2e.md`** and **`l345_router.md`** when your bundle ships them). **Do not** write **“five L345 agents”** when **seven** files are in **`base_l345`**.

**On fix:** Edit **`base_l345/{file}.md`**; record **every** change in **`~/data/superagents/sanitizer/ref_cleanup.md`** with subsections **per bundle file** (what was wrong → what was changed). **One combined log file** for the pass; do **not** scatter ref-fix notes only in per-stem **`*.corrections.md`**.

**Verify:** **`ref_cleanup.md`** exists for this pass and lists **all** bundle files touched (or states **“no edits — audit green”**). Re-run the checks until green or MR **Details** records a **waiver** (owner + reason).

**7.2 — Promote and evidence**
- **Run:** Optionally promote **`base_l345` → `l345_base`**; attach **`ref_cleanup.md`** with **`selected_files.txt`** and the **`*.cleaning.md`** set in MR / release notes.
- **Then (all modes):** Execute **Step 8** — **`l345_router.md`** topic and cluster alignment (mandatory).
- **Step 9:** After Step **8**, run **Step 9** in **Mode A**, **or** when the session owner **explicitly** requests RSI (**Execution modes** — explicit Step 9 after Mode B).
- **Verify:** MR or notes attach **`selected_files.txt`**, optional **`sanitizer.pass.md`**, **`ref_cleanup.md`** (including **Step 8** log), glob or list of **`*.reviews.md`**, **`*.cleaning.md`**, **`*.corrections.md`** for this pass, and **`sanitizer.rsi.md`** if Step 9 wrote it. Cite **(b) Layer 27** execution when applicable.

**Step 7a — Public bundle filename for monorepo overview (reconcile-only; not a substitute for Step 3)**
- **Purpose:** Some monorepos keep a **proprietary** internal overview basename (**`people_ranker_overview.md`**) in **`.cursor/context/`**, while the **Apache-facing / catalog** bundle expects **`repo_overview.md`**. Sanitized **content** is still produced in **Step 3** as usual; this step only fixes the **bundle boundary** naming so operators do not publish the proprietary filename by mistake.
- **Run (during Step 7 reconcile, after per-basename Steps 6/6B):**
  - **`selected_files.txt`** should list **`repo_overview.md`** (not **`people_ranker_overview.md`**) when this alias applies.
  - **Step 2** resolves **`ORIG`** to **`{REPO_ROOT}/.cursor/context/people_ranker_overview.md`** per the mismatch table row for **`repo_overview.md`**.
  - **Step 3** writes **`{REPO_ROOT}/OAIRuntime/sa_install/base_l345/repo_overview.md`** (i.e. **`SAN`** basename equals the **`selected_files.txt`** line **`B`**).
  - Interstitial logs should record **`ORIG=people_ranker_overview.md` → `SAN=repo_overview.md`** for MR evidence.
  - If an **older pass** left **`base_l345/people_ranker_overview.md`**, **delete** it during reconcile (after diff/review of **`repo_overview.md`**) so the tree does not ship duplicate overview files under two names.
- **Do not:** Rename or copy **`people_ranker_overview.md` → `repo_overview.md`** *instead of* running the sanitization pass—**Step 3 must still author** a fresh **`base_l345/repo_overview.md`** from **`ORIG`**. Step **7a** is **inventory / filename hygiene at bundle end**, not a short-circuit for Step 3.
- **Verify:** **`base_l345/`** contains **`repo_overview.md`** for the overview role; no stray **`people_ranker_overview.md`** remains in **`base_l345`** for catalog publish.

**Step 8 — `l345_router.md` topic list and Topic Router alignment (mandatory; before RSI)**

- **Purpose:** **`l345_router.md`** is partly **synthetic**: its **Topic List** and **`# Topic Router`** cluster bullets must **reflect the cleaned L345 agent files** in **`base_l345/`** as they exist **after** sanitization and **Step 7.1**. This step catches **drift**—topics, **`##` section** names, and **`###` sub-section** names cited in **`- agent.md | section: … | sub-section: …`** lines that no longer match the other six bundle agents.

- **When:** **After** **Step 7.0–7.2** and **Step 7a**. **Before** **Step 9** always. **Mode A** and **Mode B** both **must** run Step **8**; **Step 9** remains **Mode A / explicit-request-only**.

- **Source-of-truth agents:** **`coding_standards.md`**, **`repo_overview.md`**, **`git_mr_guidelines.md`**, **`lsai_subagents.md`**, **`lsai_superagent.md`**, **`lsai_e2e.md`** under **`base_l345/`** (not **`l345_router.md`**—the router is the **consumer** of their headings).

- **Run:**
  1. **Topic List ↔ `###` clusters:** Under **`# Topic Router`**, every **`### <topic>`** heading must appear in **`### Topic List`** as **`<topic> (weight)`** (same topic string per your indexing convention). Every **Topic List** line must have a matching **`### <topic>`** cluster (no orphan list entries; no orphan clusters). If this pass **removed or renamed** a user-facing recipe that previously had its own topic (e.g. dropped a **Recipe — …** from **`lsai_subagents.md`**), remove the matching **Topic List** line **and** its **`###`** cluster in the **same** edit. Fix **`base_l345/l345_router.md`**.
  2. **Cluster bullets → headings:** For each **`- … | section: …`** (and optional **`| sub-section: …`**), restrict **`… .md`** to the **six** source agents above. Use **one** router bullet per **`##`** and per **`###`** when practical—**do not** join multiple headings with commas or semicolons inside a single **`section:`** or **`sub-section:`** field. Each **`section:`** value must match a **`##`** title (**full** string, including any trailing parenthetical on that **`##`** line). Each **`sub-section:`** value must match a **`###`** title in that file **unless** the bundle explicitly allows **`####`** depth for that agent (document in **`ref_cleanup.md`** if so). **Parenthetical hints** after a real title are OK only when they **do not** replace the required anchor title. **`git_mr_guidelines.md`:** **`### Do NOT do these (common MR failures)`** appears **before** **`## Sections`** and is **not** a child of **Sections**—do **not** cite it as **`section: Sections | sub-section: Do NOT…`**; cite **`MR structure guardrails (hard requirements)`** and other **`###`** headings that actually sit under **`## Sections`**, or restructure **`git_mr_guidelines.md`** in a separate MR if you want **Do NOT** under **Sections**. Fix stale bullets in **`l345_router.md`**; if the **agent** file is wrong, fix it and **re-run Step 7.1** for that basename.
  3. **Opener / Cited-by lines:** Prose in the **Context Discovery** block that cites **§** or **bold** section names in other bundle agents must still match those files after edits.
  4. **Optional pipeline diff:** If you use **`build_router.py --l345`** and **`~/data/agent_topics_l345/`**, regenerate a **candidate** **`l345_router.md`** and **diff** against **`base_l345/l345_router.md`**; merge missing topics or record **hand-curation** rationale under Step **8** in the log.

- **Log:** Append a dated **`### Step 8 — l345_router topic/cluster alignment`** section to **`~/data/superagents/sanitizer/ref_cleanup.md`** listing **what** changed in **`l345_router.md`** (and any **agent** file touched). If **`ref_cleanup.md`** does not exist yet, create it with this section.

- **Verify:** Checklist **green** (scripted or manual); **no** cluster references a **missing `##`/`###`** in a **source** agent. **Recommended:** A short script (or one-liner in MR **Details**) that parses **`- agent.md | section: … | sub-section: …`** lines under **`# Topic Router`** and asserts each string exists in **`base_l345/`**, collecting headings **only outside** fenced blocks—same failure mode as **Step 4 (fenced blocks vs headings)** if headings were swallowed.

- **Do not** treat Step **8** as **Step 9:** Step **8** fixes **router ↔ bundle agent** fidelity. **Step 9** only **suggests** edits to **this recipe** from pass telemetry so the **agent** can **learn** from mistakes—**never** skip Step **8** to jump to Step **9**.

**Step 9 — RSI / post-pass recipe improvement (Mode A or explicit user request only)**
- **Definition:** **RSI** here means **editing this recipe subsection** using pass telemetry—**not** part of normal sanitization.
- **When:** Only after **Step 8**, and **either** in **Mode A** **or** when the session owner **explicitly** requests an **RSI pass** (including **Mode B**—see **Execution modes**).
- **Run:** Read all **`{stem}.corrections.md`** for basenames in this pass; **print** suggested edits to **this subsection only**; optionally mirror once to **`~/data/superagents/sanitizer/sanitizer.rsi.md`**.
- **Constraints:** ~**5%** net length growth unless waived in MR **Details**; prefer tightening over new bulk.
- **Verify:** **No** edits to **`lsai_superagent.md`** in the same automated run as sanitization; a **later** human or explicitly tasked session applies approved edits.

**Cross-reference:** **lsai_subagents.md** § **(1) How a recipe should look like**; **lsai_e2e.md** §2.f (interstitial headers).
