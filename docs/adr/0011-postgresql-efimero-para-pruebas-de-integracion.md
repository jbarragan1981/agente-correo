# ADR-0011 · PostgreSQL efímero para pruebas de integración: Docker o binarios locales

**Estado:** Aceptada · 2026-09-28 · Épica E0.2

## Contexto
`docs/09-testing-y-calidad.md` prevé testcontainers con PostgreSQL 17. En el entorno de desarrollo de los agentes de Claude Code el CLI de Docker existe pero no hay daemon, así que las pruebas de integración de E0.1 quedaron "pendientes de ejecutar con Docker". El arquitecto verificó el 2026-09-28 que el host tiene PostgreSQL 16.13 instalado (`/usr/lib/postgresql/16/bin`, con `citext`, `pgcrypto` y `pg_trgm`), que el repositorio PGDG (PostgreSQL 17) no es accesible (403 del proxy) y que un clúster temporal creado con `initdb` + `pg_ctl` como usuario `postgres` en un directorio propio, escuchando solo en `127.0.0.1` y con autenticación `scram-sha-256`, arranca en segundos y ejecuta migraciones, procrastinate y LangGraph.

## Decisión
- Una fixture de sesión `postgres_efimero` (`tests/integracion/pg_efimero.py`) resuelve el servidor en este orden:
  1. `PRUEBAS_PG_DSN` definida → usa ese servidor (debe ser desechable; la fixture crea y borra bases con prefijo `prueba_`).
  2. Daemon Docker disponible (`docker info` con código 0) → testcontainers `postgres:17-alpine`.
  3. Binarios locales (`pg_config --bindir` o `/usr/lib/postgresql/*/bin/initdb`, la versión mayor más alta) → clúster temporal: `tempfile.mkdtemp`, `initdb -U postgres --auth=scram-sha-256 --pwfile --encoding=UTF8 --locale=C` con contraseña aleatoria generada en la sesión (la codificación explícita es obligatoria: con `LANG` sin definir `initdb` crea un clúster `SQL_ASCII` y psycopg devuelve `bytes` en lugar de `str`, lo que rompe la fixture; lo mismo ocurre con un `PRUEBAS_PG_DSN` hacia un servidor no UTF-8), `pg_ctl start -o "-p <puerto libre> -k <dir> -c listen_addresses=127.0.0.1 -c fsync=off"`; si el proceso corre como root, los comandos se ejecutan con `runuser -u postgres` y el directorio se entrega a ese usuario; `pg_ctl stop -m fast` y borrado del directorio al terminar.
  4. Ninguno disponible → la sesión **falla** con un mensaje que explica las tres opciones. Nunca `skip`.
- La fixture expone la versión mayor del servidor; las pruebas no usan funciones exclusivas de PostgreSQL 17. Si una prueba futura las necesita, se marca con la versión mínima y falla (no se omite) en servidores anteriores.
- `make test-int` ejecuta `pytest -m integracion` y funciona con cualquiera de las tres fuentes.
- CI (E0.5) usa Docker, es decir, PostgreSQL 17.

## Alternativas consideradas
- **Mantener solo testcontainers:** las pruebas de E0.2 (migraciones, roles, auditoría, concurrencia) quedarían sin ejecutar en la sesión que las escribe. Descartada.
- **Usar el clúster `16/main` del sistema:** comparte estado entre sesiones y exige tocar su configuración. Descartada.
- **`pytest-postgresql`:** dependencia extra que resuelve lo mismo que ~80 líneas de fixture y no cubre el caso root/`runuser`. Descartada.

## Consecuencias
- (+) Las pruebas de integración se ejecutan de verdad en el entorno de los agentes.
- (−) Localmente se prueba con PostgreSQL 16 y en CI con 17; el riesgo de divergencia es bajo para el DDL usado y CI es la referencia.
- (−) La fixture necesita `runuser` cuando corre como root; está disponible en el host verificado.
