# Backend · Agente Correo

FastAPI + SQLAlchemy async + PostgreSQL con arquitectura hexagonal (`docs/01-arquitectura.md` §3). Stack y versiones en `docs/02-stack-tecnologico.md`. Configuración y fallo cerrado en `docs/adr/0007-configuracion-validada-y-fallo-cerrado.md`.

## Arranque local

```
cd backend
uv sync --locked --group dev                 # Python 3.12 (.python-version)
make -C .. db                                # PostgreSQL 17 en Docker (127.0.0.1:5432)
uv run python -m app.bootstrap               # o `make -C .. bootstrap`: crea, migra y siembra
uv run uvicorn --factory app.main:crear_app --reload --no-server-header --no-access-log
```

La app se crea con la fábrica `app.main:crear_app` (siempre `--factory`); importar `app.main` no lee el entorno ni abre conexiones. La API arranca aunque la base de datos esté caída: `/api/v1/salud` responde 200 y `/api/v1/salud/listo` 503 hasta que la BD responda **y** esté en la revisión `head` de Alembic (comprobación `migraciones`). La API no ejecuta DDL ni semillas: eso es trabajo del bootstrap.

## Bootstrap de la base de datos (ADR-0004, ADR-0008, ADR-0010)

`python -m app.bootstrap` es idempotente y seguro con varios procesos a la vez. En Compose lo ejecuta el servicio one-shot `migrador`; `api` arranca cuando termina bien. Pasos:

1. Espera a PostgreSQL (backoff 0,5 → 5 s, hasta `DB_ESPERA_MAX_S`). Una credencial rechazada falla de inmediato.
2. Crea la base si no existe y `DB_AUTO_CREATE=true` (prohibido en producción). El nombre debe cumplir `^[A-Za-z_][A-Za-z0-9_]{0,62}$`.
3. Toma `pg_try_advisory_lock(0xA6E17E)` hasta `DB_BOOTSTRAP_LOCK_TIMEOUT_S`.
4. `alembic upgrade head` programático con psycopg: extensiones, esquemas `procrastinate` y `langgraph`, tablas propias y el SQL versionado de procrastinate 3.10.0 (`alembic/sql/procrastinate/`).
5. `AsyncPostgresSaver.setup()` en el esquema `langgraph` y privilegios del rol de aplicación.
6. Con `DB_ROLES_SEPARADOS=true`, verifica que el rol de `DATABASE_URL` no es superusuario, no tiene `CREATEROLE`/`CREATEDB`/`BYPASSRLS`, ni `CREATE` en la base o en `public`/`langgraph`/`procrastinate`, no es propietario de tablas ni tiene `UPDATE`/`DELETE`/`TRUNCATE` sobre `auditoria`, y que el migrador no es superusuario. Si algo falla, termina con código 2 y la lista de comprobaciones (`bootstrap.privilegios_inseguros`). En rol único avisa con `bd.rol_unico`.
7. Siembra roles, proveedores (deshabilitados), taxonomía base, agentes con su prompt v1 publicado, configuración y el admin inicial si no hay usuarios, con auditoría (`bd.migrada`, `bd.semillas_aplicadas`, `usuario.admin_inicial_creado`) en la misma transacción.

Códigos de salida: `0` correcto, `1` configuración inválida (`config.invalida`), `2` fallo (`bootstrap.fallido` con `paso`, `tipo_error` y `sqlstate`, más el evento específico: `bootstrap.bd_no_disponible`, `bootstrap.autenticacion_rechazada`, `bootstrap.base_inexistente`, `bootstrap.nombre_base_invalido`, `bootstrap.lock_timeout`, `bootstrap.falta_url_migrador`, `bootstrap.privilegios_inseguros`, `bootstrap.admin_sin_email`). Ningún log incluye URL, usuario ni contraseña de la BD.

**Admin inicial.** Si `usuarios` está vacía se crea `ADMIN_INITIAL_EMAIL` (fuera de producción, `admin@agente-correo.local`) con rol `admin`, hash Argon2id (m=65536, t=3, p=4) y `requiere_cambio_password=true`. Sin `ADMIN_INITIAL_PASSWORD` se genera una contraseña aleatoria de 24 caracteres que se escribe **una sola vez** en `stderr`, fuera del log JSON, después del `COMMIT`. En producción conviene definir `ADMIN_INITIAL_PASSWORD` desde un gestor de secretos.

**Roles separados.** `infra/sql/roles.sql` (idempotente) crea `agente_migrador`, `agente_app` y `agente_lectura`; `infra/sql/00-roles.sh` lo aplica y asigna contraseñas desde `AGENTE_MIGRADOR_PASSWORD`/`AGENTE_APP_PASSWORD` al inicializar el volumen de `db`. Con un volumen de E0.1 ya existente: `make db-roles` una vez. El bootstrap no crea roles ni asigna contraseñas.

