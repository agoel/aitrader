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
| Router Builder | meta | `lsai_superagent.md` | `Router Architecture and Builder` → **Router Builder Recipe** | L4 topic index generation |

**Run:** Match user goal → row above → load owner section only. **Verify:** No new inline procedure duplicates an indexed **Run** block without a child-recipe cite.

---
