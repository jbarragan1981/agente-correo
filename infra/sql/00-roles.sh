#!/bin/sh
# Crea los roles (roles.sql) y les asigna contraseña desde el entorno (ADR-0008).
# Lo ejecuta el entrypoint de postgres con un volumen vacío (/docker-entrypoint-initdb.d) y
# `make db-roles` para volúmenes existentes. Conexión por las variables libpq habituales
# (PGHOST, PGPORT, PGPASSWORD) si se ejecuta fuera del contenedor. Nunca imprime contraseñas.
set -eu

: "${AGENTE_MIGRADOR_PASSWORD:?Define AGENTE_MIGRADOR_PASSWORD}"
: "${AGENTE_APP_PASSWORD:?Define AGENTE_APP_PASSWORD}"

USUARIO="${POSTGRES_USER:-postgres}"
BASE="${POSTGRES_DB:-agente_correo}"
ROLES_SQL="${ROLES_SQL:-/sql/roles.sql}"

psql -v ON_ERROR_STOP=1 --username "$USUARIO" --dbname "$BASE" -f "$ROLES_SQL"

# \getenv (psql >= 15) lee las contraseñas del entorno: no pasan por argv ni por `ps`.
psql -v ON_ERROR_STOP=1 --username "$USUARIO" --dbname "$BASE" <<'SQL'
\getenv pass_migrador AGENTE_MIGRADOR_PASSWORD
\getenv pass_app AGENTE_APP_PASSWORD
ALTER ROLE agente_migrador PASSWORD :'pass_migrador';
ALTER ROLE agente_app PASSWORD :'pass_app';
SQL