**Migraciones nuevas.** `uv run alembic revision --autogenerate -m "..."` (usa `alembic.ini`, solo CLI; la URL sale de `DATABASE_URL_MIGRADOR` o `DATABASE_URL`). Revisa a mano, escribe un `downgrade` real y llama a `conceder_privilegios_app(<esquema>)` al final de cada revisión que cree tablas. Subir procrastinate obliga a copiar su SQL de migración y añadir una revisión (lo exige `tests/unit/infrastructure/test_alembic_estructura.py`).

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
| `DATABASE_URL_MIGRADOR` | solo en el servicio `migrador` | — (rol único: usa `DATABASE_URL`) | `postgresql+asyncpg://agente_migrador:<contraseña>@db:5432/agente_correo` | Esquema `postgresql+asyncpg://`. Obligatoria si `DB_ROLES_SEPARADOS=true`; nunca en `api`/`worker` (Compose la anula con cadena vacía, que equivale a no definirla). |
| `DB_AUTO_CREATE` | debe ser `false` | `false` | `true` (solo desarrollo) | El bootstrap crea la base si falta. |
| `DB_ROLES_SEPARADOS` | debe ser `true` | `false` | `true` | Migrador y aplicación con roles distintos y verificación de privilegios. |
| `DB_ESPERA_MAX_S` | — | `60` | `60` | Espera máxima a PostgreSQL; `0 < t ≤ 600`. |
| `DB_BOOTSTRAP_LOCK_TIMEOUT_S` | — | `120` | `120` | Espera máxima por el advisory lock; `0 < t ≤ 1800`. |
| `ADMIN_INITIAL_EMAIL` | sí, si no hay usuarios | `admin@agente-correo.local` fuera de producción | `admin@ejemplo.com` | Se normaliza a minúsculas; ≤ 254 caracteres; sin espacios ni saltos de línea. |
| `ADMIN_INITIAL_PASSWORD` | recomendable | — (se genera y se muestra una vez) | `<definir en el gestor de secretos>` | 12–128 caracteres; solo se usa en el primer bootstrap. |

Variables de Compose (interpolación, no las lee `Settings`): `POSTGRES_PASSWORD`, `AGENTE_MIGRADOR_PASSWORD` y `AGENTE_APP_PASSWORD` son obligatorias en `infra/docker-compose.yml`; los objetivos de desarrollo del `Makefile` aportan valores locales evidentes si no están definidas. `PRUEBAS_PG_DSN` solo la usan las pruebas de integración. Compose interpola las contraseñas de los roles dentro de `DATABASE_URL` y `DATABASE_URL_MIGRADOR` sin codificarlas: usa contraseñas URL-seguras (letras, dígitos, `-`, `_`; por ejemplo `python -c "import secrets; print(secrets.token_urlsafe(24))"`). Un `%` seguido de dos dígitos hexadecimales se decodifica y cambia la contraseña sin aviso, y un espacio o un salto de línea invalidan la URL.

`langgraph-checkpoint-postgres` arrastra `langchain-core` y `langsmith`; LangSmith queda inactivo (no se define `LANGSMITH_TRACING` ni claves de LangSmith).

Generar claves para tu `.env` local (no se versiona):

```
make keys        # imprime APP_MASTER_KEY=... y JWT_SECRET=...
```

Con `ENV=production` el proceso no arranca si falta o es inválida cualquiera de `APP_MASTER_KEY`, `JWT_SECRET`, `DATABASE_URL`, `CORS_ORIGENES`, si `DEBUG=true`, si `DB_AUTO_CREATE=true` o si `DB_ROLES_SEPARADOS=false`: registra un log JSON `config.invalida` con los campos y termina con código 1.

## Estructura

```
app/
├── core/            config.py (Settings), logging.py (JSON + redacción), ids.py (UUID v7)
├── domain/          errores.py, auditoria.py, catalogo_inicial.py, agentes/preguntas.py
├── application/     ports/ (salud, auditoria, usuarios, seguridad, avisos), use_cases/, policies/
├── infrastructure/  db/ (motor, sondas, modelos/, repositorios/, semillas, bootstrap/),
│                    seguridad/argon2.py, avisos/stderr.py (único escritor directo de stderr)
├── api/             routers/, schemas/, middleware/, errores.py, dependencias.py, openapi.py
├── agents/prompts/  prompts v1 (*.md) sembrados en versiones_prompt   providers/ (E1.1)
├── bootstrap.py     `python -m app.bootstrap` (composition root del bootstrap)
└── main.py          crear_app()
alembic/             env.py, versions/ (0001–0004), sql/procrastinate/<versión>_schema.sql
tests/
├── unit/            sin E/S (marcador `unit`)
├── api/             app ASGI con httpx y dependencias falsas (marcador `api`)
└── integracion/     PostgreSQL efímero (ADR-0011) (marcador `integracion`)
```

`tests/conftest.py` asigna el marcador por directorio y falla la colección si una prueba queda fuera de esos directorios.

## Calidad

```
uv run ruff check . && uv run ruff format --check . && uv run pyrefly check
uv run pytest -q -m "not integracion and not e2e and not eval"
uv run pytest -m "unit or api" --cov=app --cov-report=term-missing --cov-fail-under=85
uv run pytest -q -m integracion          # o `make -C .. test-int`; PostgreSQL efímero (ADR-0011)
uv run bandit -q -r app -ll && uv run pip-audit
```

**Integración.** La fixture `postgres_efimero` (`tests/integracion/pg_efimero.py`) usa, en este orden: `PRUEBAS_PG_DSN` (servidor desechable; crea y borra bases `prueba_*` y roles `agente_*`), Docker con testcontainers (`postgres:17-alpine`) o un clúster temporal con los binarios locales (`initdb`/`pg_ctl`, `runuser -u postgres` si corre como root, solo `127.0.0.1`, `scram-sha-256`, contraseña aleatoria, directorio de `mkdtemp` que se borra al terminar). Si no hay ninguno, la sesión falla; nunca se omiten pruebas.

Dependencias: siempre `uv add` (nunca `pip install`); `uv.lock` se versiona y la imagen usa `uv sync --locked`.
