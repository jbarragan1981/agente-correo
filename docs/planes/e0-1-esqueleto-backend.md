# Plan E0.1 · Esqueleto backend

**Fase:** 0 · Cimientos · **Agentes:** backend, qa · **Rama:** `feature/e0-1-esqueleto-backend`
**Referencias:** `docs/10-roadmap.md` (E0.1), `docs/01-arquitectura.md` §3, `docs/02-stack-tecnologico.md` §3, `docs/04-api.md` §9 y §12, `docs/07-seguridad.md` §3, §5 y §7, `docs/08-observabilidad.md` §1, `docs/09-testing-y-calidad.md`, ADR-0004, **ADR-0007 (nueva)**.

## 1. Objetivo

Dejar un backend FastAPI arrancable, tipado y probado, con estructura hexagonal vacía y los controles transversales de seguridad y observabilidad que heredarán todas las épicas: configuración validada con fallo cerrado, logs JSON con redacción, correlation id, cabeceras de seguridad, CORS por allowlist, errores `problem+json`, sondas de salud y contenedor endurecido.

**Fuera de alcance:** bootstrap de BD, modelos SQLAlchemy, Alembic y semillas (E0.2); autenticación, RBAC, auditoría, rate limiting y límite de tamaño de body (E0.3); OpenTelemetry y `/metrics` (E1.10); dependencias de IA (`langgraph`, `langchain*`, `anthropic`, `typesafe-sdk`), `procrastinate`, IMAP/SMTP (E1.x); entrypoint `app.worker` (E1.3); CI (E0.5).

## 2. Criterios de aceptación (medibles)

| # | Criterio | Cómo se verifica |
|---|---|---|
| CA1 | `cd backend && uv sync --locked --group dev` termina sin errores con Python 3.12 y `uv.lock` versionado. | Comando con código 0. |
| CA2 | El lockfile no contiene dependencias de IA ni de fases posteriores. | `grep -Ei '^name = "(anthropic|openai|langchain.*|langgraph.*|typesafe.*|procrastinate|alembic|aioimaplib|aiosmtplib)"' backend/uv.lock` sin resultados. |
| CA3 | `make check-backend` en verde: `ruff check`, `ruff format --check`, `pyrefly check` con 0 errores y `pytest -m "not integracion and not e2e and not eval"` sin fallos. | Salida del comando. |
| CA4 | Cobertura de `app/` ≥ 85 % con pruebas `unit` + `api`; `app/core/` ≥ 90 %. | `uv run pytest -m "unit or api" --cov=app --cov-report=term-missing --cov-fail-under=85`. |
| CA5 | Con `ENV=production` el proceso no arranca si falta o es inválida cualquiera de: `APP_MASTER_KEY` (base64 de 32 bytes), `JWT_SECRET` (≥ 32 bytes), `DATABASE_URL`, `CORS_ORIGENES` (no vacío, solo `https`), o si `DEBUG=true`. El mensaje nombra el campo y **no contiene su valor**. | Pruebas parametrizadas de `Settings` (9 casos mínimo). |
| CA6 | `GET /api/v1/salud` → 200 `{"estado":"vivo"}` sin consultar la BD. | Prueba API con sonda espía: 0 llamadas. |
| CA7 | `GET /api/v1/salud/listo` → 200 `{"estado":"listo","comprobaciones":{"base_datos":"ok"}}` con BD accesible; 503 `application/problem+json` con `type="no_listo"` y `comprobaciones.base_datos="falla"` con BD caída, en ≤ `SALUD_BD_TIMEOUT_S` + 0,5 s. El cuerpo no incluye host, DSN, usuario ni texto de la excepción. | Prueba API con sonda falsa + prueba de integración con PostgreSQL 17 (contenedor) y puerto cerrado. |
| CA8 | Toda respuesta (incluidas 404, 405, 400, 500 y 503) lleva `X-Request-ID` y las cabeceras de §4.4. | Prueba API parametrizada por código de estado. |
| CA9 | Errores con `Content-Type: application/problem+json`, campos `type`, `title`, `status`, `detail`, `instance="urn:uuid:<correlation_id>"`; el 500 no expone mensaje de excepción ni traza; el 400 de validación no devuelve los valores enviados. | Pruebas API con rutas de prueba que lanzan excepción y reciben body inválido. |
| CA10 | CORS: un origen de la allowlist recibe `Access-Control-Allow-Origin` igual al origen y `Allow-Credentials: true`; un origen ajeno no recibe `Access-Control-Allow-Origin`; `*` se rechaza en configuración. | Pruebas API de preflight y de `Settings`. |
| CA11 | Con `ENV=production`, `/api/v1/docs`, `/api/v1/redoc`, `/api/v1/openapi.json`, `/docs`, `/redoc` y `/openapi.json` responden 404. En `development` `/api/v1/openapi.json` responde 200. | Prueba API. |
| CA12 | Cada línea que el proceso escribe en stdout (app, `uvicorn.error`, `sqlalchemy`) es JSON válido con `timestamp`, `nivel`, `evento` y `correlation_id` cuando hay petición en curso; no aparecen valores de claves sensibles ni patrones de token/API key/DSN con contraseña; los emails salen como `j***@dominio`. | Pruebas unitarias del procesador y prueba API que captura stdout. |
| CA13 | El log de acceso propio registra `metodo`, `ruta` **sin query string**, `estado`, `duracion_ms`; el access log de Uvicorn está deshabilitado. | Prueba API con `?token=abc` que verifica ausencia de `abc` en logs. |
| CA14 | Pruebas de arquitectura: `domain/` no importa nada fuera de la stdlib; `application/` no importa `fastapi`, `starlette`, `sqlalchemy`, `pydantic_settings`, `structlog`, `app.api`, `app.infrastructure`; ningún módulo fuera de `app/providers/` importa SDKs de IA. | `tests/unit/test_arquitectura.py`. |
| CA15 | `docker compose -f infra/docker-compose.yml config -q` sin errores. Con daemon Docker: `docker compose -f infra/docker-compose.yml up -d --build db api` deja `api` en `healthy` en ≤ 60 s y `/api/v1/salud/listo` devuelve 200. | Comando (el segundo, en máquina con Docker o CI E0.5). |
| CA16 | `uv run bandit -q -r app -ll` sin hallazgos y `uv run pip-audit` sin vulnerabilidades conocidas. | Comandos. |

## 3. Verificación del entorno local (hecha por el arquitecto el 2026-09-28)

