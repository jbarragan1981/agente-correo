# 03 · Modelo de datos (PostgreSQL 17)

Convenciones: tablas y columnas en `snake_case` español; claves primarias `uuid` (v7 generadas en la app); `creado_en`/`actualizado_en` `timestamptz` en todas las tablas; borrado lógico solo donde se indica; JSONB para payloads flexibles con validación en Pydantic. Extensiones: `pgcrypto`, `pg_trgm` (búsqueda), `uuid-ossp` opcional.

## 1. Diagrama entidad-relación (resumen)

```
usuarios ──< sesiones_refresh
usuarios ──< auditoria
roles ──< usuarios_roles >── usuarios

cuentas_correo ──< carpetas_correo
cuentas_correo ──< mensajes ──< adjuntos_meta
mensajes ──< clasificaciones
mensajes ──< ejecuciones_agente ──< llamadas_llm
mensajes ──< borradores ──< aprobaciones

agentes ──< versiones_prompt
agentes ──< ejecuciones_agente
proveedores_ia ──< credenciales_proveedor

taxonomias ──< categorias ──< acciones_categoria

sesiones_chat ──< turnos_chat ──< ejecuciones_agente

trabajos (procrastinate_*)   checkpoints (langgraph: checkpoints, checkpoint_blobs, checkpoint_writes)
```

## 2. Tablas

### 2.1 Identidad y acceso

**`usuarios`**
| columna | tipo | notas |
|---|---|---|
| id | uuid PK | |
| email | citext UNIQUE | |
| nombre | text | |
| hash_password | text | Argon2id. Null si solo SSO. |
| activo | bool | default true |
| mfa_secreto_cifrado | bytea | Fase 2 (TOTP) |
| ultimo_acceso_en | timestamptz | |

**`roles`** (`admin`, `operador`, `auditor`) y **`usuarios_roles`** (usuario_id, rol_id, PK compuesta).

**`sesiones_refresh`**: id, usuario_id, hash_token (sha256), familia (uuid, para detectar reuso), expira_en, revocado_en, ip, user_agent. Rotación en cada refresh; reuso de un token revocado revoca toda la familia.

**`auditoria`** (append-only, sin UPDATE/DELETE por permisos de rol de BD): id, ocurrido_en, actor_id, actor_tipo (`usuario`|`sistema`|`agente`), accion, entidad, entidad_id, detalle JSONB, ip, hash_previo (encadenado para detectar manipulación).

### 2.2 Proveedores y secretos

**`proveedores_ia`**: id, nombre (`anthropic`|`openai`|`gemini`|`jev`), habilitado, base_url (nullable), config JSONB (timeouts, reintentos), creado_en.

**`credenciales_proveedor`**: id, proveedor_id, etiqueta, **secreto_cifrado bytea**, **clave_datos_cifrada bytea**, nonce bytea, version_clave_maestra int, ultimo_uso_en, creado_por. Nunca se devuelve el secreto por API; solo `****últimos4`.

### 2.3 Correo

**`cuentas_correo`**
| columna | tipo | notas |
|---|---|---|
| id | uuid PK | |
| nombre | text | "Soporte Viamatica" |
| direccion | citext | |
| protocolo_entrada | text | `imap` (Fase 2: `gmail_api`, `graph`) |
| imap_host, imap_puerto, imap_tls | text,int,text | tls: `ssl`|`starttls` |
| smtp_host, smtp_puerto, smtp_tls | text,int,text | |
| usuario | text | |
| secreto_cifrado, clave_datos_cifrada, nonce, version_clave_maestra | bytea/int | contraseña de app o refresh token OAuth |
| carpeta_entrada | text | default `INBOX` |
| modo_sync | text | `idle`|`polling` |
| intervalo_polling_s | int | default 60 |
| estado | text | `activa`|`pausada`|`error` |
| ultimo_uid | bigint | cursor IMAP |
| uidvalidity | bigint | detecta reinicios del buzón |
| ultimo_error | text | |
| taxonomia_id | uuid FK | qué taxonomía aplica |
| politica JSONB | | envío automático, límites, firmas |

