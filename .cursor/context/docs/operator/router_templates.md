# Router templates (build_router.py source)

**Purpose:** Stamped by `build_router.py` into `router.md` / `l345_router.md`. Not loaded every turn — operators only.

<!-- ROUTER_TEMPLATE_START -->
## IMPORTANT: Context Discovery and Loading (Run First Every Turn)

When the user prompts something, use **user context in Cursor memory** + **the prompt** to understand what topics the request belongs to. Based on those topics, discover the relevant agents and their sections/sub-sections. Produce a **loadable context summary** for the Cursor agent and **load it before running further**.

**Project interaction log (mandatory every turn):** Resolve **`{run_slug}`**; log at **`~/data/{project_slug}/runs/{run_slug}/interaction_log.md`**. Prepend per **lsai_superagent.md** § **Recipe — Project interaction log** → **Prepend algorithm** (read entire file first). **Question:** verbatim; **Response:** summary.

### Steps to Discover and Load Context

1. **Extract the goal from user input**
   - Combine the user's prompt with any relevant user context (open files, recent edits, workspace rules, memories).
   - Identify the main goal or intent (e.g., "add a metrics pipeline for a third-party device integration").

2. **Match the goal to 2–3 topics**
   - Use the **Topic List** below (generated from `~/data/agent_topics/agent_topics.txt` and stamped here).
   - Each topic includes a **weighting** (frequency in parentheses); higher weighting indicates a more high-level or common topic across agents.
   - Select 2–3 topics whose keywords or meaning best match the goal. Prefer topics that appear in the goal or closely relate to it (e.g., "device integration overview", "canned metrics", "KPI recipe framework").
   - Use semantic matching: if the exact topic text is not in the goal, choose topics that cover the same concepts.

### Topic List

{{TOPIC_LIST}}

3. **Look up agents and sections for those topics**
   - In this file (router.md), for each selected topic, find its `### <topic>` heading in the clustered sections below and the agent references listed under it. (If the topic list shows `topic (freq)`, use the topic name only when matching headings.)
   - Each reference has the form: `agent.md | section: <section> | sub-section: <sub-section>` (or `agent.md | sub-section: <sub-section>` when there is no section).

4. **Build the loadable context summary**
   - Group all references by agent.
   - For each agent, list the unique sections and sub-sections.
   - Produce a copy-paste block in this format:
     ```
     agent1.md: Section1 (Sub-section A, Sub-section B); Section2 (Sub-section C)
     agent2.md: Overview; Section (Sub-section)
     agent3.md: Section
     ```

5. **Ensure missing agent files exist locally**
   - From the summary (step 4), collect **distinct basenames** the **domain** router listed (product-specific **`.md`** files under **`.cursor/context/`**—**not** the L345 bundle files already in this portable stack). Treat a file as missing or empty if it does not exist, has zero bytes, or is whitespace-only. If all are non-empty, go to step 6.
   - **Portable stack:** **Do not download** missing agents from a remote catalog. **Stop** and list missing basenames; tell the user to add those **`.md`** files under **`.cursor/context/`** in the repo (or remove stale router references).

6. **Load the context before proceeding**
   - Load the agent `.md` files from `.cursor/context/` (same paths as step 5).
   - Focus on the sections and sub-sections identified in the summary.
   - Use this context for all subsequent planning, coding, and tool execution.

7. **Interaction log:** At response end, prepend the turn block per **Project interaction log** above.

### Example

**User prompt:** "Add a metrics pipeline that ingests vendor device feeds for our product."

**Step 1 (goal):** Add a metrics pipeline for third-party device data.

**Step 2 (topics):** device integration overview, canned metrics, KPI recipe framework.

**Step 3–4 (loadable context):** *(Illustration only—the lines below are **fictional domain** agents returned by **`router.md`** for this story; they do **not** appear in **`OAIRuntime/sa_install/base_l345/`**.)*
```
<domain_agent_from_router_summary_A>.md: Overview; … (sections from your router output)
<domain_agent_from_router_summary_B>.md: …
```

**Step 5:** For **each** basename from step 4 that is still missing or empty under **`.cursor/context/`**, **stop** and ask the user to add the file locally (no remote fetch).

**Step 6:** Load **those** domain agent files with the listed sections before continuing.

---
<!-- ROUTER_TEMPLATE_END -->

### L345_router.md Template (stamped by `build_router.py --l345`)

Extracted by **`build_router.py --l345`** from this file. Replaces `{{TOPIC_LIST}}` from `~/data/agent_topics_l345/agent_topics.txt`, merges **`l345_router_recipe_index.md`**, appends flat **`### topic`** clusters, and writes **`.cursor/context/l345_router.md`**. Run **`bash .cursor/scripts/refresh_l345_router.sh`** (or the Python steps in **`lsai_superagent.md`** Router Builder Recipe).

<!-- L345_ROUTER_TEMPLATE_START -->
## IMPORTANT: Context Discovery and Loading (Run First Every Turn)

When the user prompts something, use **user context in Cursor memory** + **the prompt** to understand what topics the request belongs to. Based on those topics, discover the relevant agents and their sections/sub-sections. Produce a **loadable context summary** for the Cursor agent and **load it before running further**.

**Portable L345 bundle:** Hot-path files under **`.cursor/context/`** (indexed below). **On-demand:** **`agentic_merge.md`**, **`docs/operator/*`** — load via **Recipe index**, not every turn. **No download** — stack is repo-local. Domain **`router.md`** optional. Missing cited files → **stop** and add locally.

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

{{TOPIC_LIST}}

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
<!-- L345_ROUTER_TEMPLATE_END -->
