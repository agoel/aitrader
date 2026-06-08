#!/usr/bin/env bash
# One-shot portable stack bootstrap. No network, no S3, no Cursor agent step required.
# {project_slug} = workspace folder basename (whatever the user named their copy).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTEXT="$ROOT/.cursor/context"
PY="${PYTHON:-python3}"

REQUIRED=(
  l345_router.md
  lsai_subagents.md
  lsai_superagent.md
  git_mr_guidelines.md
  coding_standards.md
  repo_overview.md
  lsai_e2e.md
)

missing=0
for f in "${REQUIRED[@]}"; do
  if [[ ! -s "$CONTEXT/$f" ]]; then
    echo "MISSING or empty: $CONTEXT/$f"
    missing=1
  fi
done

if [[ ! -f "$SCRIPT_DIR/build_router.py" ]]; then
  echo "MISSING: .cursor/scripts/ router pipeline"
  missing=1
fi

if [[ $missing -ne 0 ]]; then
  echo "Stack incomplete. Fix missing files and re-run."
  exit 1
fi

PROJECT_SLUG="$(basename "$ROOT" | tr '[:upper:]' '[:lower:]')"
USERNAME="$(whoami)"
RUN_STEM="${RUN_STEM:-stack-bootstrap}"
RUN_STARTED="$(date +%Y%m%d-%H%M%S)"
RUN_SLUG="${RUN_SLUG:-${USERNAME}_${RUN_STEM}_${RUN_STARTED}}"
DATA_ROOT="${ROUTER_BUILDER_DATA:-$HOME/data}"
RUN_DIR="$DATA_ROOT/$PROJECT_SLUG/runs/$RUN_SLUG"
LOG_FILE="$RUN_DIR/interaction_log.md"
META_FILE="$RUN_DIR/meta.json"
NOW="$(date +%Y-%m-%d:%H:%M:%S)"

mkdir -p "$RUN_DIR"

if [[ ! -f "$LOG_FILE" ]]; then
  cat >"$LOG_FILE" <<EOF
# Interaction log — ${PROJECT_SLUG} / ${RUN_SLUG}

| Field | Value |
|-------|-------|
| **Project slug** | \`${PROJECT_SLUG}\` |
| **Run slug** | \`${RUN_SLUG}\` |
| **Username** | \`${USERNAME}\` |
| **Run directory** | \`~/data/${PROJECT_SLUG}/runs/${RUN_SLUG}/\` |
| **Log file** | \`~/data/${PROJECT_SLUG}/runs/${RUN_SLUG}/interaction_log.md\` |
| **Run started** | \`${RUN_STARTED}\` |
| **Last updated** | \`${NOW}\` |
| **Order** | Newest \`## Turn\` block first (below this header) |

---
EOF
fi

if [[ ! -f "$META_FILE" ]]; then
  cat >"$META_FILE" <<EOF
{
  "project_slug": "${PROJECT_SLUG}",
  "run_slug": "${RUN_SLUG}",
  "username": "${USERNAME}",
  "run_started": "${RUN_STARTED}",
  "status": "active"
}
EOF
fi

"$PY" "$SCRIPT_DIR/fill_bootstrap_tables.py" \
  -w "$ROOT" \
  --project-slug "$PROJECT_SLUG" \
  --username "$USERNAME" \
  --run-slug "$RUN_SLUG" \
  --run-started "$RUN_STARTED"

echo ""
echo "Stack bootstrap complete: ${PROJECT_SLUG}"
echo "  Repo:     $ROOT"
echo "  Run dir:  $RUN_DIR"
echo "  Log:      $LOG_FILE"
echo "  Overview: $CONTEXT/repo_overview.md (§ Active run filled)"
echo ""
echo "Open in Cursor and start working — agents read § Active run for paths."
echo "Optional: bash $SCRIPT_DIR/refresh_l345_router.sh"
