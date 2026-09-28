# 02 · Stack tecnológico

Versiones verificadas en PyPI / npm el 2026-09-28. Se fijan en `pyproject.toml` y `package.json`; se actualizan con Renovate/Dependabot y pruebas.

## 1. Resumen ejecutivo

| Capa | Elección | Por qué |
|---|---|---|
| Lenguaje backend | **Python 3.12** | Ecosistema de IA más maduro; tipado moderno; soporte de `uv`. |
| Gestor de paquetes | **uv** | Instalación reproducible y rápida; lockfile; reemplaza pip/venv/poetry. |
| API | **FastAPI 0.141** + Uvicorn | Async nativo, OpenAPI automático, Pydantic v2, WebSockets. |
| Orquestación de agentes | **LangGraph 1.2** | Grafo de estado explícito, checkpointing, `interrupt()` para aprobación humana, streaming de eventos. |
| Abstracción de modelos | **LangChain 1.4** (`init_chat_model`) + `langchain-anthropic`, `langchain-openai`, `langchain-google-genai` | Un solo contrato de chat model para todos los proveedores; herramientas y salida estructurada uniformes. |
| Clasificador | **TypeSafe Jev** vía `typesafe-sdk 0.7` (y `langchain-typesafe` para composición) | Decisión tipada y calibrada, ~0,1 s y ~USD 0,00008 por correo. |
| Base de datos | **PostgreSQL 17** | Transacciones, `SKIP LOCKED` como cola, JSONB, `pgcrypto`, checkpoints de LangGraph. |
| ORM / migraciones | **SQLAlchemy 2.1 (async) + asyncpg + Alembic 1.20** | Estándar de facto; migraciones programáticas al arrancar. |
| Cola de trabajos | **PostgreSQL nativo** (`procrastinate 3.10`) | Cero infraestructura extra; reintentos, programación, bloqueos. Redis/arq queda como camino de escala. |
| Correo | **aioimaplib 2.0** (IMAP IDLE) + **aiosmtplib 5.1** + `email` stdlib + **nh3** para sanear HTML | Async, sin dependencias nativas, sanitizado seguro (Rust). |
| Seguridad | **PyJWT 2.15**, **argon2-cffi**, **cryptography 50** (AES-GCM), **slowapi** (rate limit), **Authlib** (OIDC Fase 2) | Estándares, sin criptografía casera. |
| Observabilidad | **OpenTelemetry SDK 1.45** + instrumentación FastAPI/SQLAlchemy/httpx, **structlog 26** (JSON), **Langfuse 4** opcional | Trazas distribuidas y de LLM; métricas Prometheus; logs correlacionados. |
| Calidad Python | **ruff 0.16** (lint + format), **pyrefly 1.3** o **mypy 2.3** (tipos), **pytest 9** + `pytest-asyncio` + `httpx` + `testcontainers` | Rápido, estricto, CI-friendly. |
| Seguridad de código | **bandit**, **pip-audit**, **semgrep**, **gitleaks** | SAST, CVEs, secretos. |
| Frontend | **Angular 22.2** (standalone, zoneless, signals, Signal Forms) | Última versión estable; rendimiento y DX modernas. |
| UI kit | **Angular Material 22 + CDK** + **Tailwind CSS 4.3** | Componentes accesibles + utilidades con tokens de marca. |
| Estado | **@ngrx/signals 22** | Stores basados en signals, simple y tipado. |
| Gráficas | **ECharts 6 + ngx-echarts 22** | Dashboards ricos, temas, buen rendimiento con series grandes. |
| Pruebas front | **Vitest 5** (unitarias, por defecto en Angular 21+), **Playwright 1.63** (e2e) | Rápido, estándar. |
| Contenedores | **Docker Compose**, imágenes distroless/`python:3.12-slim`, usuario sin privilegios | Portabilidad on-premise y nube. |
| CI/CD | **GitHub Actions** | Lint, tipos, pruebas, SAST, build de imágenes, escaneo de contenedor (Trivy). |

## 2. Justificación de las decisiones clave

### 2.1 LangGraph sí, "LangChain Agents" clásicos no

