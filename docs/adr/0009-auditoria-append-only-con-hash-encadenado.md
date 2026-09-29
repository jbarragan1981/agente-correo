# ADR-0009 · Auditoría append-only con hash encadenado en PostgreSQL

**Estado:** Aceptada · 2026-09-28 · Épica E0.2

## Contexto
`docs/03-modelo-de-datos.md` §2.1 y `docs/07-seguridad.md` §6 exigen una tabla `auditoria` append-only, sin `UPDATE`/`DELETE` para el rol de aplicación y con `hash_previo` encadenado para detectar manipulación. Hay que decidir dónde se calcula el hash, cómo se ordena la cadena con inserciones concurrentes y cómo se protege la tabla en el modo de rol único de desarrollo, donde el rol conectado es propietario de la tabla (el `REVOKE` no le afecta).

## Decisión
- Columnas añadidas al modelo documentado: `secuencia bigint GENERATED ALWAYS AS IDENTITY UNIQUE` (orden de la cadena, independiente del reloj) y `hash bytea NOT NULL` (hash de la fila). `ocurrido_en` lo fija el trigger con `now()`; el cliente no puede antedatar.
- Una función SQL inmutable `auditoria_calcular_hash(hash_previo, secuencia, ocurrido_en, actor_id, actor_tipo, accion, entidad, entidad_id, detalle, ip) RETURNS bytea` calcula
  `digest(coalesce(hash_previo, '') || convert_to(jsonb_build_array(secuencia, epoch_µs(ocurrido_en), actor_id, actor_tipo, accion, entidad, entidad_id, detalle, host(ip))::text, 'UTF8'), 'sha256')`.
  `jsonb_build_array(...)::text` da una serialización canónica sin ambigüedad de separadores; el tiempo se usa en microsegundos desde epoch para no depender del `TimeZone` de la sesión.
- Trigger `BEFORE INSERT` (`auditoria_encadenar`, `SET search_path = public, pg_temp`): toma `pg_advisory_xact_lock(0xA6E17F)`, lee el `hash` de la fila de mayor `secuencia`, fija `ocurrido_en`, `hash_previo` y `hash`. El lock transaccional serializa las inserciones de auditoría y garantiza una cadena lineal.
- Triggers `BEFORE UPDATE OR DELETE` (por fila) y `BEFORE TRUNCATE` (por sentencia) que lanzan excepción: protegen también al propietario y al modo de rol único.
- En la migración: `REVOKE UPDATE, DELETE, TRUNCATE ON auditoria FROM agente_app` si el rol existe (bloque `DO` condicional para el modo de rol único).
- Sin FK de `actor_id` a `usuarios`: la auditoría debe sobrevivir al borrado de usuarios.
- Verificación: el adaptador `RepositorioAuditoriaSql.verificar_cadena()` recalcula la cadena en SQL con la misma función y devuelve la primera `secuencia` rota. E1.10 la expone por API.
- El dominio define `EntradaAuditoria` y `ActorTipo`; la aplicación define `AuditoriaPort.registrar(entrada)`; el adaptador SQL inserta sin calcular hash.

## Alternativas consideradas
- **Hash calculado en Python**: dos procesos concurrentes leerían el mismo último hash y bifurcarían la cadena, salvo que la aplicación tome el mismo lock; duplica la lógica entre escritor y verificador. Descartada.
- **Orden por `ocurrido_en` o por UUID v7**: dos filas pueden compartir marca de tiempo y el reloj de la app no es fuente de verdad. Descartada.
- **Solo `REVOKE`**: no protege en desarrollo ni frente al propietario. Se combinan ambos controles.
- **Extensión externa (pgaudit) o tabla particionada desde el inicio**: no la exige ningún requisito de MVP. El particionado mensual queda para Fase 2 (`docs/03-modelo-de-datos.md` §4).

## Consecuencias
- (+) Cualquier modificación o borrado posterior (por un superusuario que desactive triggers) rompe la cadena y es detectable.
- (+) El rol de aplicación no puede alterar la auditoría ni por permisos ni por triggers.
- (−) Las inserciones de auditoría se serializan; aceptable para el volumen previsto (decenas por segundo). Si se convierte en cuello de botella, se evalúa cadena por partición.
- (−) Un superusuario puede desactivar los triggers y reescribir toda la cadena; se mitiga fuera de la BD (respaldos cifrados y, en Fase 2, anclaje periódico del último hash en almacenamiento externo).