| Comprobación | Resultado |
|---|---|
| `uv --version` | `uv 0.8.17` |
| Python 3.12 | `/usr/bin/python3.12` (3.12.3) disponible; `uv python list` lo detecta. El `python3` por defecto es 3.11, por eso se fija `.python-version`. |
| `uv pip download` | **No existe** en uv 0.8.17 (`unrecognized subcommand 'download'`). Se usó `uv pip compile` y una instalación en un venv temporal. |
| Acceso a PyPI | Sí, vía proxy. `uv pip compile --python-version 3.12` resolvió: fastapi 0.141.1, starlette 1.7.0, uvicorn 0.54.0, pydantic 2.13.5, pydantic-settings 2.15.0, sqlalchemy 2.1.1, asyncpg 0.31.0, structlog 26.1.0, httpx 0.28.1, pytest 9.1.1, pytest-asyncio 1.4.0, pytest-cov 7.1.0, ruff 0.16.9, pyrefly 1.3.1, bandit 1.9.4, pip-audit 2.10.1, testcontainers 4.15.0. La instalación real de wheels en Python 3.12 funcionó. |
| Docker | CLI 29.3.1 presente, **daemon no disponible** (`/var/run/docker.sock` no existe). No se pueden ejecutar `docker build`, `compose up` ni testcontainers en este entorno. |

**Cómo verificará cada agente en local:**
1. `cd backend && uv python pin 3.12 && uv lock && uv sync --locked --group dev` (usa `/usr/bin/python3.12`, sin descargar intérpretes).
2. `make check-backend` y `uv run pytest -m "unit or api" --cov=app --cov-fail-under=85`.
3. `uv run bandit -q -r app -ll && uv run pip-audit`.
4. `docker compose -f infra/docker-compose.yml config -q` (no requiere daemon).
5. Las pruebas `integracion` (testcontainers) y el arranque con Compose (CA15) **no se pueden ejecutar aquí**: se escriben, se validan con `pytest --collect-only -m integracion` y se marcan en el reporte como "pendiente de ejecutar con Docker" (máquina del desarrollador o CI de E0.5). Nunca se omiten ni se marcan `skip` para simular verde.
6. Si en otra sesión PyPI no respondiera, **no** se instala nada por fuera de `uv` ni se edita `uv.lock` a mano: se detiene la tarea y se informa.

## 4. Diseño

### 4.1 Estructura de paquetes

```
backend/
├── .python-version                 # 3.12
├── pyproject.toml · uv.lock · README.md
├── app/
│   ├── __init__.py
│   ├── main.py                     # crear_app(settings: Settings | None = None) -> FastAPI (fábrica, sin efectos al importar)
│   ├── core/
│   │   ├── config.py               # Settings, cargar_settings(), ConfiguracionInvalida
│   │   └── logging.py              # configurar_logging(nivel), redactar(), obtener_logger()
│   ├── domain/
│   │   └── errores.py              # ExcepcionDominio (base), NoEncontrado, Conflicto
│   ├── application/
│   │   ├── ports/salud.py          # SondaDependenciaPort
│   │   ├── use_cases/comprobar_preparacion.py
│   │   └── policies/__init__.py
│   ├── agents/__init__.py          # vacío (E1.4)
│   ├── providers/__init__.py       # vacío (E1.1)
│   ├── infrastructure/
│   │   └── db/{motor.py, sonda_postgres.py}
│   └── api/
│       ├── dependencias.py         # proveedores de dependencias (settings, sondas, caso de uso)
│       ├── errores.py              # manejadores problem+json, tabla ExcepcionDominio→HTTP
│       ├── middleware/{correlacion.py, cabeceras.py, errores_inesperados.py}
│       ├── routers/salud.py
│       └── schemas/{salud.py, problema.py}
└── tests/
    ├── conftest.py
    ├── unit/{core,application,api}/ · unit/test_arquitectura.py
    ├── api/test_salud.py · test_errores.py · test_cors.py · test_cabeceras.py · test_docs.py · test_logs_acceso.py
    └── integracion/test_sonda_postgres.py
```

Cada `__init__.py` de capa lleva un docstring de una línea con su responsabilidad y la regla de dependencias. Sin código especulativo en `agents/` ni `providers/`.

### 4.2 `pyproject.toml` (dependencias solo de E0.1)

```toml
[project]
name = "agente-correo-backend"
version = "0.1.0"
requires-python = ">=3.12,<3.13"          # igual que la imagen python:3.12-slim
dependencies = [
  "fastapi>=0.141,<0.142",
  "uvicorn[standard]>=0.54",
  "pydantic>=2.13",
  "pydantic-settings>=2.15",
  "sqlalchemy[asyncio]>=2.1",              # motor async para la sonda; E0.2 lo reutiliza
  "asyncpg>=0.31",
  "structlog>=26",
]

[dependency-groups]
dev = [
  "pytest>=9", "pytest-asyncio>=1.4", "pytest-cov>=7", "httpx>=0.28",
  "testcontainers[postgres]>=4.15",
  "ruff>=0.16", "pyrefly>=1.3", "bandit>=1.9", "pip-audit>=2.10",
]

[tool.uv]
package = false                             # aplicación, no librería; `app` se importa desde la raíz
```

`httpx` pasa a dependencias de runtime cuando un adaptador lo necesite (E1.1). `alembic`, `procrastinate`, IA, `slowapi`, `pyjwt`, `argon2-cffi`, `cryptography` y OTel se añaden con `uv add` en sus épicas. `semgrep` no se añade al grupo dev (dependencias pesadas); en E0.1 el objetivo `make security` pasa a invocarlo con `uvx semgrep` (tarea B8).

**Ruff**
```toml
[tool.ruff]
target-version = "py312"
line-length = 100
[tool.ruff.lint]
select = ["E","W","F","I","B","UP","S","ASYNC","SIM","RUF","PT","DTZ","T20","BLE","C4","PIE","RET","PTH","ERA","TRY","N"]
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "S105", "S106"]      # assert y valores de prueba evidentes
[tool.ruff.format]
quote-style = "double"
```

**Pyrefly**
```toml
[tool.pyrefly]
project-includes = ["app", "tests"]
python-version = "3.12"
search-path = ["."]
```
Todo el código con anotaciones completas; sin `# type: ignore` salvo con comentario que explique la causa.

**Pytest (marcadores estrictos)**
```toml
[tool.pytest.ini_options]
minversion = "9.0"
testpaths = ["tests"]
pythonpath = ["."]
addopts = ["--strict-markers", "--strict-config", "-ra"]
xfail_strict = true
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
filterwarnings = ["error"]                 # añadir ignores puntuales y comentados si una librería avisa
markers = [
  "unit: sin E/S, puertos falsos",
  "contrato: adaptadores de proveedor con respx/cassettes",
  "integracion: requiere Docker (testcontainers)",
  "api: app ASGI con httpx, dependencias falsas",
  "agentes: grafo LangGraph con proveedores falsos",
  "e2e: Compose + Playwright",
  "eval: evaluación del clasificador",
  "lento: > 1 s",
]

[tool.coverage.run]
source = ["app"]
branch = true
```
`tests/conftest.py` implementa `pytest_collection_modifyitems` que asigna el marcador según el directorio (`tests/unit` → `unit`, `tests/api` → `api`, `tests/integracion` → `integracion`) y **falla la colección** si un archivo de prueba está fuera de esos directorios. Así `make check` (`-m "not integracion ..."`) nunca ejecuta por accidente pruebas que requieren Docker.

