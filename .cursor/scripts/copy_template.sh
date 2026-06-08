#!/usr/bin/env bash
# Copy this portable L345 stack to a new project folder WITHOUT .git (or template history).
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: copy_template.sh <destination-path> [--bootstrap]

  <destination-path>  New project folder (must not exist yet).
  --bootstrap         Run bootstrap_portable.sh in the copy when done.

Examples:
  bash .cursor/scripts/copy_template.sh ../my-new-project --bootstrap
  cd ../my-new-project && cursor .

Do NOT use plain "cp -r" — it copies .git from the template checkout.
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

SRC="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="$1"
DO_BOOTSTRAP=0
shift

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bootstrap) DO_BOOTSTRAP=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
  shift
done

if [[ -e "$DEST" ]]; then
  echo "ERROR: Destination already exists: $DEST"
  exit 1
fi

mkdir -p "$(dirname "$DEST")"
DEST="$(cd "$(dirname "$DEST")" && pwd)/$(basename "$DEST")"

if command -v rsync >/dev/null 2>&1; then
  rsync -a \
    --exclude '.git' \
    --exclude '.DS_Store' \
    --exclude '__pycache__' \
    --exclude '.venv' \
    "$SRC/" "$DEST/"
else
  mkdir -p "$DEST"
  tar -C "$SRC" \
    --exclude '.git' \
    --exclude '.DS_Store' \
    --exclude '__pycache__' \
    --exclude '.venv' \
    -cf - . | tar -C "$DEST" -xf -
fi

echo "Copied portable stack → $DEST"
echo "  (excluded .git — use 'git init' in the new folder when ready)"

if [[ $DO_BOOTSTRAP -eq 1 ]]; then
  echo ""
  (cd "$DEST" && bash .cursor/scripts/bootstrap_portable.sh)
else
  echo ""
  echo "Next: cd $DEST && bash .cursor/scripts/bootstrap_portable.sh"
fi
