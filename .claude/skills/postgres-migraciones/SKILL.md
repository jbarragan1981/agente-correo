---
name: postgres-migraciones
description: >-
  Modelado, migraciones Alembic y bootstrap automático de PostgreSQL en Agente Correo: modelos SQLAlchemy 2, convenciones de nombres, migraciones reversibles y seguras en producción, creación automática de la base al arrancar, advisory lock, semillas idempotentes, esquema de procrastinate y del checkpointer de LangGraph, índices, vistas materializadas, retención y roles de BD. Úsalo al tocar backend/app/infrastructure/db o alembic/.
---

# PostgreSQL · modelos, migraciones y bootstrap

Referencia: `docs/03-modelo-de-datos.md`, ADR-0004.

## Modelos SQLAlchemy 2
- `infrastructure/db/modelos/<dominio>.py`, `DeclarativeBase` con `MetaData(naming_convention=...)` (ix/uq/ck/fk/pk con nombres deterministas).
- `Mapped[...]` + `mapped_column`; `uuid` PK generado en app (uuid v7); `creado_en`/`actualizado_en` con `server_default=func.now()` y `onupdate`.
- JSONB para payloads validados por Pydantic; `citext` para emails; `tsvector` generado para búsqueda.
- Columnas de secretos: `secreto_cifrado LargeBinary`, `clave_datos_cifrada LargeBinary`, `nonce LargeBinary`, `version_clave_maestra Integer`.
- Enumerados de estado como `String` con `CheckConstraint` (más fácil de migrar que `ENUM` nativo).

## Migraciones Alembic
```
cd backend && uv run alembic revision --autogenerate -m "crear cuentas_correo"
```
Después de generar: revisar a mano (autogenerate no detecta todo), añadir índices concurrentes si la tabla es grande (`op.create_index(..., postgresql_concurrently=True)` con `op.get_context().autocommit_block()`), escribir `downgrade` real y probar `upgrade head && downgrade -1 && upgrade head` contra un contenedor limpio (`make db-test`).
Reglas para producción: sin `DROP COLUMN` en la misma versión que deja de usarse (expandir → migrar datos → contraer); `NOT NULL` en dos pasos con `DEFAULT`; sin bloqueos largos (evitar `ALTER TYPE`); migraciones de datos en lotes con `SKIP LOCKED`.

## Bootstrap automático (`infrastructure/db/bootstrap.py`)
```python
async def bootstrap_base_de_datos(s: Settings) -> None:
    await esperar_postgres(s.database_url, max_s=60)                 # backoff exponencial
    if s.db_auto_create and not await existe_base(s): await crear_base(s)   # conecta a 'postgres', CREATE DATABASE + extensiones
    async with conexion_admin(s) as conn:
        await conn.execute(text("SELECT pg_advisory_lock(0xA6E17E)"))
        try:
            await ejecutar_alembic_upgrade(s)                          # alembic.command.upgrade en hilo
            await aplicar_esquema_procrastinate(s)                     # app.schema_manager.apply_schema() si falta
            await AsyncPostgresSaver.from_conn_string(s.database_url_langgraph).setup()  # esquema langgraph
            await sembrar_datos_iniciales(s)                          # idempotente (ON CONFLICT DO NOTHING)
        finally:
            await conn.execute(text("SELECT pg_advisory_unlock(0xA6E17E)"))
```
Semillas: roles; admin inicial (`ADMIN_INITIAL_EMAIL`, `ADMIN_INITIAL_PASSWORD` o contraseña aleatoria mostrada una vez en logs con aviso); proveedores (deshabilitados hasta cargar credencial); taxonomía base; agentes por defecto con `versiones_prompt` v1 desde `agents/prompts/*.md` y `preguntas_jev` generadas; `configuracion` con valores por defecto. Readiness (`/salud/listo`) comprueba `alembic current == head`.

## Cola (procrastinate)
`infrastructure/cola/app.py`: `App(connector=PsycopgConnector(conninfo=...))`; tareas `procesar_mensaje`, `sincronizar_cuenta`, `refrescar_metricas` (periódica `*/5 * * * *`), `aplicar_retencion` (diaria), `enviar_borrador`. Colas separadas: `correo`, `ia`, `mantenimiento` con concurrencias configurables. Reintentos `retry=RetryStrategy(max_attempts=5, exponential_wait=2)`. Idempotencia por `queueing_lock=f"mensaje:{id}"`.

## Índices y vistas
Los de `docs/03-modelo-de-datos.md` §4. `mv_metricas_diarias` con `REFRESH MATERIALIZED VIEW CONCURRENTLY` (requiere índice único). Consultas del dashboard en `infrastructure/db/consultas/metricas.py` con `text()` parametrizado y pruebas de integración.

## Retención y borrado
Tarea diaria que anonimiza según `configuracion.retencion_dias_mensajes`; borrado de cuenta en una transacción con `ON DELETE CASCADE` declarado en FKs + limpieza de checkpoints por `thread_id` + auditoría.

## Roles de BD (producción)
`DB_ROLES_SEPARADOS=true`: `agente_migrador` (DDL, solo en bootstrap) y `agente_app` (DML; `auditoria` solo INSERT; sin `TRUNCATE`). Script `infra/sql/roles.sql` idempotente aplicado en bootstrap.

## Pruebas
`tests/integracion/test_migraciones.py`: contenedor PostgreSQL 17 limpio → `bootstrap` → todas las tablas esperadas → `downgrade base` sin errores → segundo `bootstrap` no falla (idempotencia) → dos procesos concurrentes (lock) sin error.