### 4.3 Configuración (`app/core/config.py`) · ADR-0007

```python
Entorno = Literal["development", "test", "production"]
NivelLog = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RAIZ_REPO / ".env", env_file_encoding="utf-8",
        extra="ignore", hide_input_in_errors=True, case_sensitive=False, frozen=True,
    )
    env: Entorno = "development"
    debug: bool = False
    log_level: NivelLog = "INFO"
    database_url: SecretStr | None = None            # obligatoria en production; esquema postgresql+asyncpg://
    app_master_key: SecretStr | None = None          # base64 de 32 bytes exactos si se define
    jwt_secret: SecretStr | None = None              # ≥ 32 bytes si se define
    cors_origenes: Annotated[list[str], NoDecode] = []   # "https://a,https://b" → lista; sin '*', sin ruta
    salud_bd_timeout_s: float = Field(2.0, gt=0, le=10)

    @property
    def es_produccion(self) -> bool: ...
    def url_base_datos(self) -> str: ...             # default de desarrollo si None y env != production

# Validadores
# - field_validator("cors_origenes", mode="before"): split por coma, strip, descarta vacíos.
# - field_validator("cors_origenes"): cada origen = scheme://host[:puerto], esquema http|https, sin ruta/query/'*'.
# - field_validator("app_master_key"): base64 estricto → exactamente 32 bytes.
# - field_validator("jwt_secret"): len(utf-8) >= 32.
# - field_validator("database_url"): prefijo "postgresql+asyncpg://".
# - model_validator(mode="after") _exigir_produccion: si env == "production" → app_master_key, jwt_secret,
#   database_url presentes; debug False; cors_origenes no vacío y todos https.

class ConfiguracionInvalida(Exception):
    """Contiene solo [(campo, mensaje)], nunca valores."""

def cargar_settings() -> Settings: ...  # envuelve ValidationError → ConfiguracionInvalida
```

- Default de desarrollo de la URL: `postgresql+asyncpg://postgres:postgres@localhost:5432/agente_correo` (coincide con Compose; valor de ejemplo evidente). En `production` no hay default.
- Nadie fuera de `core/config.py` lee `os.environ`.
- `FORWARDED_ALLOW_IPS` no es campo de `Settings`: la lee Uvicorn directamente.
- Variables nuevas a documentar (ver B9 y riesgo R9): `ENV`, `DEBUG`, `LOG_LEVEL`, `DATABASE_URL`, `APP_MASTER_KEY`, `JWT_SECRET`, `CORS_ORIGENES`, `SALUD_BD_TIMEOUT_S`, `FORWARDED_ALLOW_IPS`.

### 4.4 Middleware y orden

Todos los middlewares propios son **ASGI puros** (sin `BaseHTTPMiddleware`) para no romper streaming/WebSocket futuros. Orden de fuera hacia dentro (en Starlette se registran en orden inverso):

```
CorrelacionMiddleware → CabecerasSeguridadMiddleware → CORSMiddleware → ErroresInesperadosMiddleware → router
```
(OTel se inserta tras Correlación en E1.10; rate limit y límite de body entre CORS y Errores en E0.3.)

**CorrelacionMiddleware** (`api/middleware/correlacion.py`)
- Lee `X-Request-ID`; lo acepta solo si es un UUID válido (`uuid.UUID(valor)` y longitud 36); si no, genera `uuid4()`. Esto evita inyección de cabeceras/logs con valores arbitrarios.
- Guarda el id en `scope["state"]["correlation_id"]`, hace `structlog.contextvars.bind_contextvars(correlation_id=...)` y lo limpia al terminar.
- Añade `X-Request-ID` a la respuesta.
- Emite el log de acceso `evento="http.peticion"` con `metodo`, `ruta` (`scope["path"]`, **sin query string**), `estado`, `duracion_ms` (`time.perf_counter`).

**CabecerasSeguridadMiddleware** (`api/middleware/cabeceras.py`), sobre todas las respuestas HTTP:

| Cabecera | Valor |
|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` |
| `Cross-Origin-Opener-Policy` | `same-origin` |
| `Cross-Origin-Resource-Policy` | `same-origin` |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'; base-uri 'none'` |
| `Cache-Control` | `no-store` |

Excepción única: las rutas de documentación (`/api/v1/docs`, `/api/v1/redoc`), que solo existen fuera de producción, reciben una CSP que permite el JS/CSS de Swagger UI (`script-src 'self' https://cdn.jsdelivr.net; style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' data: https://fastapi.tiangolo.com; default-src 'none'; frame-ancestors 'none'`). Se decide por ruta en una función pura `csp_para(ruta: str) -> str` con prueba unitaria. El servidor no envía `Server` (`--no-server-header`).

**CORSMiddleware** (Starlette): `allow_origins=settings.cors_origenes` (lista vacía = sin CORS), `allow_credentials=True`, `allow_methods=["GET","POST","PUT","PATCH","DELETE"]`, `allow_headers=["Authorization","Content-Type","X-Request-ID","Idempotency-Key"]`, `expose_headers=["X-Request-ID","Retry-After"]`, `max_age=600`. Nunca `allow_origin_regex` ni `*`.

**ErroresInesperadosMiddleware** (`api/middleware/errores_inesperados.py`): captura cualquier excepción no manejada que salga del router; si la respuesta no empezó, registra `evento="http.error_inesperado"` con `exc_info` (pasa por redacción) y responde 500 `problem+json` `type="error_interno"`, `detail="Error interno. Cite el identificador al reportarlo."`. Motivo: el manejador `Exception` de Starlette corre en `ServerErrorMiddleware`, **fuera** de los middlewares de usuario, y su respuesta saldría sin `X-Request-ID`, sin cabeceras de seguridad y sin CORS. `FastAPI(debug=False)` siempre (ADR-0007).

### 4.5 Errores `problem+json` (RFC 9457)

```python
class ErrorCampo(BaseModel):
    campo: str            # "body.email" (loc unido por puntos)
    mensaje: str          # msg de Pydantic; nunca el valor recibido

class Problema(BaseModel):
    model_config = ConfigDict(extra="allow")   # extensiones: errores, comprobaciones
    type: str             # código de docs/04-api.md §12
    title: str
    status: int
    detail: str | None = None
    instance: str         # "urn:uuid:<correlation_id>"
```

| Origen | HTTP | `type` |
|---|---|---|
| `RequestValidationError` | 400 | `validacion` (con `errores: list[ErrorCampo]`, sin `input` ni `ctx`) |
| `StarletteHTTPException` 404 | 404 | `no_encontrado` |
| `StarletteHTTPException` 405 | 405 | `metodo_no_permitido` (**nuevo**, se añade a `docs/04-api.md` §12) |
| Otros `HTTPException` | su código | `error_http` con `title` estándar del código |
| `NoEncontrado` / `Conflicto` (dominio) | 404 / 409 | `no_encontrado` / `conflicto` |
| Preparación fallida | 503 | `no_listo` (con `comprobaciones`) |
| Excepción no manejada | 500 | `error_interno` (**nuevo**, se añade a §12) |