LangGraph da control explícito del flujo (grafo, estado tipado, reintentos por nodo, checkpoints, `interrupt()`), que es justo lo que exige un sistema con aprobación humana y auditoría. LangChain se usa únicamente por su capa de modelos (`init_chat_model("anthropic:claude-opus-5-5")`) y por `langchain-typesafe`, que expone a Jev como `Runnable`. Se evitan las abstracciones de alto nivel de "agente genérico" porque esconden el flujo.

Las librerías `langgraph-supervisor` y `langgraph-swarm` se consideraron. Se adopta un grafo propio con el patrón que ambas implementan (coordinador + traspasos con `Command`) porque el enjambre tiene nodos sin LLM y necesita puntos de interrupción específicos; así se evita depender de paquetes en versión 0.x para el núcleo (ver ADR-0001).

### 2.2 Jev como clasificador primario

Jev (`jev-latest`, endpoint `POST https://api.typesafe.ai/v1/systemone`) recibe un `state` (texto o JSON) y un mapa de `questions` tipadas, y devuelve probabilidades calibradas:

| Tipo | Pregunta | Respuesta |
|---|---|---|
| `noul` | sí/no (`instructions`, `criteria.true/false`) | `noul: float` (probabilidad de sí) |
| `choice` | una entre varias (`criteria: {etiqueta: descripción}`) | `choice`, `confidence`, `probabilities` |
| `score` | rúbrica ordinal (`criteria: [nivel0, nivel1, ...]`) | `score` (esperado), `confidence`, `legend`, `probabilities` |

Datos operativos publicados: contexto de 64K tokens (32K para el estado), precio USD 0,042 por millón de tokens de entrada, salida gratuita, límites de 1.200 req/min. Latencia típica ~0,1 s. Auth por `Authorization: Bearer $TYPESAFE_API_KEY`. Variables: `TYPESAFE_API_KEY`, `TYPESAFE_BASE_URL`, `TYPESAFE_DEFAULT_MODEL`.

Limitación documentada por TypeSafe: Jev trata el estado como datos, pero texto diseñado para manipular la respuesta puede desplazarla. Por eso el Guardián combina Jev con **verificaciones deterministas** (SPF/DKIM/DMARC de cabeceras, listas de dominios, patrones de inyección, URLs acortadas) y la clasificación con baja confianza cae al LLM de respaldo (ADR-0003).

### 2.3 Modelos por defecto (configurables desde el panel)

| Agente | Proveedor:modelo por defecto | Alternativas |
|---|---|---|
| Guardián | `jev:jev-latest` + reglas deterministas | `anthropic:claude-haiku-4-5` |
| Clasificador | `jev:jev-latest` | `anthropic:claude-haiku-4-5` (respaldo automático), `openai:gpt-4o-mini`, `gemini:gemini-2.5-flash` |
| Enrutador | sin modelo (reglas) | `anthropic:claude-haiku-4-5` para desempates |
| Redactor | `anthropic:claude-opus-5-5` (effort `medium`) | `anthropic:claude-sonnet-5-5` cuando el costo importe más que la calidad |
| Agente Webchat | `anthropic:claude-sonnet-5-5` (streaming, effort `low`) | `anthropic:claude-opus-5-5` |
| Evaluador (Fase 2) | `anthropic:claude-opus-5-5` | — |

Precios de referencia Anthropic (USD por millón de tokens, entrada/salida): Opus 5.5 4/20, Sonnet 5.5 2/10, Haiku 4.5 1/5. Para Anthropic se activa `fallbacks: "default"` (beta `server-side-fallback-2026-07-01`) para que una negativa del clasificador de seguridad del modelo se reenrute en el servidor. Los modelos 4.6+ no aceptan prefill ni `budget_tokens`; se usa `thinking: {type: "adaptive"}` y `output_config.effort`.

### 2.4 PostgreSQL como única dependencia

Se descarta Redis en MVP para cumplir "se crea sola la primera vez": `procrastinate` implementa cola, reintentos, programación y bloqueos sobre PostgreSQL con `LISTEN/NOTIFY` y `SKIP LOCKED`. `langgraph-checkpoint-postgres` guarda el estado del grafo en la misma base. Cuando el volumen supere ~50 trabajos/s por base, se introduce Redis + arq sin tocar el dominio (el puerto `JobQueuePort` lo aísla).

