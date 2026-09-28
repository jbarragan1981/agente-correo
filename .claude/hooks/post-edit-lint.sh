#!/usr/bin/env bash
# PostToolUse (Write|Edit|MultiEdit): formatea y lintea el archivo tocado. Nunca bloquea (exit 0); informa por stdout.
set -uo pipefail
entrada="$(cat)"
ruta="$(printf '%s' "$entrada" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null || true)"
[ -z "$ruta" ] || [ ! -f "$ruta" ] && exit 0
raiz="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

case "$ruta" in
  "$raiz"/backend/*.py)
    if command -v uv >/dev/null 2>&1 && [ -f "$raiz/backend/pyproject.toml" ]; then
      ( cd "$raiz/backend" && uv run --quiet ruff format "$ruta" >/dev/null 2>&1; uv run --quiet ruff check --fix --quiet "$ruta" 2>&1 | tail -n 20 ) || true
    fi ;;
  "$raiz"/frontend/*.ts|"$raiz"/frontend/*.html|"$raiz"/frontend/*.scss)
    if [ -d "$raiz/frontend/node_modules" ]; then
      ( cd "$raiz/frontend" && npx --no-install prettier --write "$ruta" >/dev/null 2>&1; case "$ruta" in *.ts|*.html) npx --no-install eslint --fix "$ruta" 2>&1 | tail -n 20 ;; esac ) || true
    fi ;;
  *.json)
    python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$ruta" 2>&1 | sed 's/^/JSON inválido: /' ;;
  *.yml|*.yaml)
    python3 -c "import sys; import yaml; yaml.safe_load(open(sys.argv[1]))" "$ruta" 2>&1 | grep -v ModuleNotFoundError | sed 's/^/YAML inválido: /' ;;
  *.sh)
    bash -n "$ruta" 2>&1 | sed 's/^/Sintaxis bash: /' ;;
esac
exit 0