La tabla `ExcepcionDominio → (status, type, title)` vive en `api/errores.py` (el dominio no conoce HTTP). Las respuestas usan `media_type="application/problem+json"`. En OpenAPI se declara `Problema` como respuesta de error por defecto de los routers (`responses={400: ..., 404: ..., 500: ...}` vía un diccionario compartido).

### 4.6 Logging (`app/core/logging.py`)

```python
def configurar_logging(nivel: NivelLog) -> None
def redactar(logger, metodo: str, evento: dict) -> dict      # procesador structlog
def obtener_logger(nombre: str) -> structlog.stdlib.BoundLogger
```

- Cadena: `merge_contextvars` → `add_log_level` → `TimeStamper(fmt="iso", utc=True, key="timestamp")` → `format_exc_info` → **`redactar`** (siempre después de `format_exc_info` para limpiar también trazas) → `EventRenamer("evento")` → `JSONRenderer()`.
- La librería estándar (`uvicorn`, `uvicorn.error`, `sqlalchemy`, `asyncio`) se enruta por `structlog.stdlib.ProcessorFormatter` con los mismos procesadores: una sola salida JSON por stdout. `uvicorn.access` se silencia (el acceso lo registra `CorrelacionMiddleware`). `configurar_logging` se llama dentro de `crear_app`, después de que Uvicorn aplique su `dictConfig`.
- `redactar` recorre dicts, listas y tuplas de forma recursiva (profundidad máx. 8):
  - **Por clave** (insensible a mayúsculas, subcadena): `password`, `contrasena`, `contraseña`, `secreto`, `secret`, `token`, `authorization`, `api_key`, `apikey`, `cookie`, `master_key`, `jwt`, `database_url`, `dsn` → `"[REDACTADO]"`.
  - **Por valor** (en cualquier string, incluidos `evento` y `exception`): JWT (`eyJ…​.eyJ…​.…`), `Bearer <x>`, `sk-ant-…`, `sk-…` (≥ 20), `ts_…`, contraseña en URL (`://usuario:***@`) → reemplazo del fragmento.
  - **Emails**: `juan.perez@dominio.com` → `j***@dominio.com`.
  - `SecretStr` → `"**********"`.
  - Strings de más de 2 000 caracteres se truncan con sufijo `…[truncado]`.
- Nunca se loguean cuerpos de petición.

### 4.7 Salud: puerto, caso de uso y adaptador

```python
# application/ports/salud.py
class ResultadoSonda(StrEnum): OK = "ok"; FALLA = "falla"

class SondaDependenciaPort(Protocol):
    @property
    def nombre(self) -> str: ...                    # "base_datos"; E0.2 añade "migraciones", E1.1 "proveedores"
    async def comprobar(self) -> ResultadoSonda: ... # no lanza; devuelve FALLA

# application/use_cases/comprobar_preparacion.py
@dataclass(frozen=True)
class InformePreparacion:
    listo: bool
    comprobaciones: Mapping[str, ResultadoSonda]

class ComprobarPreparacion:
    def __init__(self, sondas: Sequence[SondaDependenciaPort], timeout_s: float) -> None: ...
    async def ejecutar(self) -> InformePreparacion:
        # asyncio.gather de todas las sondas, cada una envuelta en asyncio.timeout(timeout_s);
        # TimeoutError o cualquier excepción inesperada ⇒ FALLA (se registra el tipo de excepción, sin mensaje).
```

```python
# infrastructure/db/motor.py
def crear_motor(settings: Settings) -> AsyncEngine
    # create_async_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5,
    #                     connect_args={"timeout": settings.salud_bd_timeout_s}); perezoso: no conecta al crear.

# infrastructure/db/sonda_postgres.py
class SondaPostgres:            # implementa SondaDependenciaPort
    nombre = "base_datos"
    def __init__(self, motor: AsyncEngine) -> None: ...
    async def comprobar(self) -> ResultadoSonda:   # SELECT 1 vía conn.execute(text("SELECT 1"))
```

Ciclo de vida en `crear_app`: `lifespan` crea el motor (sin conectar; la API arranca aunque la BD esté caída), lo guarda en `app.state.motor` y hace `await motor.dispose()` al apagar. `api/dependencias.py` expone `dep_comprobar_preparacion(request) -> ComprobarPreparacion`; las pruebas lo sustituyen con `app.dependency_overrides`.

### 4.8 Endpoints

| Método | Ruta | Rol | Respuesta 2xx | Errores |
|---|---|---|---|---|
| GET | `/api/v1/salud` | público (contrato `docs/04-api.md` §9) | 200 `SaludOut {estado: Literal["vivo"]}` | 405 |
| GET | `/api/v1/salud/listo` | público | 200 `PreparacionOut {estado: Literal["listo"], comprobaciones: dict[str, Literal["ok"]]}` | 503 `Problema` + `comprobaciones: dict[str, Literal["ok","falla"]]`, 405 |

- Las respuestas no incluyen versión, hostname ni detalles de dependencias (evita fingerprinting).
- No hay endpoints autenticados en E0.1; la regla "pruebas 401/403 por endpoint" no aplica. E0.3 añadirá la dependencia de autenticación y las pruebas 401/403 a todo endpoint no público.
- `crear_app` monta `APIRouter(prefix="/api/v1")`; documentación: `docs_url="/api/v1/docs"`, `redoc_url="/api/v1/redoc"`, `openapi_url="/api/v1/openapi.json"` fuera de producción, y `None` en los tres con `ENV=production`. El acceso de admin a OpenAPI en producción (mencionado en `docs/04-api.md`) se decide en E0.3, cuando exista autenticación.

### 4.9 Contenedor y Compose (revisión de `infra/`)

Hallazgos en los archivos actuales y cambio requerido:

