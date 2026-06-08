# Recipe — Agentic merge (agent .md conflicts)

**Cited by:** `l345_router.md` (topic **agentic merge**), `lsai_subagents.md` (pointer), `git_mr_guidelines.md` (Related Files).

> **Warning — scope:** Use this workflow **only** for **merge conflicts in agent/context Markdown files** (typically under `.cursor/context/`, file extension `.md`). **Do not** use it for ordinary source-code merges (TypeScript, Python, etc.). For code conflicts, use normal review, tests, and team merge practices.

**Recipe purpose:** When `git merge` (or similar) reports conflicts in one or more **agent `.md` files** because two branches diverged on context docs, follow this workflow so the agent can help resolve conflicts with minimal pasted input: **per file**, **recommend** which branch should be **primary** (with reasons), wait for the user to **approve or override**, then show a **summary table** of what applying primary will pick in each region and why; **preserve** a copy of the secondary side under `~`, **overwrite** the working tree with primary to match the approved plan, summarize what secondary might still contribute, fold in **manual** edits only as agreed, then hand off. The human stages, commits, and pushes when ready; the agent does **not** run any of those Git commands.

**CRITICAL — human owns the index and merge completion (non-negotiable):** Do **not** run `git add` (or any command that **stages** resolved files), `git commit`, `git merge --continue`, or `git push` as part of this workflow. Editing **file content** in the working tree to remove conflict markers and fold text is in scope; **staging** paths is out of scope—it records conflict resolution in the **index** and moves the repo toward a merge commit the human must own. Do not “help” by running `git add` after edits, even to mark a file resolved.

**CRITICAL — preserve secondary under `~` first (non-negotiable):** Before overwriting the conflicted file or editing away conflict markers, the agent **must** write the **secondary** branch’s version of that path to **`~/<stem>_<suffix>.md`** (see §3 Step 1). **Do not skip this step** to “save time” or merge by hand from conflict markers alone. The human relies on this file for **manual review** and for **repeated comparisons** (e.g. `diff` against the working tree) **without** running `git show` / `git diff` against a ref on every pass—those commands are often **slow** and may require **repeated permission grants** in the user’s environment. If Step 1 is skipped, the recipe was not followed.

## 1. Capture the conflict context

**Content:**

- **Ask the user** to paste the **conflict output** from their terminal or editor (the `CONFLICT` lines and paths), **and** to state the **merge direction** in plain language (e.g. `master` into current branch, or `<other-branch>` into current branch). Minimal paste is enough if paths and branch names are clear.

## 2. Select files to resolve

**Content:**

- **Ask the user** which **`.md` agent/context files** they want to handle in this session (list paths relative to repo root, e.g. `.cursor/context/l345_router.md`).
- **Scope:** Only files that are **Markdown agent/context docs** for this workflow. If the user lists non-`.md` paths, **decline** those paths for this workflow and point them to normal code-merge workflows.

## 3. Per-file loop (repeat for each selected file)

Work **one file at a time**. The primary branch **may differ per file**.

### (a) Recommend primary branch for this file, then confirm

**Content:**

- **Run:** For this file, inspect how the two sides diverged—using the conflicted working copy (markers), or `git show <ref>:<path>` for **HEAD** and the **other** branch involved in the merge (from §1). Use the stated **merge direction** to name refs clearly (e.g. merging `master` into a feature branch: refs are **HEAD** and **master**).
- **Run:** **Recommend** which ref should be **primary** for **this file** (one short paragraph or bullet list). **Reasons** should be concrete, for example: newer cross-references or renamed sections aligned with the rest of `.cursor/context/`; authoritative or integration-branch updates to shared process docs; **current branch** carrying intentional doc work for the open MR; scope of edits (one side touched only trivial lines). The recommendation is **advisory** until the user confirms.
- **Ask:** Present **Recommendation:** treat **`<primary-ref>`** as primary and **`<secondary-ref>`** as secondary, with **Reasons:** …
- **Ask the user** to **approve** that recommendation or **override** it (state which side is primary). Primary = the version that should win as the **base** for the next steps because it has the **largest or most authoritative** set of changes **for this file** (either side may be primary—user judgment wins over the recommendation).
- **Then infer secondary:** The branch that is **not** primary for this file is **secondary** for Steps 1–2 below.

### (b) Summary table (after the user approves primary)

**Content:**

- **Run only after** the user approves or overrides primary for this file.
- **Run:** Emit a **summary table** (markdown table or equivalent) of what resolution will do when **primary** is applied. Cover **each conflicting region** or logical **section** (headings, subsection, or numbered conflict block)—not only the first hunk.
- **Suggested columns:**
  - **Doc area / section** — heading, subsection title, or short label for the region (e.g. “Overview — Cited by”, “Sections — Layered Implementation Sequence”).
  - **What primary gives** — one line: substance of that side in that region.
  - **Planned action** — typically **Keep primary** (secondary dropped unless folded in later). Add **Optional: review secondary after Step 2** when secondary might still contribute per §3 (c).
- **Purpose:** Same role as a human merge plan: the user sees **what will be picked and why** before the working tree is overwritten. If the whole file should match primary with no regional nuance, a **single row** (“Entire file — matches `<primary-ref>` — Keep primary”) is acceptable.
- **Do not** run Step 1 or Step 2 until this table has been shown (unless the user explicitly skips the table for a trivial single-hunk file—they should say so).

### Step 1 — Preserve secondary under `~` **before** overwriting the working tree (mandatory)

**Content:**

