# ADR-0006 · Secretos con cifrado envelope y clave maestra externa

**Estado:** Aceptada · 2026-09-28

## Contexto
Se almacenan contraseñas de aplicación de correo, refresh tokens OAuth y API keys de proveedores de IA. La fuga de estos secretos compromete buzones corporativos y genera costos.

## Decisión
Cifrado envelope: clave de datos aleatoria por secreto (AES-256-GCM, nonce único) y clave de datos cifrada con la clave maestra `APP_MASTER_KEY` (32 bytes) que vive fuera de la BD (variable de entorno, KMS o Vault). Se guarda `version_clave_maestra` para rotación. Los secretos nunca salen por la API; se escriben con endpoints `PUT` dedicados; los logs los redactan. En Fase 2 la clave maestra se obtiene de KMS con `KMS_KEY_ID`.

## Alternativas descartadas
- `pgcrypto` con clave en la BD: la clave viaja en cada consulta y queda en logs de BD.
- Secretos en texto plano con cifrado de disco: no protege contra volcado de la BD.

## Consecuencias
- (+) Rotación sin reescribir toda la tabla de golpe (re-cifrado perezoso por versión).
- (−) Perder la clave maestra vuelve irrecuperables las credenciales; se documenta el procedimiento de custodia y respaldo de la clave.