**`carpetas_correo`**: id, cuenta_id, nombre, ruta, proposito (`entrada`|`procesados`|`cuarentena`|`spam`).

**`mensajes`**
| columna | tipo | notas |
|---|---|---|
| id | uuid PK | también `thread_id` del grafo |
| cuenta_id | uuid FK | |
| uid_imap | bigint | UNIQUE (cuenta_id, uidvalidity, uid_imap) |
| message_id | text | cabecera; índice |
| in_reply_to, referencias | text, text[] | hilos |
| hash_contenido | text | dedupe |
| de, para, cc | jsonb | `[{nombre, direccion}]` |
| asunto | text | |
| fecha | timestamptz | |
| cuerpo_texto | text | saneado |
| cuerpo_html_saneado | text | nh3 |
| idioma | text | |
| cabeceras_auth | jsonb | spf, dkim, dmarc |
| tiene_adjuntos | bool | |
| estado | text | `recibido`→`en_proceso`→`clasificado`→`pendiente_aprobacion`→`respondido`/`archivado`/`cuarentena`/`error` |
| canal | text | `correo` |
| busqueda | tsvector | GIN (asunto + cuerpo) |

**`adjuntos_meta`**: id, mensaje_id, nombre, mime, tamano, hash_sha256, escaneado (bool), veredicto. Los binarios no se guardan en Fase 1 (se leen bajo demanda del IMAP).

### 2.4 Taxonomía y acciones

**`taxonomias`**: id, nombre, descripcion, activa.
**`categorias`**: id, taxonomia_id, clave (`facturacion`, `soporte`, `comercial`, `spam`, `phishing`, `interno`, `otro`), nombre, descripcion_para_modelo (texto que va al `criteria` de Jev), umbral_confianza numeric(3,2) default 0.70, prioridad int, color.
**`acciones_categoria`**: id, categoria_id, tipo (`etiquetar`|`mover`|`marcar_leido`|`webhook`|`escalar`|`responder`|`cuarentena`), parametros JSONB, orden.

### 2.5 Agentes

**`agentes`**
| columna | tipo | notas |
|---|---|---|
| id | uuid PK | |
| clave | text UNIQUE | `guardian`, `clasificador`, `enrutador`, `redactor`, `webchat`, `extractor` |
| nombre, descripcion | text | |
| tipo | text | `decision` (Jev/LLM estructurado) · `generativo` · `reglas` |
| proveedor_id | uuid FK | |
| modelo | text | `claude-opus-5-5`, `jev-latest`… |
| parametros JSONB | | effort, max_tokens, temperatura (si aplica), umbrales |
| modelo_respaldo | text | `anthropic:claude-haiku-4-5` |
| herramientas text[] | | allowlist de tools |
| version_prompt_activa_id | uuid FK | |
| habilitado | bool | |

**`versiones_prompt`**: id, agente_id, numero int, prompt_sistema text, preguntas_jev JSONB (para agentes `decision`: mapa de `Noul/Choice/Score`), esquema_salida JSONB, notas, creado_por, creado_en, publicado_en. Inmutable una vez publicada; se crea una nueva versión por cada cambio. UNIQUE (agente_id, numero).

**`ejecuciones_agente`**: id, agente_id, version_prompt_id, mensaje_id (nullable), turno_chat_id (nullable), origen (`correo`|`webchat`|`playground`), estado (`ok`|`error`|`interrumpida`), entrada JSONB (redactada), salida JSONB, inicio_en, fin_en, duracion_ms, error, traza_otel_id.

**`llamadas_llm`**: id, ejecucion_id, proveedor, modelo, tokens_entrada, tokens_salida, tokens_cache_lectura, costo_usd numeric(12,8), latencia_ms, stop_reason, request_id_proveedor, exito bool. Índice por (proveedor, modelo, creado_en) para el dashboard.