| Archivo | Hallazgo | Cambio |
|---|---|---|
| `Dockerfile.backend` | `ghcr.io/astral-sh/uv:latest` sin fijar (cadena de suministro). | Fijar `ghcr.io/astral-sh/uv:0.8.17` (digest en producción, E1.12). |
| `Dockerfile.backend` | `uv sync --frozen … \|\| uv sync …` ignora el lockfile si falla. | Solo `uv sync --locked --no-dev --no-install-project`; sin fallback. `uv.lock` obligatorio. |
| `Dockerfile.backend` | `COPY backend/ ./` copia pruebas y cualquier `.env` local a la imagen. | Copiar solo `backend/pyproject.toml`, `backend/uv.lock` y `backend/app/`. Crear `.dockerignore` en la raíz (contexto `..`) excluyendo `**/.env*` (salvo `.env.example`), `.git`, `**/.venv`, `**/__pycache__`, `**/.pytest_cache`, `**/.ruff_cache`, `backend/tests`, `frontend/node_modules`, `evals/reportes`, `*.pem`, `*.key`. |
| `Dockerfile.backend` | `CMD` con `app.main:app` y access log de Uvicorn. | `CMD ["uvicorn","--factory","app.main:crear_app","--host","0.0.0.0","--port","8000","--no-server-header","--no-access-log","--proxy-headers"]`; `ENV FORWARDED_ALLOW_IPS=127.0.0.1`. |
| `docker-compose.yml` `api` | `--forwarded-allow-ips "*"` confía `X-Forwarded-For` de cualquiera (falsea IP en logs y en el rate limit de E0.3). | Quitar el flag del `command` (usar el `CMD` de la imagen) y definir `FORWARDED_ALLOW_IPS: ${FORWARDED_ALLOW_IPS:-127.0.0.1}`; documentar que se pone la IP/CIDR del reverse proxy al desplegar. |
| `docker-compose.yml` `db` | Crea solo la base `postgres`; `DATABASE_URL` apunta a `agente_correo`, que no existiría hasta E0.2 ⇒ readiness siempre 503. | `POSTGRES_DB: ${POSTGRES_DB:-agente_correo}` y `pg_isready -U … -d agente_correo`. E0.2 sigue implementando la creación automática para bases externas. |
| `docker-compose.yml` `worker` | `python -m app.worker` no existe hasta E1.3; `compose up` fallaría. | `profiles: ["worker"]` hasta E1.3 (se retira el perfil en esa épica). |
| `docker-compose.yml` `web` | `frontend/` vacío hasta E0.4; el build falla. | `profiles: ["web"]` hasta E0.4. |
| `docker-compose.yml` `api`, `worker` | `env_file: [../.env]` obligatorio: `compose config` falla sin `.env`. | `env_file: [{path: ../.env, required: false}]`. Sin `.env`, la imagen corre con `ENV=production` y **falla cerrada** por falta de claves (comportamiento deseado). |
| `Makefile` | `dev` muestra `uvicorn app.main:app`; `security` usa `uv run semgrep`, que no estará instalado. | `uv run uvicorn --factory app.main:crear_app --reload`; `uvx semgrep@<versión fijada>`. |

El resto (usuario 10001, `read_only`, `tmpfs`, `cap_drop: ALL`, `no-new-privileges`, puertos solo en `127.0.0.1`, `HEALTHCHECK` a `/api/v1/salud`, healthcheck de Compose a `/salud/listo`) ya cumple `docs/07-seguridad.md` §7 y se conserva.

### 4.10 Métricas y auditoría

E0.1 no introduce acciones de negocio ni cambios de estado: no hay auditoría. Las métricas OTel (`http_server_*`) llegan en E1.10; mientras tanto el log de acceso (`duracion_ms`, `estado`) es la señal disponible. Esto se deja explícito para que qa no lo marque como faltante.

## 5. Tareas

### Backend

| # | Tarea | Depende de | Paralelo con |
|---|---|---|---|
| B1 | Proyecto uv: `.python-version` (3.12), `pyproject.toml` de §4.2 (deps, grupo dev, ruff, pyrefly, pytest, coverage), `uv lock`, `uv sync --locked --group dev`. Paquetes vacíos de §4.1 con docstrings. `tests/conftest.py` mínimo con el marcado por directorio. | — | — |
| B2 | `core/config.py`: `Settings`, validadores, `cargar_settings`, `ConfiguracionInvalida` (§4.3) + pruebas unitarias. | B1 | B3, B4 |
| B3 | `core/logging.py`: `configurar_logging`, `redactar`, enrutado de stdlib (§4.6) + pruebas unitarias. | B1 | B2, B4 |
| B4 | `domain/errores.py`, `api/schemas/problema.py`, `api/errores.py` (manejadores y tabla de mapeo, §4.5) + pruebas unitarias. | B1 | B2, B3 |
| B5 | Middlewares ASGI: correlación con log de acceso, cabeceras con `csp_para`, errores inesperados (§4.4) + pruebas unitarias. | B3, B4 | B6 |
| B6 | Puerto `SondaDependenciaPort`, caso de uso `ComprobarPreparacion`, `crear_motor`, `SondaPostgres` (§4.7) + pruebas unitarias del caso de uso con sondas falsas. | B2 | B3, B4, B5 |
| B7 | `api/routers/salud.py`, `api/schemas/salud.py`, `api/dependencias.py`, `main.crear_app` (lifespan, orden de middlewares, CORS, docs condicionales, prefijo `/api/v1`, `FastAPI(debug=False)`) (§4.8). | B2–B6 | B8 |
| B8 | Infra según §4.9: `Dockerfile.backend`, `.dockerignore`, `docker-compose.yml`, `Makefile`. Verificar `docker compose -f infra/docker-compose.yml config -q`. | B1 (forma del comando decidida en este plan) | B2–B7 |
| B9 | Documentación: `backend/README.md` (arranque con `--factory`, tabla de variables de §4.3 con valores de ejemplo evidentes, cómo generar claves con `make keys`); `docs/04-api.md` §9 (formas de respuesta de `/salud` y `/salud/listo`, cabecera `X-Request-ID`) y §12 (`metodo_no_permitido` 405, `error_interno` 500, formato `instance`); `docs/08-observabilidad.md` §1 (campos del log de acceso). | B7 | — |
| B10 | Cierre backend: `make check-backend`, `bandit`, `pip-audit`, `pytest --collect-only -m integracion`; reporte con salida real. | B1–B9 | — |

### QA

| # | Tarea | Depende de | Paralelo con |
|---|---|---|---|
| Q1 | Completar `tests/conftest.py`: `settings_prueba()` (fábrica de `Settings(_env_file=None, env="test", …)` con valores de ejemplo), `app_prueba` (`crear_app(settings)`), `cliente_api` (`httpx.AsyncClient(transport=ASGITransport(app), base_url="http://prueba")`), `SondaFalsa(resultado, retardo)`, `SondaEspia`, fixture `capturar_logs` (stdout JSON parseado por línea). | B1, B2 | B3–B8 |
| Q2 | `tests/unit/test_arquitectura.py` (CA14) recorriendo el AST de `app/`. | B1 | B2–B8 |
| Q3 | Casos límite adicionales de `Settings` y `redactar` (§6.1) si faltan tras B2/B3. | B2, B3, Q1 | Q4 |
| Q4 | Pruebas API (§6.2). | B7, Q1 | Q3, Q5 |
| Q5 | `tests/integracion/test_sonda_postgres.py` con testcontainers `postgres:17-alpine` (§6.3). Ejecutar si hay Docker; si no, `--collect-only` y dejarlo reportado como pendiente. | B6, Q1 | Q3, Q4 |
| Q6 | Ejecución y reporte: tabla CA → prueba → resultado, cobertura (CA4), `bandit`, `pip-audit`, `compose config`; defectos con formato `BUG-nn`. | Q1–Q5, B10 | — |

