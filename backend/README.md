# Backend · Agente Correo

FastAPI + SQLAlchemy async + PostgreSQL con arquitectura hexagonal (`docs/01-arquitectura.md` §3). Stack y versiones en `docs/02-stack-tecnologico.md`. Configuración y fallo cerrado en `docs/adr/0007-configuracion-validada-y-fallo-cerrado.md`.

## Arranque local

```
cd backend
uv sync --locked --group dev                 # Python 3.12 (.python-version)
make -C .. db                                # PostgreSQL 17 en Docker (opcional para /salud)
uv run uvicorn --factory app.main:crear_app --reload --no-server-header --no-access-log
```

La app se crea con la fábrica `app.main:crear_app` (siempre `--factory`); importar `app.main` no lee el entorno ni abre conexiones. La API arranca aunque la base de datos esté caída: `/api/v1/salud` responde 200 y `/api/v1/salud/listo` 503 hasta que la BD responda.

Documentación interactiva (solo fuera de producción): `http://localhost:8000/api/v1/docs`, `/api/v1/redoc`, `/api/v1/openapi.json`.

## Variables de entorno

`Settings` (`app/core/config.py`) es el único lector del entorno. Lee variables de proceso y, si existe, el `.env` de la raíz del repo; ignora claves que no conoce (el `.env` es compartido con Compose y épicas futuras). Los errores nombran la variable y nunca muestran su valor.

| Variable | Obligatoria en producción | Valor por defecto | Ejemplo evidente | Regla |
|---|---|---|---|---|
| `ENV` | — | `development` (la imagen Docker usa `production`) | `development` | `development`, `test` o `production`. |
| `DEBUG` | debe ser `false` | `false` | `false` | Solo sube el nivel de log a `DEBUG`; la app se construye siempre con `FastAPI(debug=False)`. |
| `LOG_LEVEL` | — | `INFO` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `DATABASE_URL` | sí | `postgresql+asyncpg://postgres:postgres@localhost:5432/agente_correo` fuera de producción | `postgresql+asyncpg://usuario:<contraseña>@db:5432/agente_correo` | Esquema `postgresql+asyncpg://`. Se trata como secreto. |
| `APP_MASTER_KEY` | sí | — | salida de `make keys` | Base64 estricto que decodifica a 32 bytes exactos. |
| `JWT_SECRET` | sí | — | salida de `make keys` | Al menos 32 bytes UTF-8. |
| `CORS_ORIGENES` | sí (no vacía, solo `https`) | vacía (sin CORS) | `https://panel.ejemplo.com,https://www.ejemplo.com` | Lista separada por comas de `scheme://host[:puerto]`; sin `*`, ruta, query ni credenciales. |
| `SALUD_BD_TIMEOUT_S` | — | `2.0` | `2.0` | Timeout por sonda de `/salud/listo` y de conexión a la BD; `0 < t ≤ 10`. |
| `FORWARDED_ALLOW_IPS` | recomendable | `127.0.0.1` (imagen y Compose) | `10.0.0.5` | La lee Uvicorn (no `Settings`): IP/CIDR del reverse proxy cuyo `X-Forwarded-For` se acepta. Nunca `*`. |

Generar claves para tu `.env` local (no se versiona):

```
make keys        # imprime APP_MASTER_KEY=... y JWT_SECRET=...
```

Con `ENV=production` el proceso no arranca si falta o es inválida cualquiera de `APP_MASTER_KEY`, `JWT_SECRET`, `DATABASE_URL`, `CORS_ORIGENES`, o si `DEBUG=true`: registra un log JSON `config.invalida` con los campos y termina con código 1.

## Estructura

```
app/
├── core/            config.py (Settings), logging.py (JSON + redacción)
├── domain/          errores.py (ExcepcionDominio, NoEncontrado, Conflicto)
├── application/     ports/salud.py, use_cases/comprobar_preparacion.py, policies/
├── infrastructure/  db/motor.py, db/sonda_postgres.py
├── api/             routers/, schemas/, middleware/, errores.py, dependencias.py, openapi.py
├── agents/          (E1.4)   providers/ (E1.1)
└── main.py          crear_app()
tests/
├── unit/            sin E/S (marcador `unit`)
├── api/             app ASGI con httpx y dependencias falsas (marcador `api`)
└── integracion/     PostgreSQL 17 con testcontainers; requiere Docker (marcador `integracion`)
```

`tests/conftest.py` asigna el marcador por directorio y falla la colección si una prueba queda fuera de esos directorios.

## Calidad

```
uv run ruff check . && uv run ruff format --check . && uv run pyrefly check
uv run pytest -q -m "not integracion and not e2e and not eval"
uv run pytest -m "unit or api" --cov=app --cov-report=term-missing --cov-fail-under=85
uv run pytest -q -m integracion          # requiere Docker
uv run bandit -q -r app -ll && uv run pip-audit
```

Dependencias: siempre `uv add` (nunca `pip install`); `uv.lock` se versiona y la imagen usa `uv sync --locked`.
