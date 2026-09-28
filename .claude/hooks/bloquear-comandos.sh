#!/usr/bin/env bash
# PreToolUse (Bash): bloquea comandos destructivos o inseguros. Exit 2 = bloquear y devolver el motivo a Claude.
set -euo pipefail
entrada="$(cat)"
cmd="$(printf '%s' "$entrada" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null || true)"
[ -z "$cmd" ] && exit 0

bloquear() { echo "BLOQUEADO por .claude/hooks/bloquear-comandos.sh: $1" >&2; exit 2; }

# Borrados masivos / rutas críticas
echo "$cmd" | grep -Eq '(^|[;&|[:space:]])rm[[:space:]]+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)[[:space:]]+(/|~|\$HOME|\.\.?|\*)([[:space:]]|$)' && bloquear "rm -rf sobre raíz, home, cwd o comodín."
echo "$cmd" | grep -Eq '(^|[;&|[:space:]])rm[[:space:]]+-[a-zA-Z]*r[a-zA-Z]*[[:space:]]+.*(\.git|backend/app|frontend/src|docs)([[:space:]/]|$)' && bloquear "rm recursivo sobre directorios del proyecto."
echo "$cmd" | grep -Eq '(^|[;&|[:space:]])(mkfs|dd[[:space:]]+if=|shred|fdisk|parted)([[:space:]]|$)' && bloquear "comando de disco destructivo."
echo "$cmd" | grep -Eq 'chmod[[:space:]]+(-R[[:space:]]+)?(777|o\+w)' && bloquear "permisos 777 / escritura para todos."

# Git peligroso
echo "$cmd" | grep -Eq 'git[[:space:]]+push[[:space:]]+.*(--force([[:space:]]|$)|-f([[:space:]]|$)|\+[a-zA-Z])' && ! echo "$cmd" | grep -Eq -- '--force-with-lease' && bloquear "git push --force. Usa --force-with-lease solo en ramas propias y con motivo."
echo "$cmd" | grep -Eq 'git[[:space:]]+push[[:space:]]+[^|;&]*[[:space:]](main|master)([[:space:]]|$)' && bloquear "push directo a main/master. Trabaja en rama y abre PR."
echo "$cmd" | grep -Eq 'git[[:space:]]+(reset[[:space:]]+--hard|clean[[:space:]]+-[a-zA-Z]*f|checkout[[:space:]]+--[[:space:]]+\.|branch[[:space:]]+-D)' && bloquear "git destructivo sobre el árbol de trabajo o ramas. Guarda primero (stash/commit) y pide confirmación."
echo "$cmd" | grep -Eq 'git[[:space:]]+(commit|add)[[:space:]]+.*--no-verify' && bloquear "--no-verify omite hooks de calidad."

# Ejecución remota y secretos
echo "$cmd" | grep -Eq '(curl|wget)[^|]*\|[[:space:]]*(sudo[[:space:]]+)?(ba|z|da)?sh([[:space:]]|$)' && bloquear "descargar y ejecutar scripts remotos."
# Copiar la plantilla a .env es la forma legítima de crear el entorno local; se excluye antes de evaluar la regla.
cmd_sin_plantilla="$(printf '%s' "$cmd" | sed -E 's/cp[[:space:]]+(\.\/)?\.env\.example[[:space:]]+(\.\/)?\.env([[:space:]]|$)/ /g')"
echo "$cmd_sin_plantilla" | grep -Eq '(^|[;&|[:space:]])(cat|less|more|head|tail|bat|sed|awk|grep|cp|scp|base64|xxd)([[:space:]]+[^[:space:]|;&]+)*[[:space:]]+([^[:space:]|;&]*/)?\.env([[:space:]]|$|\.local|\.prod|\.production|\.staging)' && bloquear "lectura o copia de archivos .env con secretos. Usa .env.example."
echo "$cmd" | grep -Eq '(^|[[:space:]])(printenv|env)([[:space:]]|$)|echo[[:space:]]+"?\$(ANTHROPIC_API_KEY|TYPESAFE_API_KEY|OPENAI_API_KEY|GOOGLE_API_KEY|APP_MASTER_KEY|JWT_SECRET|DATABASE_URL)' && bloquear "volcado de variables de entorno con secretos."

# Base de datos y contenedores
echo "$cmd" | grep -Eiq 'drop[[:space:]]+(database|schema)|truncate[[:space:]]+(table[[:space:]]+)?(auditoria|usuarios|mensajes|cuentas_correo)' && bloquear "DDL destructivo sobre la base de datos."
echo "$cmd" | grep -Eq 'docker[[:space:]]+(system|volume)[[:space:]]+prune|docker[[:space:]]+compose[[:space:]]+down[[:space:]]+.*-v' && bloquear "borrado de volúmenes Docker (perderías la base de datos local)."
echo "$cmd" | grep -Eq 'alembic[[:space:]]+downgrade[[:space:]]+base' && bloquear "alembic downgrade base fuera de pruebas. Usa el contenedor de pruebas (make db-test)."

# Desactivar seguridad
echo "$cmd" | grep -Eq -- '--no-verify-ssl|--insecure|-k[[:space:]]+https|PYTHONHTTPSVERIFY=0|NODE_TLS_REJECT_UNAUTHORIZED=0' && bloquear "desactivar verificación TLS."
echo "$cmd" | grep -Eq 'pip[[:space:]]+install|pip3[[:space:]]+install' && ! echo "$cmd" | grep -Eq 'uv[[:space:]]+pip' && bloquear "usa 'uv add' / 'uv sync' en vez de pip para mantener el lockfile."

exit 0
