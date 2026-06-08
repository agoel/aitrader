#!/usr/bin/env bash
# Cursor keyword extraction pipeline (primary L2 path). No OpenAI key.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RUN_DIR="${1:-}"
PY="${PYTHON:-$ROOT/.venv/bin/python}"

if [[ -z "$RUN_DIR" ]]; then
  CONTEXT="$ROOT/.cursor/context/repo_overview.md"
  if [[ -f "$CONTEXT" ]]; then
    RUN_DIR="$(grep -m1 'Run directory' "$CONTEXT" | sed -E 's/.*`(~[^`]+)`.*/\1/' | sed "s|~|$HOME|")"
  fi
fi

if [[ -z "$RUN_DIR" || ! -d "$RUN_DIR" ]]; then
  echo "Usage: bash .cursor/scripts/run_cursor_keywords.sh <run-dir>"
  echo "  or set Active run in repo_overview.md"
  exit 1
fi

cd "$ROOT"
"$PY" -m aitrader keywords run-cursor --run-dir "$RUN_DIR" --force
echo "Cursor keyword pipeline complete for $RUN_DIR"