**`clasificaciones`**: id, mensaje_id, ejecucion_id, categoria_id, categoria_clave, confianza numeric(4,3), probabilidades JSONB, urgencia numeric(3,2), requiere_respuesta numeric(3,2), riesgo JSONB (`{jailbreak, phishing, inyeccion, spf_ok, dkim_ok, dmarc_ok}`), motor (`jev`|`llm`), corregida_por (usuario nullable), categoria_corregida_id (nullable). Las correcciones alimentan el dataset de evaluación.

### 2.6 Borradores y aprobación

**`borradores`**: id, mensaje_id, ejecucion_id, asunto, cuerpo_texto, cuerpo_html, para/cc JSONB, citas JSONB (fuentes usadas), version int, estado (`pendiente`|`aprobado`|`editado`|`rechazado`|`enviado`|`fallido`), enviado_en, message_id_enviado.
**`aprobaciones`**: id, borrador_id, usuario_id, decision, comentario, cuerpo_final (si editó), decidido_en.

### 2.7 Webchat

**`sesiones_chat`**: id, sitio_id, visitante_hash, iniciada_en, ultima_actividad_en, estado, metadatos JSONB (página, idioma; sin PII salvo consentimiento), escalada_a (usuario nullable).
**`turnos_chat`**: id, sesion_id, rol (`visitante`|`agente`|`operador`), contenido, riesgo JSONB, creado_en.
**`sitios_webchat`**: id, nombre, origenes_permitidos text[], clave_publica, agente_id, activo.

### 2.8 Playground y evaluación

**`sesiones_playground`**: id, agente_id, version_prompt_id, usuario_id, entrada JSONB, salida JSONB, trazas JSONB, costo_usd, creado_en.
**`dataset_evaluacion`** (Fase 2): id, mensaje_id, categoria_esperada_id, origen (`correccion`|`manual`), creado_en.

### 2.9 Configuración

**`configuracion`**: clave text PK, valor JSONB, descripcion, editable_ui bool, actualizado_por, actualizado_en. Ej.: `retencion_dias_mensajes`, `umbral_riesgo_cuarentena`, `envio_automatico_habilitado`.

## 3. Tablas gestionadas por librerías

- `procrastinate_jobs`, `procrastinate_events`, `procrastinate_periodic_defers` (esquema propio de procrastinate, aplicado en el arranque).
- `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations` (LangGraph). Se ubican en el esquema `langgraph` para separarlas.

## 4. Índices y rendimiento

- `mensajes(cuenta_id, estado, fecha desc)` para la bandeja.
- `mensajes USING gin(busqueda)`; `mensajes(message_id)`; `mensajes(hash_contenido)`.
- `llamadas_llm(creado_en)` BRIN + `(proveedor, modelo)` para agregados del dashboard.
- Vistas materializadas para el dashboard: `mv_metricas_diarias` (por día, cuenta, categoría, motor: conteo, costo, latencia p50/p95), refrescadas cada 5 min por trabajo periódico.
- Particionado por mes de `llamadas_llm` y `auditoria` cuando superen 20 M filas (Fase 2).

## 5. Retención y privacidad

- `retencion_dias_mensajes` (default 180): trabajo diario que anonimiza `cuerpo_*`, `de`, `para` y elimina adjuntos_meta; mantiene métricas agregadas.
- Borrar una cuenta de correo elimina en cascada mensajes, clasificaciones, borradores y checkpoints asociados (transacción + auditoría).
- Las entradas en `ejecuciones_agente.entrada` se redactan (emails, teléfonos, tarjetas) antes de persistir.

## 6. Roles de base de datos

| Rol | Permisos |
|---|---|
| `agente_app` | CRUD en tablas de aplicación; INSERT-only en `auditoria`. |
| `agente_migrador` | DDL; usado solo durante `alembic upgrade`. |
| `agente_lectura` | SELECT para BI/auditoría externa. |

En MVP, con `DB_AUTO_CREATE=true`, el arranque crea la base y usa un solo rol; la separación se activa con `DB_ROLES_SEPARADOS=true` en producción.
