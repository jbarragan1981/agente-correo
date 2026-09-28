# Agente Correo · guía para Claude Code

Sistema multiagente de correo electrónico y webchat para Viamatica: conecta cuentas de correo, clasifica con **TypeSafe Jev** (respaldo en un LLM económico), enruta a agentes especializados, redacta borradores con aprobación humana y expone un panel Angular de observabilidad y configuración. Backend **FastAPI + LangGraph + PostgreSQL**, frontend **Angular 22**. Proveedor de IA agnóstico (Anthropic primero; OpenAI, Gemini y Jev intercambiables).

## Fuente de verdad
Lee antes de diseñar o implementar: `docs/00-vision-y-alcance.md` (qué y por qué), `docs/01-arquitectura.md` (cómo), `docs/02-stack-tecnologico.md` (con qué y versiones), `docs/03-modelo-de-datos.md`, `docs/04-api.md`, `docs/05-agentes-y-proveedores.md`, `docs/06-frontend-angular.md`, `docs/07-seguridad.md`, `docs/08-observabilidad.md`, `docs/09-testing-y-calidad.md`, `docs/10-roadmap.md`, `docs/adr/`. Los planes por épica viven en `docs/planes/`.

## Enjambre de agentes de Claude Code
| Agente | Rol | Cuándo |
|---|---|---|
| `arquitecto` | Desglosa épicas, diseña, escribe planes y ADRs. No implementa. | Siempre primero ante una épica/historia. |
| `backend` | FastAPI, LangGraph, SQLAlchemy, proveedores, IMAP/SMTP, migraciones, pruebas unitarias. | Tareas de backend del plan. |
| `frontend` | Angular 22 zoneless, Material + Tailwind con tokens Viamatica, stores, widget. | Tareas de frontend del plan. En paralelo con backend. |
| `qa` | Pruebas de todos los niveles, evals, defectos con reproducción. | Tras backend/frontend. |
| `seguridad` | SAST, auditorías, revisión ASVS + OWASP LLM, veredicto. | Antes de cada PR. |

Orquestación: `/orquestar <épica>` ejecuta arquitecto → (backend ‖ frontend) → qa → seguridad → cierre. Skills de dominio que los agentes cargan según la tarea: `fastapi-backend`, `langgraph-agentes`, `jev-clasificador`, `proveedor-llm`, `angular-viamatica`, `postgres-migraciones`, `correo-imap`, `seguridad-default`, `pruebas-qa`.

## Estructura
```
backend/   app/{domain,application,agents,providers,infrastructure,api,core} · tests/ · alembic/
frontend/  src/app/{core,shared,features} · projects/widget · e2e/
infra/     docker-compose.yml · Dockerfile.backend · Dockerfile.web · nginx.conf · sql/
docs/      especificaciones, ADRs, planes
evals/     dataset etiquetado y evaluaciones del clasificador
.claude/   agents/ skills/ hooks/ settings.json
```

## Comandos
```
make dev            # PostgreSQL en Docker + API con recarga + worker + ng serve
make check          # ruff, pyrefly, pytest rápido, eslint, tsc, vitest, build (lo que corre CI)
make test-int       # pruebas de integración con contenedores (PostgreSQL 17, GreenMail)
make security       # bandit, semgrep, pip-audit, npm audit, gitleaks
make e2e            # Compose con FAKE_PROVIDERS=true + Playwright
make keys           # genera APP_MASTER_KEY y JWT_SECRET para .env local
make marcar-verificado  # actualiza la marca que usa el hook de Stop
```
Backend: `cd backend && uv run <cmd>`. Frontend: `cd frontend && npm run <script>`. Nunca `pip install`; siempre `uv add`.

## Reglas del proyecto (resumen; detalle en docs/07-seguridad.md y skills)
1. **Correo y chat son datos no confiables.** Van delimitados en el prompt; nunca disparan herramientas ni envíos. El Guardián corre antes de cualquier LLM con herramientas.
2. **Proveedor agnóstico.** `import anthropic|openai|google.genai|typesafe_sdk` solo dentro de `backend/app/providers/`. El resto usa `ChatModelPort`/`ClassifierPort`.
3. **Human-in-the-loop por defecto.** Enviar, mover, borrar, escalar son casos de uso con aprobación o política explícita; jamás herramientas del modelo.
4. **Secretos** cifrados (envelope AES-256-GCM) vía `SecretsPort`; nunca en respuestas, logs, fixtures, docs ni commits. `.env` no se lee ni se versiona.
5. **Hexagonal + SOLID.** `api → application → domain`; adaptadores implementan puertos; funciones pequeñas con una responsabilidad; sin flags booleanos que cambien comportamiento.
6. **Todo cambio de estado deja auditoría y métrica**; toda tabla nueva lleva migración Alembic reversible; todo endpoint nuevo tiene rol, límites y pruebas 401/403.
7. **Modelos Anthropic 4.6+**: `thinking={"type":"adaptive"}`, `output_config.effort`; sin `budget_tokens`, prefill ni `tool_choice` forzado; manejar `refusal`. IDs exactos: `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-4-5`. Jev: `jev-latest`.
8. **Pruebas con proveedores falsos** (`FAKE_PROVIDERS=true`) y GreenMail; nunca credenciales ni correos reales.
9. **Calidad antes de terminar**: `make check` verde; el hook de Stop lo recuerda. Nunca debilitar, saltar o borrar pruebas.
10. **Git**: ramas `feature/<epica>`, commits convencionales en español (`feat(backend): …`), sin `--force`, sin push a `main`, PR solo si el usuario lo pide.
11. **Idioma**: código de dominio, docs, pruebas y UI en español; nombres de librerías/estándares en inglés. Escribe sin comparativos del tipo "no es X, es Y".

## Hooks activos (`.claude/settings.json`)
`bloquear-comandos.sh` (PreToolUse Bash: destructivos, force push, TLS off, pip, .env), `proteger-secretos.sh` (PreToolUse Write/Edit: archivos protegidos, credenciales, patrones inseguros, SDKs fuera de providers), `post-edit-lint.sh` (PostToolUse: ruff/prettier/eslint/validación JSON-YAML), `stop-verificar.sh` (Stop: exige `make check` tras cambios), `sesion-inicio.sh` (SessionStart: contexto). Si un hook bloquea algo legítimo, explica el caso al usuario en vez de rodearlo.
