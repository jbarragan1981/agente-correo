-- Roles de base de datos (ADR-0008). SQL puro e idempotente: ejecutable con psql o con un cursor.
-- Se aplica sobre la base de la aplicación (current_database()). Sin contraseñas: las asigna
-- infra/sql/00-roles.sh desde variables de entorno. El bootstrap no crea roles.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agente_migrador') THEN CREATE ROLE agente_migrador LOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agente_app') THEN CREATE ROLE agente_app LOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agente_lectura') THEN CREATE ROLE agente_lectura LOGIN; END IF;
END $$;

ALTER ROLE agente_migrador NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION;
ALTER ROLE agente_app      NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION;
ALTER ROLE agente_lectura  NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION;

DO $$ BEGIN
  EXECUTE format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database());
  EXECUTE format('GRANT CONNECT, CREATE, TEMPORARY ON DATABASE %I TO agente_migrador', current_database());
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO agente_app, agente_lectura', current_database());
END $$;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO agente_migrador;
GRANT USAGE ON SCHEMA public TO agente_app, agente_lectura;

ALTER DEFAULT PRIVILEGES FOR ROLE agente_migrador IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO agente_app;
ALTER DEFAULT PRIVILEGES FOR ROLE agente_migrador IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO agente_app;
ALTER DEFAULT PRIVILEGES FOR ROLE agente_migrador IN SCHEMA public GRANT SELECT ON TABLES TO agente_lectura;
-- El REVOKE de auditoria y los privilegios de procrastinate y langgraph los aplica cada migración
-- (función agente_conceder_privilegios, ADR-0010).
