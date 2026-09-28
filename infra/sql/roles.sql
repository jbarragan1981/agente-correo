-- Roles de base de datos para producción (DB_ROLES_SEPARADOS=true). Idempotente.
-- Las contraseñas se asignan fuera de este archivo (ALTER ROLE ... PASSWORD desde el bootstrap con valores de entorno).
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agente_migrador') THEN CREATE ROLE agente_migrador LOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agente_app') THEN CREATE ROLE agente_app LOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agente_lectura') THEN CREATE ROLE agente_lectura LOGIN; END IF;
END $$;

GRANT CONNECT ON DATABASE agente_correo TO agente_app, agente_lectura, agente_migrador;
GRANT ALL ON SCHEMA public TO agente_migrador;
GRANT USAGE ON SCHEMA public TO agente_app, agente_lectura;
ALTER DEFAULT PRIVILEGES FOR ROLE agente_migrador IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO agente_app;
ALTER DEFAULT PRIVILEGES FOR ROLE agente_migrador IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO agente_app;
ALTER DEFAULT PRIVILEGES FOR ROLE agente_migrador IN SCHEMA public GRANT SELECT ON TABLES TO agente_lectura;
-- La auditoría es append-only para la aplicación: la migración que crea la tabla revoca UPDATE/DELETE a agente_app.
