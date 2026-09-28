#!/usr/bin/env bash
# SessionStart: contexto breve del proyecto para el agente.
set -uo pipefail
raiz="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$raiz" || exit 0
echo "Agente Correo · rama: $(git branch --show-current 2>/dev/null) · último commit: $(git log -1 --format='%h %s' 2>/dev/null)"
echo "Docs clave: docs/00-vision-y-alcance.md, docs/01-arquitectura.md, docs/10-roadmap.md. Agentes: arquitecto, backend, frontend, qa, seguridad. Orquestación: /orquestar <épica>."
[ -d backend/app ] && echo "Backend presente ($(find backend/app -name '*.py' | wc -l) archivos .py)." || echo "Backend aún no inicializado (ver docs/10-roadmap.md E0.1)."
[ -d frontend/src ] && echo "Frontend presente." || echo "Frontend aún no inicializado (E0.4)."
ls docs/planes/*.md >/dev/null 2>&1 && echo "Planes: $(ls docs/planes/*.md | xargs -n1 basename | tr '\n' ' ')"
command -v uv >/dev/null || echo "Aviso: 'uv' no instalado (curl -LsSf https://astral.sh/uv/install.sh | sh, revisar antes de ejecutar)."
exit 0
