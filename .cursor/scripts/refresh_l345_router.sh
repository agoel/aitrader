#!/usr/bin/env bash
# Regenerate l345_router.md from .cursor/context agent sources. No network.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"

export ROUTER_BUILDER_WORKSPACE="$ROOT"

"$PY" "$SCRIPT/generate_l345_topics.py" -w "$ROOT" --l345
"$PY" "$SCRIPT/topic_frequency.py" --l345
"$PY" "$SCRIPT/build_agent_topics.py" --l345
"$PY" "$SCRIPT/build_agent_topics_index.py" -w "$ROOT" --l345
"$PY" "$SCRIPT/build_reverse_index.py" --l345
"$PY" "$SCRIPT/build_router.py" -w "$ROOT" --l345

echo "Wrote $ROOT/.cursor/context/l345_router.md"
echo "Recipe index preserved from docs/operator/l345_router_recipe_index.md"
