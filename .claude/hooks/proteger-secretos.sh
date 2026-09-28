#!/usr/bin/env bash
# PreToolUse (Write|Edit|MultiEdit): impide escribir en archivos protegidos y detecta secretos en el contenido.
set -euo pipefail
entrada="$(cat)"
leer() { printf '%s' "$entrada" | python3 -c "import sys,json; d=json.load(sys.stdin); ti=d.get('tool_input',{}); print(ti.get('$1','') or '')" 2>/dev/null || true; }
ruta="$(leer file_path)"
contenido="$(leer content)$(leer new_string)"
if [ -z "$contenido" ]; then
  contenido="$(printf '%s' "$entrada" | python3 -c 'import sys,json; d=json.load(sys.stdin); print("\n".join(e.get("new_string","") for e in d.get("tool_input",{}).get("edits",[])))' 2>/dev/null || true)"
fi
bloquear() { echo "BLOQUEADO por .claude/hooks/proteger-secretos.sh: $1" >&2; exit 2; }

base="$(basename -- "$ruta")"
case "$ruta" in
  *.env|*/.env|*.env.local|*.env.production|*.env.prod|*.env.staging) bloquear "no se editan archivos .env reales; edita .env.example y documenta la variable." ;;
  *.pem|*.key|*.p12|*.pfx|*.jks|*id_rsa*|*id_ed25519*) bloquear "archivos de claves privadas." ;;
  */secrets/*|*/.secrets/*|*/credentials*|*/.aws/*|*/.ssh/*) bloquear "directorio de credenciales." ;;
  */uv.lock|*/package-lock.json) bloquear "los lockfiles se regeneran con la herramienta (uv lock / npm install), no a mano." ;;
  */alembic/versions/*)
    if [ -f "$ruta" ] && git -C "$(dirname "$ruta")" ls-files --error-unmatch "$ruta" >/dev/null 2>&1 && git -C "$(dirname "$ruta")" log --oneline -1 -- "$ruta" | grep -q .; then
      bloquear "migración ya versionada en git; crea una migración nueva en vez de editar una publicada."
    fi ;;
esac
case "$base" in .env.example|.env.sample|.env.template) exit 0 ;; esac

[ -z "$contenido" ] && exit 0

# Patrones de secretos (excluye placeholders obvios)
if printf '%s' "$contenido" | grep -Eq 'sk-ant-[A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----|eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}'; then
  bloquear "el contenido parece incluir una credencial real (API key, token, clave privada). Usa variables de entorno y SecretsPort."
fi
if printf '%s' "$contenido" | grep -Eiq '(password|passwd|contrasena|contraseña|api[_-]?key|secret|token)[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"'$<{%]{12,}["'"'"']' \
   && ! printf '%s' "$contenido" | grep -Eiq '(ejemplo|example|placeholder|changeme|cambiame|dummy|fake|test|prueba|xxx|\*\*\*|<[^>]+>|\$\{)'; then
  bloquear "asignación literal de una contraseña/clave de más de 12 caracteres. Léela de configuración o usa un valor de ejemplo evidente."
fi
if printf '%s' "$contenido" | grep -Eq 'postgres(ql)?://[^:/@[:space:]]+:[^@[:space:]]{8,}@' && ! printf '%s' "$contenido" | grep -Eq 'postgres(ql)?://[^:@]+:(postgres|password|changeme|\$\{|\{\{|<)'; then
  bloquear "DATABASE_URL con contraseña embebida."
fi

# Patrones inseguros de código
if printf '%s' "$ruta" | grep -Eq '\.py$'; then
  printf '%s' "$contenido" | grep -Eq 'verify[[:space:]]*=[[:space:]]*False|ssl\._create_unverified_context|check_hostname[[:space:]]*=[[:space:]]*False' && bloquear "desactivación de verificación TLS en Python."
  printf '%s' "$contenido" | grep -Eq '(^|[^a-zA-Z_])(eval|exec)\(|subprocess\.[a-z_]+\([^)]*shell[[:space:]]*=[[:space:]]*True|pickle\.loads?\(|yaml\.load\([^)]*\)$' && bloquear "eval/exec, shell=True, pickle o yaml.load inseguro. Usa alternativas seguras (yaml.safe_load, listas de argumentos)."
  printf '%s' "$contenido" | grep -Eq '(execute|text)\([[:space:]]*f["'"'"']|["'"'"'][[:space:]]*%[[:space:]]*\(.*\)[[:space:]]*\)[[:space:]]*$' && bloquear "posible SQL construido por interpolación. Usa parámetros."
  printf '%s' "$ruta" | grep -Evq '/providers/|/tests/' && printf '%s' "$contenido" | grep -Eq '^(from|import)[[:space:]]+(anthropic|openai|google\.generativeai|google\.genai|typesafe_sdk|langchain_anthropic|langchain_openai|langchain_google_genai)' && bloquear "SDKs de proveedores solo se importan dentro de backend/app/providers/ (ADR-0002)."
  printf '%s' "$contenido" | grep -Eq 'budget_tokens|tool_choice[[:space:]]*=[[:space:]]*\{[^}]*"type"[[:space:]]*:[[:space:]]*"(any|tool)"' && bloquear "budget_tokens y tool_choice forzado no existen en modelos Claude 4.6+; usa thinking adaptive y output_config.effort."
fi
if printf '%s' "$ruta" | grep -Eq '\.(ts|html)$'; then
  printf '%s' "$contenido" | grep -Eq 'bypassSecurityTrust(Html|Script|Style|Url|ResourceUrl)|innerHTML[[:space:]]*=' && bloquear "bypassSecurityTrust*/innerHTML en Angular. Usa iframe sandbox con srcdoc saneado por el backend."
  printf '%s' "$contenido" | grep -Eq 'localStorage\.setItem\([^)]*(token|jwt|access)' && bloquear "tokens en localStorage. Guárdalos en un signal en memoria (SesionStore)."
fi
exit 0