### 2.5 Angular 22 zoneless

Nuevos proyectos Angular ya nacen sin `zone.js`. Con signals, `computed`, `resource()` y Signal Forms se elimina la mayoría del boilerplate de RxJS en formularios y estado. Angular Material aporta accesibilidad; Tailwind 4 aporta los tokens de color de Viamatica como variables CSS.

## 3. Dependencias Python (extracto de `backend/pyproject.toml`)

```toml
[project]
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.141,<0.142",
  "uvicorn[standard]>=0.54",
  "pydantic>=2.13",
  "pydantic-settings>=2.15",
  "sqlalchemy[asyncio]>=2.1",
  "asyncpg>=0.31",
  "alembic>=1.20",
  "procrastinate[psycopg]>=3.10",
  "langgraph>=1.2,<2",
  "langgraph-checkpoint-postgres>=3.1",
  "langchain>=1.4,<2",
  "langchain-anthropic>=1.7",
  "anthropic>=1.9",
  "typesafe-sdk[http2]>=0.7",
  "langchain-typesafe>=0.0.1a3",
  "aioimaplib>=2.0",
  "aiosmtplib>=5.1",
  "nh3>=0.3",
  "email-validator>=2.3",
  "pyjwt[crypto]>=2.15",
  "argon2-cffi>=25.1",
  "cryptography>=50",
  "slowapi>=0.1.10",
  "structlog>=26",
  "opentelemetry-sdk>=1.45",
  "opentelemetry-instrumentation-fastapi",
  "opentelemetry-instrumentation-sqlalchemy",
  "opentelemetry-instrumentation-httpx",
  "opentelemetry-exporter-otlp",
  "httpx>=0.28",
  "tenacity>=9",
]

[project.optional-dependencies]
openai = ["langchain-openai>=1.6"]
gemini = ["langchain-google-genai>=4.4"]
langfuse = ["langfuse>=4"]

[dependency-groups]
dev = ["pytest>=9", "pytest-asyncio", "pytest-cov", "testcontainers[postgres]", "respx",
       "ruff>=0.16", "pyrefly>=1.3", "bandit>=1.9", "pip-audit>=2.10", "semgrep"]
```

## 4. Dependencias frontend (extracto de `frontend/package.json`)

```json
{
  "dependencies": {
    "@angular/core": "^22.2.0", "@angular/common": "^22.2.0", "@angular/router": "^22.2.0",
    "@angular/forms": "^22.2.0", "@angular/material": "^22.2.0", "@angular/cdk": "^22.2.0",
    "@ngrx/signals": "^22.0.1", "echarts": "^6.1.0", "ngx-echarts": "^22.0.0", "tailwindcss": "^4.3.3"
  },
  "devDependencies": {
    "@angular/cli": "^22.2.0", "typescript": "~7.0", "vitest": "^5.0", "@playwright/test": "^1.63",
    "eslint": "^9", "angular-eslint": "^22", "prettier": "^3"
  }
}
```

## 5. Herramientas de desarrollo

| Herramienta | Uso |
|---|---|
| `make dev` | Levanta PostgreSQL en Docker, backend con recarga y frontend con `ng serve`. |
| `make check` | ruff + pyrefly + pytest + eslint + vitest (lo mismo que CI). |
| `make security` | bandit, pip-audit, npm audit, gitleaks, semgrep. |
| `pre-commit` | Hooks locales espejo de los hooks de Claude Code (`.claude/hooks`). |
| Renovate | Actualización de dependencias con PR automáticos. |

## 6. Entornos

| Entorno | Infra | Notas |
|---|---|---|
| Local | Docker Compose (`db`) + procesos locales | `.env` desde `.env.example`; clave maestra generada por `make keys`. |
| Staging | Compose completo o Kubernetes (Helm en Fase 2) | Datos sintéticos; cuentas de correo de prueba. |
| Producción | Compose en VM endurecida o K8s | Secretos vía variables/KMS; TLS terminado en reverse proxy (Caddy/Traefik); respaldos `pg_dump` diarios + PITR. |