- **Run first:** Do **not** resolve conflicts in the editor until this step is done. Obtain the **secondary** branch’s content for the conflict path with `git show <secondary-ref>:<path>` (or equivalent) and **write** it to the user’s home directory **`~`**.
  - **Example:** `git show master:.cursor/context/l345_router.md > ~/l345_router_master.md` (use the real **secondary** ref and repo-relative **path**).
- **Filename:** `~/<stem>_<suffix>.md` where:
  - **`<stem>`** is the conflicted file’s **basename without** the `.md` extension (e.g. `l345_router` for `.cursor/context/l345_router.md`).
  - **`<suffix>`** is a **short ASCII label** for the **secondary** branch (e.g. `master`, `main`, `feature-foo` shortened if needed). No spaces if possible.
  - Examples: `.cursor/context/l345_router.md` → `~/l345_router_master.md`; `.cursor/context/git_mr_guidelines.md` → `~/git_mr_guidelines_master.md`.
- **Purpose:** Stable **diff partner** on disk for the human and for the agent’s summary step. Avoids relying on repeated `git show <secondary-ref>:path` (slow / permission prompts). **Skipping this step is a recipe violation**, not an optimization.

### Step 2 — Copy primary into the working tree

**Content:**

- **Run:** After Step 1, obtain the file content from the **primary** branch at the conflict path (e.g. `git show <primary-ref>:<path>` or `git checkout <primary-ref> -- <path>` per your workflow).
- **Run:** **Overwrite** the conflicted file in the working tree (the path Git reports) with that **primary** content—i.e. copy the primary side’s version into the repo path so conflict markers are gone and the tree matches primary for this file. This **materializes** the **Planned action** column from §3 (b) (usually **Keep primary** per row).

### (c) Summarize what secondary might still contribute (clustered tables)

**Content:**

- **Run:** Compare the repo file (after **Step 2**) vs the **Step 1** `~` copy of the secondary branch. Use `diff` or editor diff as appropriate (the `~` file is the secondary snapshot; do not substitute repeated `git show` if the user needs to re-check manually).
- **Choose output shape:**
  - For a **small** diff or when the user prefers brevity, give a **short, actionable bullet list** of what is **new or different in secondary** that could **safely** be merged in and **seems worth keeping**. Account for **moved or reshaped** text: if a paragraph relocated or was reworded but the **information still exists** in primary, say so and **do not** treat it as missing.
  - For a **large** diff, many unrelated sections, or when the user asks for structured review, use **clustered tables** (below) instead of or **in addition to** a terse list—do not dump one giant table for the whole file unless the diff is small.
- **Clustering (when using tables):** Group related diffs into **clusters**—one cluster = one coherent topic (e.g. same section, same router topic block, same recipe subsection). **Keep related changes together**; split unrelated changes into separate clusters. A single merged file may need **several clusters** (and thus **several tables**), presented **one cluster at a time** or in sequence—do not dump one giant table for the whole file unless the diff is small.
- **Optional table format — one Markdown table per cluster**, three columns:
  - **Primary** — what the **primary** branch had for this cluster (concise excerpt or bullet summary; quote short spans verbatim when helpful).
  - **Secondary** — what the **secondary** branch had for the **same** cluster (same granularity).
  - **Merged** — the **current intended outcome** in the repo path after **Step 2**; this is usually *same as Primary*; where secondary should be folded in, state the **proposed** merged wording or `*(pending user — see below)*` until the user decides in **§3 (d)**.
- **Mandatory when in table mode:** After you choose clustered tables for this pass (per **Choose output shape** above), emit **one** Markdown table per cluster using the three columns above—**do not** substitute a loose bullet list for those clusters.
- **Narrate each cluster:** Before or after each table, one short **Cluster:** line naming the topic (e.g. “Cluster: `l345_router.md` — agentic merge topic entries”).
- **Moved or reshaped text (tables path):** If a paragraph relocated or was reworded but the **information still exists** in primary, say so in the cluster narrative and in the table—**do not** treat it as missing secondary-only content.
- **Goal:** Either a short list **or** actionable, reviewable **optional** incorporations per cluster—not an automatic merge. **Table path only:** for clusters presented as tables, the tables **replace** a loose bullet list for those clusters (the list-only path is unchanged).

**Example (shape only; shorten real excerpts):**

```markdown
**Cluster:** `.cursor/context/example.md` — Topic List entries

| Primary | Secondary | Merged |
| --- | --- | --- |
| *(excerpt or summary from primary)* | *(excerpt or summary from secondary for same cluster)* | Same as Primary / *(proposed merge text)* |
```

### (d) Apply accepted edits manually (no staging, no commit)

**Content:**

- **Take instructions** from the user on which secondary changes to **accept**, **reject**, or **adapt**—**cluster by cluster** or **row-by-row within a cluster** when **§3 (c)** used tables; otherwise **one change or batch at a time** if the user prefers.
- **Run:** Apply edits **manually** into the file at the repo path (insert/reorder/edit as agreed), **one change or batch at a time** if the user prefers.
- **After edits:** When **§3 (c)** included **Primary | Secondary | Merged** tables for any cluster and the **Merged** column for that cluster **changed or no longer matches** the file after your edits, show an **updated** three-column table for **that** cluster so documented intent, the documented merge outcome, and the working tree stay aligned.
- **Do not** run `git add`, `git commit`, `git merge --continue`, or `git push`; the user owns staging and version control (see **CRITICAL — human owns the index** above).

### (e) Hand off to the user for commit

**Content:**

- Remind the user: when they are satisfied with this file, they **`git add`** (and **`git merge --continue`** / **`git commit`** / **`git push`** as needed) on their own schedule, possibly together with other files.
- **Wait** for the user to say they are ready for the **next** file (if any), then return to **section 3 (a)** for that file.

---