### Seguridad

Sin tareas de implementación en esta épica. La revisión del agente `seguridad` (checklist ASVS/OWASP) sigue siendo la puerta previa al PR según el flujo de `/orquestar`; los puntos a revisar están en §7.

### Orden y paralelismo

```
B1 ─┬─ B2 ─┬─ B6 ─────────────┐
    │      └─ Q1 ─┬─ Q3        │
    ├─ B3 ─┐      │            ├─ B7 ─ B9 ─ B10 ─┐
    ├─ B4 ─┴─ B5 ─┼────────────┘                  ├─ Q6 → seguridad → PR
    ├─ B8 (en paralelo con B2–B7)                 │
    └─ Q2        └─ Q4 (tras B7) · Q5 (tras B6) ──┘
```
- Tras B1: B2, B3, B4, B8 y Q2 en paralelo.
- Tras B2: B6 y Q1 en paralelo con B3/B4/B5.
- Q4 espera a B7; Q5 puede empezar tras B6.

## 6. Pruebas requeridas al terminar

Nombres en español, `test_<sujeto>_<condición>_<resultado>`, una aserción de comportamiento por prueba, sin `sleep`.

**Aviso para quien escriba pruebas:** el hook `proteger-secretos.sh` bloquea literales con forma de JWT, `sk-ant-…` de 20+ caracteres y asignaciones de claves largas sin palabras como `prueba`/`ejemplo`. Construye esos valores en tiempo de ejecución (p. ej. `"sk-ant-" + "x" * 24`, JWT armado con `base64.urlsafe_b64encode`) y usa nombres evidentes (`JWT_SECRET_PRUEBA`). No rodees el hook de ninguna otra forma.

### 6.1 Unitarias (`tests/unit/`)
- `core/test_config.py`
  - producción válida carga sin error; desarrollo sin variables carga con defaults (sin CORS, URL de desarrollo).
  - producción falla (parametrizado, `ids=`): sin `APP_MASTER_KEY`; `APP_MASTER_KEY` no base64; `APP_MASTER_KEY` de 31 y de 33 bytes; sin `JWT_SECRET`; `JWT_SECRET` de 31 bytes; sin `DATABASE_URL`; `DEBUG=true`; `CORS_ORIGENES` vacío; origen `http://` en producción.
  - `CORS_ORIGENES` rechaza `*`, origen con ruta, origen sin esquema; acepta lista separada por comas con espacios.
  - `DATABASE_URL` con esquema distinto de `postgresql+asyncpg://` falla.
  - el texto de `ConfiguracionInvalida` y de la `ValidationError` subyacente **no contiene** el valor secreto probado; `repr(settings)` no contiene secretos.
- `core/test_logging.py`
  - redacción por clave (parametrizado con todas las claves de §4.6), anidada en dict y lista; por valor (Bearer, JWT, `sk-ant-`, `ts_`, DSN con contraseña) dentro de `evento` y dentro de la traza de excepción; email parcial; `SecretStr`; truncado > 2 000.
  - cada línea emitida es JSON con `timestamp`, `nivel`, `evento`; `correlation_id` presente si está en contextvars.
  - un registro de `logging.getLogger("uvicorn.error")` sale como JSON y redactado.
- `application/test_comprobar_preparacion.py`: todas OK ⇒ `listo=True`; una FALLA ⇒ `listo=False` con el mapa correcto; sonda que excede el timeout ⇒ FALLA; sonda que lanza ⇒ FALLA y el mensaje de la excepción no aparece en el informe.
- `api/test_csp.py`: `csp_para` devuelve la CSP estricta para rutas de API y la de documentación solo para `/api/v1/docs` y `/api/v1/redoc`.
- `api/test_errores_mapeo.py`: `NoEncontrado` → 404 `no_encontrado`; `Conflicto` → 409 `conflicto`.
- `api/test_correlacion.py`: `X-Request-ID` UUID válido se propaga; valor no UUID, vacío, de 200 caracteres o con `\r\n` se reemplaza por uno nuevo.
- `test_arquitectura.py`: CA14.

### 6.2 API (`tests/api/`, app ASGI con dependencias falsas)
- `test_salud.py`: liveness 200 y sonda espía sin llamadas; readiness 200 con `SondaFalsa(OK)`; readiness 503 `problem+json` `no_listo` con `SondaFalsa(FALLA)`; readiness con sonda lenta responde en ≤ timeout + 0,5 s (medido con `time.perf_counter`); el cuerpo 503 no contiene `postgres`, `@`, `5432` ni nombre de excepción; `POST /api/v1/salud` → 405 `metodo_no_permitido`.
- `test_errores.py` (con un router **solo de prueba** añadido a la app de prueba): body inválido → 400 `validacion` con `errores[].campo` y sin el valor enviado (se envía un campo `password` con un valor marcador y se verifica que no aparece); ruta que lanza `RuntimeError("marcador-interno")` → 500 `error_interno` sin `marcador-interno` ni `Traceback` en el cuerpo, con `X-Request-ID` y cabeceras de seguridad, y el log contiene la excepción; ruta inexistente → 404 `no_encontrado`; `instance == f"urn:uuid:{X-Request-ID}"`.
- `test_cabeceras.py`: parametrizado por respuesta 200, 404, 405, 400, 500, 503 ⇒ todas las cabeceras de §4.4 y sin cabecera `Server`.
- `test_cors.py`: preflight desde origen permitido ⇒ ACAO = origen, `Allow-Credentials: true`; desde origen ajeno ⇒ sin ACAO; con `cors_origenes=[]` ⇒ sin ACAO para ningún origen.
- `test_docs.py`: producción ⇒ 404 en las seis rutas de CA11; desarrollo ⇒ `/api/v1/openapi.json` 200 y contiene el esquema `Problema`.
- `test_logs_acceso.py`: `GET /api/v1/salud?token=valor-marcador` ⇒ un log `http.peticion` con `ruta="/api/v1/salud"`, `estado=200`, `duracion_ms` numérico, `correlation_id` igual a `X-Request-ID`, y `valor-marcador` ausente de toda la salida.

### 6.3 Integración (`tests/integracion/`, requiere Docker)
- `test_sonda_postgres.py`: con `postgres:17-alpine` ⇒ `SondaPostgres.comprobar()` = OK; con `DATABASE_URL` hacia un puerto cerrado de `127.0.0.1` ⇒ FALLA en ≤ `salud_bd_timeout_s` + 0,5 s; `crear_app` con BD caída arranca y `/salud` responde 200.

## 7. Riesgos de seguridad y mitigaciones

