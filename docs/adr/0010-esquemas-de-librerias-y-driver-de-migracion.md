# ADR-0010 · Esquemas de procrastinate y LangGraph, y driver psycopg para el bootstrap

**Estado:** Aceptada · 2026-09-28 · Épica E0.2

## Contexto
El bootstrap debe aplicar el esquema de procrastinate (cola) y el del checkpointer de LangGraph además de las migraciones propias. Pruebas hechas por el arquitecto el 2026-09-28 contra PostgreSQL 16.13 local:

1. `procrastinate.schema.SchemaManager.get_schema()` (3.10.0) devuelve un script multi-sentencia sin referencias a `public.`; aplicado con `search_path=procrastinate` crea todo en ese esquema.
2. Ese script **falla** con SQLAlchemy + asyncpg (`cannot insert multiple commands into a prepared statement`) y con `exec_driver_sql` de psycopg (interpreta `%` como marcador). Funciona con el cursor DBAPI de psycopg sin parámetros, tanto con motor síncrono como asíncrono vía `run_sync`.
3. `AsyncPostgresSaver.setup()` (langgraph-checkpoint-postgres 3.1.2) es idempotente y, con `options=-c search_path=langgraph`, crea `checkpoints`, `checkpoint_blobs`, `checkpoint_writes` y `checkpoint_migrations` en ese esquema.
4. `uv pip compile` resolvió `langchain-core 0.3.76` junto a `langgraph-checkpoint 4.2.0`, combinación que falla al importar (`Reviver.__init__() got an unexpected keyword argument 'allowed_objects'`). Con `langchain-core>=1` funciona.

## Decisión
- **Esquemas:** `public` para tablas propias, `procrastinate` para la cola y `langgraph` para checkpoints. La migración inicial crea ambos esquemas (`CREATE SCHEMA IF NOT EXISTS`).
- **procrastinate versionado por Alembic:** el SQL de `procrastinate 3.10.0` se copia a `backend/alembic/sql/procrastinate/3.10.0_schema.sql` y lo aplica una revisión Alembic con `SET LOCAL search_path = procrastinate` y el cursor DBAPI. Su `downgrade` es `DROP SCHEMA procrastinate CASCADE` seguido de `CREATE SCHEMA procrastinate` (el esquema lo gestiona la revisión inicial). Una prueba unitaria compara la versión instalada de procrastinate con la última versión copiada: subir procrastinate obliga a añadir una revisión con sus scripts de `procrastinate/sql/migrations/`. El conector de la cola (E1.3) fija `search_path=procrastinate`.
- **Privilegios explícitos, sin depender de privilegios por defecto en esquemas de librerías:** al final de cada revisión, y tras `setup()` de LangGraph, se ejecuta el mismo bloque idempotente `conceder_privilegios_app(esquema)` (`GRANT USAGE ON SCHEMA`, `SELECT, INSERT, UPDATE, DELETE ON ALL TABLES`, `USAGE, SELECT ON ALL SEQUENCES`, `EXECUTE ON ALL FUNCTIONS` a `agente_app` y `SELECT` a `agente_lectura`, solo si los roles existen), seguido del `REVOKE` de `auditoria`. Así el `DROP SCHEMA ... CASCADE` de un `downgrade` no pierde privilegios al volver a subir.
- **LangGraph fuera de Alembic:** el bootstrap ejecuta `AsyncPostgresSaver.setup()` en cada arranque, conectado como migrador con `search_path=langgraph`; la librería gestiona sus propias versiones en `langgraph.checkpoint_migrations`. La aplicación (E1.4) nunca llama a `setup()`.
- **Driver del bootstrap:** migraciones, semillas y verificaciones del bootstrap usan `postgresql+psycopg` (asíncrono). La API mantiene `postgresql+asyncpg` (E0.1). La URL del bootstrap se deriva de la configurada cambiando solo el driver (`make_url(...).set(drivername="postgresql+psycopg")`), sin registrar la URL.
- **Dependencias fijadas:** `alembic>=1.20,<1.21`, `psycopg[binary]>=3.3,<3.4`, `procrastinate>=3.10,<3.11`, `langgraph-checkpoint-postgres>=3.1,<3.2`, `langchain-core>=1.6,<2` (restricción explícita que evita la resolución rota), `uuid-utils>=0.12,<1.0` (UUID v7 en Python 3.12; uuid-utils 1.x rompe el checkpointer de LangGraph, por eso el tope `<1.0`; el lock resuelve 0.17.1), `argon2-cffi>=25.1`. Desviación registrada por QA el 2026-09-28: el borrador de esta ADR decía `langchain-core>=1.0` y `uuid-utils>=1.0`; el backend fijó los rangos anteriores al implementar.

## Alternativas consideradas
- **`SchemaManager.apply_schema_async()` en cada arranque fuera de Alembic:** solo sirve para bases vacías; las actualizaciones de procrastinate quedarían sin versionar y `alembic current == head` no reflejaría el estado real. Descartada.
- **Leer el SQL desde el paquete instalado dentro de la migración:** tras subir procrastinate, una base nueva aplicaría el esquema nuevo y luego las migraciones posteriores fallarían. Descartada: se copia el SQL.
- **Todo en `public`:** el `downgrade` necesitaría enumerar decenas de funciones, tipos y triggers de procrastinate. Descartada.
- **Migrar toda la app a psycopg ahora:** cambia contratos de E0.1 (validador de `DATABASE_URL`, motor) sin requisito que lo pida. Se reevalúa en E1.3, cuando procrastinate use psycopg en tiempo de ejecución.

## Consecuencias
- (+) El estado completo de la BD propia y de la cola lo describe `alembic_version`, que usa la sonda de readiness.
- (+) `downgrade base` es limpio y verificable en pruebas.
- (−) Dos drivers PostgreSQL en el lockfile (asyncpg y psycopg).
- (−) `langgraph-checkpoint-postgres` arrastra `langchain-core` y `langsmith` desde E0.2; `langsmith` no se activa (sin `LANGSMITH_TRACING` ni claves) y se documenta en `backend/README.md`. `langsmith` se subió a 0.14.1 en el lock por un CVE de la versión anterior (`pip-audit` sin hallazgos con 0.14.1).
