#!/usr/bin/env bash
# Stop: si hay cambios de código sin verificar (make check no ejecutado después del último cambio), pide ejecutarlo. Evita bucles con stop_hook_active.
set -uo pipefail
entrada="$(cat)"
activo="$(printf '%s' "$entrada" | python3 -c 'import sys,json; print(str(json.load(sys.stdin).get("stop_hook_active", False)).lower())' 2>/dev/null || echo false)"
[ "$activo" = "true" ] && exit 0
raiz="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$raiz" || exit 0
cambios="$(git status --porcelain -- backend frontend 2>/dev/null | grep -E '\.(py|ts|html|scss|toml|json)$' || true)"
[ -z "$cambios" ] && exit 0
marca="$raiz/.claude/.ultima-verificacion"
mas_reciente="$(git status --porcelain -- backend frontend | awk '{print $2}' | xargs -I{} stat -c %Y "{}" 2>/dev/null | sort -n | tail -1)"
ultima="$( [ -f "$marca" ] && stat -c %Y "$marca" || echo 0 )"
if [ "${mas_reciente:-0}" -gt "$ultima" ]; then
  echo "Hay cambios en backend/ o frontend/ posteriores a la última verificación. Ejecuta 'make check' (o los comandos de CLAUDE.md) y corrige lo que falle antes de terminar. Si ya lo hiciste manualmente, ejecuta 'make marcar-verificado'." >&2
  exit 2
fi
exit 0