| # | Riesgo | Mitigación en E0.1 |
|---|---|---|
| R1 | Arranque en producción sin claves o con `DEBUG=true` (ASVS V14.1). | Validador de producción + `cargar_settings` fallan cerrado (CA5); la imagen trae `ENV=production` por defecto. |
| R2 | Secretos impresos en errores de validación o en `repr` (ASVS V7.1). | `hide_input_in_errors=True`, `ConfiguracionInvalida` sin valores, `SecretStr` también para `DATABASE_URL` (ADR-0007). |
| R3 | Secretos/PII en logs, incluidas trazas y query strings (ASVS V7.1, LLM06). | Procesador `redactar` tras `format_exc_info`, logs de stdlib por la misma cadena, access log de Uvicorn deshabilitado y log propio sin query string (CA12, CA13). |
| R4 | Fuga de trazas o detalles internos al cliente (ASVS V7.4). | `FastAPI(debug=False)` siempre; `ErroresInesperadosMiddleware`; 400 sin `input`; 503 sin detalles de la dependencia (CA7, CA9). |
| R5 | CORS permisivo con credenciales (ASVS V14.5). | Allowlist validada, `*` rechazado, vacía por defecto, solo `https` en producción (CA10). |
| R6 | Inyección de cabeceras/logs vía `X-Request-ID`. | Solo se acepta UUID válido; si no, se genera uno. |
| R7 | Superficie de información: OpenAPI/Swagger, cabecera `Server`, versión en salud. | Docs a `None` en producción (CA11), `--no-server-header`, respuestas de salud sin versión ni hostname. |
| R8 | IP del cliente falsificable con `X-Forwarded-For` (afecta auditoría y rate limit de E0.3). | `FORWARDED_ALLOW_IPS` restringido (default `127.0.0.1`), fuera `*` en Compose. |
| R9 | `.env.example` desalineado: los agentes de Claude Code no pueden leer ni editar `.env*` (`permissions.deny` en `.claude/settings.json`). | No se rodea el permiso. Las variables se documentan en `backend/README.md`; **acción manual del usuario**: añadir a `.env.example` las variables de §4.3 con valores de ejemplo evidentes. Se deja listado en el reporte de cierre. |
| R10 | Cadena de suministro: imagen de uv sin fijar y fallback que ignora el lockfile. | Versión de uv fijada, `uv sync --locked` sin fallback, `uv.lock` versionado, `pip-audit` (CA16). |
| R11 | Secretos o pruebas copiados a la imagen. | `.dockerignore` en la raíz y `COPY` selectivo de `backend/app`. |
| R12 | DoS barato sobre `/salud/listo` (abre conexión a BD en cada llamada). | Pool acotado (`pool_size=5`, `max_overflow=5`), timeout por sonda, puerto solo en `127.0.0.1`; rate limit general llega en E0.3. Riesgo residual aceptado para Fase 0. |
| R13 | Contaminar el contexto de logs entre peticiones concurrentes. | `bind_contextvars`/`clear_contextvars` por petición en el middleware ASGI; prueba con dos peticiones concurrentes que verifica ids distintos en sus logs. |

Puntos para la revisión del agente `seguridad`: R1–R13, `bandit`, `pip-audit`, lectura del `Dockerfile` y del `docker-compose.yml` resultantes, y confirmación de que no hay `import` de SDKs de IA.

## 8. Definición de terminado de la épica

1. CA1–CA14 y CA16 verificados en este entorno con salida real; CA15 verificado al menos con `compose config -q` y, con Docker disponible, con `compose up`.
2. Pruebas de integración escritas y recolectadas; su ejecución queda registrada como pendiente si no hay Docker.
3. `docs/04-api.md`, `docs/08-observabilidad.md` y `backend/README.md` actualizados (B9); ADR-0007 aceptada.
4. Lista de acciones manuales para el usuario en el reporte de cierre: actualizar `.env.example` (R9).
5. Revisión de `seguridad` sin hallazgos bloqueantes; commits convencionales en `feature/e0-1-esqueleto-backend`.

## 9. Resultado de QA

**Fecha:** 2026-09-28 · **Agente:** qa · Todo reejecutado desde `backend/`, sin confiar en el reporte previo. No se leyó ni editó `.env` ni `.env.example`.

### 9.1 Comandos ejecutados

| Comando | Resultado |
|---|---|
| `uv sync --locked --group dev` | código 0 (`Audited 66 packages`) |
| `uv run ruff check` / `ruff format --check` | `All checks passed!` / `67 files already formatted` |
| `uv run pyrefly check` | `0 errors` |
| `uv run pytest -q -m "not integracion and not e2e and not eval"` | `452 passed, 5 deselected, 1 xfailed` |
| `uv run pytest -m "unit or api" --cov=app --cov-fail-under=85` | `Total coverage: 99.72%` (rama incluida); `app/core/config.py` 100 %, `app/core/logging.py` 99 % (rama 137->139) |
| `uv run bandit -q -r app -ll` | sin hallazgos |
| `uv run pip-audit` | `No known vulnerabilities found` |
| `docker compose -f infra/docker-compose.yml config -q` | código 0 |
| `uv run pytest --collect-only -q -m integracion` | 5 pruebas recolectadas |
| Arranque real `uvicorn --factory app.main:crear_app` con `ENV=development` | 200 en `/api/v1/salud`, 503 `problem+json` en `/salud/listo` sin BD, 200 en `openapi.json`, 405 con `Allow: GET`, logs de stdout JSON, `?token=abc` ausente de los logs |
| Ídem con `ENV=production JWT_SECRET=<corto>` | código de salida 1, una línea JSON `config.invalida` con los campos `DATABASE_URL`, `APP_MASTER_KEY`, `JWT_SECRET`, `CORS_ORIGENES`; el valor del secreto no aparece |

### 9.2 Criterios de aceptación → prueba → resultado

