# ADR-0004 · PostgreSQL como única dependencia con bootstrap automático

**Estado:** Aceptada · 2026-09-28 · Refinada por ADR-0008 (bootstrap como comando dedicado y roles) y ADR-0010 (esquemas de librerías)

## Contexto
Requisito: "la base de datos se crea sola la primera vez al instanciar". Se busca el menor número de piezas de infraestructura para instalaciones on-premise y en nube.

## Decisión
- PostgreSQL 17 aloja datos, cola de trabajos (`procrastinate`, `SKIP LOCKED` + `LISTEN/NOTIFY`), checkpoints de LangGraph y auditoría.
- Al arrancar, la aplicación: espera la BD, crea la base si no existe (`DB_AUTO_CREATE`), toma `pg_advisory_lock`, ejecuta `alembic upgrade head` programático, aplica el esquema de procrastinate y del checkpointer, siembra datos idempotentes, libera el lock.
- Redis/arq se reservan como camino de escala detrás del puerto `JobQueuePort`.

## Consecuencias
- (+) `docker compose up` es suficiente; sin scripts manuales.
- (+) Un solo respaldo y un solo punto de cifrado en reposo.
- (−) La BD concentra carga OLTP + cola; se mitiga con índices, vistas materializadas y particionado (Fase 2).
- (−) El bootstrap con DDL requiere privilegios al arrancar; en producción se separa `agente_migrador` de `agente_app` (`DB_ROLES_SEPARADOS=true`).
