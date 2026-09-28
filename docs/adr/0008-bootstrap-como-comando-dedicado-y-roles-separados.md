# ADR-0008 · Bootstrap de BD como comando dedicado con roles separados

**Estado:** Aceptada · 2026-09-28 · Épica E0.2 · Refina ADR-0004

## Contexto
ADR-0004 fija que "al arrancar" la aplicación crea la base, toma un advisory lock, migra, aplica los esquemas de procrastinate y LangGraph y siembra datos. Al diseñar E0.2 aparecen cuatro tensiones:

1. Si el bootstrap corre dentro del `lifespan` de la API, el proceso que atiende peticiones necesita privilegios DDL (propietario de tablas o superusuario). La revisión de seguridad de E0.1 (observación B6) exige que la aplicación no se conecte como superusuario en producción.
2. E0.1 decidió que la API arranca aunque la BD esté caída (liveness 200, readiness 503). Un bootstrap en el `lifespan` bloquearía el arranque hasta 60 s y lo haría fallar.
3. `DB_AUTO_CREATE` necesita conectarse a la base de mantenimiento `postgres` con `CREATEDB`: en producción es un privilegio que la aplicación no debe tener (B6).
4. El servicio `db` de Compose publica `127.0.0.1:5432` con `postgres/postgres` por defecto (observación M1).

## Decisión
- **Comando dedicado.** El bootstrap es un comando idempotente `python -m app.bootstrap` (composition root en `app/bootstrap.py`, orquestación en `app/infrastructure/db/bootstrap/`). Códigos de salida: `0` correcto, `1` configuración inválida, `2` fallo de bootstrap. La API **no** ejecuta DDL ni semillas; su `lifespan` solo crea el motor.
- **Compose.** Nuevo servicio one-shot `migrador` (misma imagen, `command: ["python","-m","app.bootstrap"]`, `restart: "no"`). `api` (y `worker` en E1.3) dependen de él con `condition: service_completed_successfully`. `docker compose up` sigue siendo suficiente (hito M0).
- **Roles.** Con `DB_ROLES_SEPARADOS=true`:
  - `migrador` se conecta con `DATABASE_URL_MIGRADOR` (rol `agente_migrador`: propietario del esquema, `CREATE` en la base, sin `SUPERUSER`, `CREATEROLE` ni `CREATEDB`).
  - `api` y `worker` se conectan con `DATABASE_URL` (rol `agente_app`: DML por privilegios por defecto, `INSERT`/`SELECT` en `auditoria`, sin DDL).
  - `DATABASE_URL_MIGRADOR` solo se entrega al servicio `migrador`; la API nunca la recibe.
  - Los roles los crea el DBA (o el script de inicialización del contenedor `db`) con `infra/sql/roles.sql`; el bootstrap no crea roles ni asigna contraseñas.
  - El bootstrap **verifica** (falla cerrado, código 2) que el rol de `DATABASE_URL` no es superusuario, no tiene `CREATEROLE`/`CREATEDB`/`BYPASSRLS`, no tiene `CREATE` en la base ni en los esquemas `public`, `langgraph` y `procrastinate`, no es propietario de tablas y no tiene `UPDATE`/`DELETE`/`TRUNCATE` sobre `auditoria`; y que el rol migrador no es superusuario.
- **Fallo cerrado en producción** (validador de `Settings`, ADR-0007): con `ENV=production`, `DB_AUTO_CREATE=true` se rechaza y `DB_ROLES_SEPARADOS` debe ser `true`.
- **Modo de rol único** (solo `development`/`test`, `DB_ROLES_SEPARADOS=false`): el bootstrap usa `DATABASE_URL` para todo y emite el aviso `bd.rol_unico`.
- **Lock.** `pg_try_advisory_lock(0xA6E17E)` en bucle con backoff hasta `DB_BOOTSTRAP_LOCK_TIMEOUT_S`; el lock se mantiene en una conexión dedicada durante todos los pasos y se libera en `finally`. Las migraciones fijan `lock_timeout` de 30 s por sentencia para no bloquear indefinidamente a una API en marcha.
- **Admin inicial.** Solo se crea si `usuarios` está vacía. Si no se define `ADMIN_INITIAL_PASSWORD`, se genera una contraseña aleatoria (`secrets.token_urlsafe(18)`) que se escribe **una sola vez** directamente en `stderr` en un bloque fijo, fuera de structlog; el evento estructurado `bootstrap.admin_inicial_creado` solo lleva `generada_aleatoriamente: true` (nombre elegido para que la redacción por subcadena no oculte el booleano). El usuario queda con `requiere_cambio_password=true` (E0.3 obliga a cambiarla en el primer login). En `ENV=production` sin usuarios y sin `ADMIN_INITIAL_EMAIL`, el bootstrap falla cerrado.
- **Compose sin puerto de BD (M1).** `infra/docker-compose.yml` es la configuración con postura de producción: `db` sin `ports`, `POSTGRES_PASSWORD`, `AGENTE_MIGRADOR_PASSWORD` y `AGENTE_APP_PASSWORD` obligatorias (`${VAR:?}`). `infra/docker-compose.dev.yml` añade el puerto `127.0.0.1:5432` y `DB_AUTO_CREATE=true`; el `Makefile` lo incluye en los objetivos de desarrollo y aporta contraseñas locales evidentes solo si no están definidas.

## Alternativas consideradas
- **Bootstrap en el `lifespan` de la API** (lectura literal de ADR-0004): obliga a dar DDL al proceso expuesto y rompe "la API arranca con la BD caída". Descartada.
- **Bootstrap en `lifespan` con dos motores (migrador y app)**: la API seguiría recibiendo credenciales DDL. Descartada.
- **Crear roles y contraseñas desde el bootstrap**: exige conectarse como superusuario en cada arranque. Descartada; se hace una vez en la inicialización de la BD.
- **Contraseña del admin inicial en el log estructurado**: la redacción la ocultaría (clave `contrasena`) o, si se desactiva, quedaría indexada en el agregador de logs con metadatos. Se usa `stderr` directo, una sola vez, más cambio obligatorio.

## Consecuencias
- (+) El proceso expuesto nunca tiene privilegios DDL en producción; la auditoría es inmutable para él a nivel de permisos.
- (+) `docker compose up` sigue creando, migrando y sembrando sin pasos manuales.
- (+) Varios `migrador` o réplicas concurrentes se serializan por el lock.
- (−) En desarrollo con `uvicorn --reload` hay que ejecutar `make bootstrap` (lo hace `make dev`) antes de la API; si no, `/salud/listo` responde 503 con `migraciones: falla`.
- (−) La contraseña aleatoria del admin queda en el log del contenedor `migrador`; se mitiga con el cambio obligatorio y con la recomendación de definir `ADMIN_INITIAL_PASSWORD` desde un gestor de secretos en producción.