| CA | Prueba principal | Resultado |
|---|---|---|
| CA1 | `uv sync --locked --group dev` | OK |
| CA2 | `tests/unit/test_arquitectura_extra.py::test_lockfile_no_contiene_dependencias_de_ia_ni_de_fases_posteriores` y `test_pyproject_no_declara_dependencias_de_ia` (añadidas por QA; antes solo existía el grep manual) | OK |
| CA3 | ruff, format, pyrefly y pytest rápido de 9.1 | OK |
| CA4 | Cobertura 99,72 % total; `app/core/` 99-100 % | OK |
| CA5 | `tests/unit/core/test_config.py::test_settings_produccion_invalida_falla_en_el_campo` (10 casos) + `tests/unit/core/test_config_limites.py` (clave de 0/1/16/24/31/33/64 bytes, `DEBUG` en cinco formas, `ENV` mal escrito, CORS vacío o solo comas, mensajes sin valores) | OK |
| CA6 | `tests/api/test_salud.py::test_salud_vivo_no_consulta_sondas` | OK |
| CA7 | `tests/api/test_salud.py::test_salud_listo_*`, `test_adversarial.py::test_readiness_con_bd_caida_real_responde_503_sin_detalles_y_a_tiempo` (motor real contra puerto cerrado, verifica ausencia de host, usuario, base y clave en respuesta y logs, y duración ≤ timeout + 0,5 s) | OK sin Docker; la variante con PostgreSQL 17 (`tests/integracion/`) queda **pendiente** |
| CA8 | `tests/api/test_cabeceras.py` (200, 404, 405, 400, 500, 503) + `test_adversarial.py::test_error_lleva_todas_las_cabeceras_de_seguridad` (11 solicitudes) + preflight CORS rechazado | OK |
| CA9 | `tests/api/test_errores.py` + `test_adversarial.py::test_error_es_problem_json_con_instance_igual_al_request_id` (400 por JSON roto, binario y tipos, 404, 405 incl. HEAD, 409, 500) | OK salvo el preflight rechazado (BUG-01) |
| CA10 | `tests/api/test_cors.py`, `test_adversarial.py` (origen con prefijo de la allowlist, métodos exóticos) y `test_config_limites.py` (comodines) | OK |
| CA11 | `tests/api/test_docs.py` (7 rutas en producción) | OK |
| CA12 | `tests/unit/core/test_logging.py`, `test_logging_limites.py` (16 casos), `test_adversarial.py` (JWT, `sk-ant-`, correo, DSN en ruta, excepción y `sqlalchemy`) | OK; ver BUG-04 corregido |
| CA13 | `tests/api/test_logs_acceso.py` + arranque real con `?token=abc` | OK |
| CA14 | `tests/unit/test_arquitectura.py` + `test_arquitectura_extra.py` (importaciones dinámicas de SDKs, `os.environ` solo en `config.py`) | OK |
| CA15 | `compose config -q` código 0; `up -d --build db api` | `config`: OK. `up`: **pendiente** (sin daemon Docker) |
| CA16 | `bandit -ll`, `pip-audit` | OK |

Pruebas de integración con contenedor (`tests/integracion/test_sonda_postgres.py`, 5 pruebas): **pendientes de ejecutar con Docker**. Sin daemon, `pytest -m integracion` falla con `DockerException: Error while fetching server API version` (esperado); no se marcaron `skip`. Las dos pruebas que usan contenedor real son `test_sonda_postgres_con_bd_real_devuelve_ok` y `test_readiness_con_bd_real_responde_200`.

`docs/04-api.md` contiene `metodo_no_permitido` (§12, fila 405, con `Allow`) y `error_interno` (§12, fila 500), además de `X-Request-ID` e `instance`: la discrepancia detectada antes está resuelta.

### 9.3 Pruebas añadidas por QA

| Archivo | Pruebas | Contenido |
|---|---|---|
| `backend/tests/unit/core/test_config_limites.py` | 54 | Límites de `Settings` con entorno real y sin `.env`. |
| `backend/tests/unit/core/test_logging_limites.py` | 16 | Variantes de clave, anidados, bytes, DSN con `@`, query, correo. |
| `backend/tests/unit/test_arquitectura_extra.py` | 95 | CA2, importaciones dinámicas, `os.environ`. |
| `backend/tests/api/test_adversarial.py` | 59 (1 xfail) | `X-Request-ID` hostil (CRLF, 10 000 caracteres, JSON de log, unicode), problem+json y cabeceras en 11 errores, CORS, readiness con BD real caída, redacción de extremo a extremo. |
| `backend/tests/api/test_proceso_uvicorn.py` | 5 (`lento`) | Proceso real `uvicorn --factory` en copia sin `.env`: desarrollo (salud, readiness 503, apagado con SIGINT) y producción (código 1, sin valores, `DEBUG=true`). |

### 9.4 Defectos

| ID | Severidad | Estado | Descripción |
|---|---|---|---|
| BUG-01 | Baja | Abierto, `xfail(strict=True)` | El preflight CORS de un origen ajeno responde `400 text/plain` ("Disallowed CORS origin") en lugar de `problem+json`, contra CA9. Lleva `X-Request-ID` y cabeceras de seguridad. Reproducción: `OPTIONS /api/v1/salud` con `Origin: https://malicioso.ejemplo.net` y `Access-Control-Request-Method: GET`. Origen: `CORSMiddleware` de Starlette montado en `backend/app/main.py` (`_registrar_middlewares`). Arreglo sugerido: subclase de `CORSMiddleware` que convierta el rechazo en `respuesta_problema` con `type="error_http"`, o decidir en el plan que el 400 de preflight queda fuera de CA9. Prueba: `tests/api/test_adversarial.py::test_cors_preflight_rechazado_responde_problem_json`. |
| BUG-02 | Baja | Corregido (trivial) | Una `ExcepcionDominio` sin entrada en `MAPEO_DOMINIO` devolvía 500 sin dejar rastro en el log. Se añade `_log.error("http.excepcion_dominio_sin_mapeo", tipo_error=...)` en `backend/app/api/errores.py` (`describir_excepcion_dominio`). Prueba: `test_dominio_sin_mapeo_deja_rastro_en_el_log`. |
| BUG-03 | Baja | Corregido (trivial) | `CORS_ORIGENES` aceptaba `https://a.com:abc`, `https://a.com:99999` y `HTTPS://A.com`; los dos primeros son inválidos y el tercero nunca coincide con el `Origin` del navegador (silenciosamente sin CORS en producción). Se añadió la validación de puerto y de minúsculas en `_validar_origen` (`backend/app/core/config.py`). Prueba: `test_cors_origen_mal_formado_o_que_nunca_coincidiria_falla` (10 casos). |
| BUG-04 | Media | Corregido (trivial) | La redacción de DSN dejaba visible parte de la contraseña si contenía `@` sin codificar: `postgresql://u:pa@ss-secreta@host/db` salía como `postgresql://u:***@ss-secreta@host/db`. Se cambió el patrón a `[^\s/]+@` en `backend/app/core/logging.py:51`. Prueba: `test_redactar_dsn_con_contrasena_que_contiene_arroba_no_deja_resto_visible`. |

### 9.5 Observaciones sin defecto (para decisión)

- `JWT_SECRET` de 32 espacios pasa la validación (solo se exige longitud). Entropía mínima queda para E0.3, cuando exista el uso real.
- `HEAD /api/v1/salud` responde 405; los sondeos de Compose y del Dockerfile usan GET. Si algún balanceador usa HEAD habrá que declarar el método.
- `DEBUG=true` en desarrollo sube el nivel raíz a DEBUG, lo que también activa los logs de `sqlalchemy` con parámetros; pasan por la redacción, pero conviene revisarlo al añadir modelos en E0.2.
- La puerta de `proteger-secretos.sh` no bloqueó ninguna prueba; los JWT y claves se arman en tiempo de ejecución.
- Sin `.env`, el proceso de producción termina con código 1; con el árbol real, `Settings` leería `RAIZ_REPO/.env` si existiera (las pruebas de proceso usan una copia de `app/` para evitarlo).
