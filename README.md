# Portable L345 stack (SuperAgent for Cursor)

Self-contained agent stack under **`.cursor/context/`** — routers, recipes, and standards. No hosted catalog, S3, or org secrets.

Runtime artifacts (interaction logs, run folders) live under **`~/data/{project_slug}/runs/`**, not in this repo.

---

## New project from this template

**Do not use `cp -r`** — it copies the template’s **`.git`** history.

From this template checkout:

```bash
bash .cursor/scripts/copy_template.sh ../my-new-project --bootstrap
cd ../my-new-project
git init          # optional — copy has no .git
cursor .          # or open the folder in Cursor
```

What **`--bootstrap`** does:

1. Copies the stack (excludes `.git`, `.venv`, `__pycache__`)
2. Runs **`bootstrap_portable.sh`** in the new folder

---

## Bootstrap an existing checkout

Use when you already have the stack in a folder, or after **`git pull`** on another machine:

```bash
cd /path/to/your-project
bash .cursor/scripts/bootstrap_portable.sh
```

Safe to re-run (idempotent). It will not overwrite an existing interaction log.

---

## What bootstrap sets up

| Item | Location |
|------|----------|
| **Project slug** | Workspace folder basename (e.g. `my-new-project`) |
| **Run folder** | `~/data/{project_slug}/runs/{run_slug}/` |
| **Interaction log** | `…/interaction_log.md` |
| **Run metadata** | `…/meta.json` (`status: active`) |
| **Active run table** | `.cursor/context/repo_overview.md` § **Active run** |
| **Git context** | Same file § **Git and review context** (when `git` is available) |

Default run slug: **`{username}_stack-bootstrap_{yyyyMMdd-HHmmss}`**

Override before running:

```bash
RUN_STEM=my-feature bash .cursor/scripts/bootstrap_portable.sh
# or
RUN_SLUG=agoel_my-feature_20260607-120000 bash .cursor/scripts/bootstrap_portable.sh
```

Success line: **`Stack bootstrap complete: <project_slug>`**

---

## After bootstrap

Open the project in Cursor and work normally. Agents run **Context Discovery** from **`l345_router.md`** every turn and prepend turns to the interaction log under **`~/data/`**.

### AITrader — L2 Cursor keywords (after L1 data plane)

From the active run in **`repo_overview.md`** § **Active run**:

```bash
cd /path/to/aitrader
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

# One-shot: prepare batches → agent macro phrases → apply → IC discover
bash .cursor/scripts/run_cursor_keywords.sh ~/data/aitrader/runs/<run_slug>
```

Manual CoT: open `data/news/cursor_batches/batch_NNN.md` in Cursor; write `batch_NNN_out.json`; checkpoint with `keywords apply-cursor`. See **`aitrader_subagent.md`** § **Recipe — Cursor keyword extraction (primary)**.

Optional:

```bash
bash .cursor/scripts/refresh_l345_router.sh   # regenerate l345_router.md from agent sources
```

---

## Layout

```
.cursor/
  context/          # L345 agents + routers (loaded by Cursor)
  scripts/          # copy_template.sh, bootstrap_portable.sh, router pipeline
  rules/router.mdc  # reminds agents to run context discovery each turn
~/data/
  {project_slug}/
    runs/
      {run_slug}/
        interaction_log.md
        meta.json
        …             # CoT, MR slug packs, domain artifacts
```

More detail: **`lsai_superagent.md`** § **Recipe — Stack bootstrap (portable)**.
