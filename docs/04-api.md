# 04 · Contrato de API (REST + WebSocket)

Base: `/api/v1`. JSON UTF-8. Autenticación: `Authorization: Bearer <access_jwt>` (15 min) + cookie `refresh` httpOnly/SameSite=Strict (7 días, rotativa). Todas las respuestas de error siguen RFC 9457 (`application/problem+json`). Paginación por cursor (`?cursor=&limit=`). Idempotencia en POST sensibles con `Idempotency-Key`.

Correlación: toda respuesta (incluidos errores) lleva `X-Request-ID`. Si el cliente envía un `X-Request-ID` que es un UUID válido se reutiliza; cualquier otro valor se descarta y se genera un UUID v4 nuevo. El mismo id aparece en los logs (`correlation_id`) y en el campo `instance` de los errores.

OpenAPI generado por FastAPI en `/api/v1/openapi.json`, con Swagger UI en `/api/v1/docs` y ReDoc en `/api/v1/redoc`. Con `ENV=production` las tres rutas responden 404; el acceso de admin a OpenAPI en producción se decide en E0.3, cuando exista autenticación.

## 1. Autenticación

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/auth/login` | público | `{email, password}` → `{access_token, expires_in, usuario}` + cookie refresh. Rate limit 5/min/IP. |
| POST | `/auth/refresh` | cookie | Rota refresh, emite access nuevo. Detecta reuso. |
| POST | `/auth/logout` | auth | Revoca familia de refresh. |
| GET | `/auth/me` | auth | Perfil y roles. |
| POST | `/auth/password/cambiar` | auth | Requiere password actual. |

## 2. Usuarios (admin)

`GET/POST /usuarios`, `GET/PATCH /usuarios/{id}`, `POST /usuarios/{id}/roles`, `POST /usuarios/{id}/desactivar`.

## 3. Proveedores de IA

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/proveedores` | admin, auditor | Lista proveedores, estado, credenciales enmascaradas. |
| PATCH | `/proveedores/{nombre}` | admin | `habilitado`, `base_url`, `config`. |
| PUT | `/proveedores/{nombre}/credencial` | admin | `{secreto}` → cifra y guarda. Nunca se devuelve. |
| POST | `/proveedores/{nombre}/probar` | admin | Llamada mínima de verificación; devuelve latencia y modelo. |
| GET | `/proveedores/{nombre}/modelos` | admin, operador | Modelos disponibles (consulta `/v1/models` del proveedor con caché 1 h). |

## 4. Cuentas de correo

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/cuentas` | admin, operador, auditor | Lista con estado de sincronización y último error. |
| POST | `/cuentas` | admin | Alta. Body incluye credenciales; se cifran. Valida host contra allowlist/denylist (sin IP privadas). |
| GET | `/cuentas/{id}` | admin, operador | Detalle sin secretos. |
| PATCH | `/cuentas/{id}` | admin | Cambios de config/política. |
| POST | `/cuentas/{id}/probar-conexion` | admin | Prueba IMAP y SMTP; devuelve capacidades (IDLE, carpetas). |
| POST | `/cuentas/{id}/sincronizar` | admin, operador | Fuerza sync inmediata. |
| POST | `/cuentas/{id}/pausar` · `/reanudar` | admin | |
| DELETE | `/cuentas/{id}` | admin | Borrado en cascada con confirmación (`?confirmar=<direccion>`). |

## 5. Mensajes y bandeja

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/mensajes` | operador, auditor | Filtros: `cuenta_id, estado, categoria, urgencia_min, desde, hasta, q` (búsqueda). |
| GET | `/mensajes/{id}` | operador, auditor | Detalle + clasificación + riesgo + ejecuciones + borradores. |
| POST | `/mensajes/{id}/reclasificar` | operador | Re-ejecuta el grafo desde Clasificador. |
| POST | `/mensajes/{id}/corregir-clasificacion` | operador | `{categoria_id, comentario}` → alimenta dataset. |
| POST | `/mensajes/{id}/archivar` · `/cuarentena` | operador | |
| GET | `/mensajes/{id}/hilo` | operador | Mensajes relacionados por `references`. |

## 6. Borradores y aprobación (human-in-the-loop)

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/borradores?estado=pendiente` | operador | Cola de aprobación. |
| GET | `/borradores/{id}` | operador | Borrador + citas + traza. |
| POST | `/borradores/{id}/aprobar` | operador | Opcional `{cuerpo_final, asunto_final}`. Reanuda el grafo (`resume`) y envía. Idempotente. |
| POST | `/borradores/{id}/rechazar` | operador | `{motivo}`. |
| POST | `/borradores/{id}/regenerar` | operador | `{instrucciones}` → nueva versión del borrador. |

## 7. Agentes y prompts

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/agentes` | todos | Lista con versión activa, proveedor, modelo, métricas 24 h. |
| POST | `/agentes` | admin | Crear agente (clave, tipo, proveedor, modelo, prompt inicial). |
| GET | `/agentes/{id}` | todos | |
| PATCH | `/agentes/{id}` | admin | proveedor, modelo, parámetros, herramientas, habilitado. Valida que el modelo exista en el proveedor. |
| GET | `/agentes/{id}/versiones` | todos | Historial de prompts. |
| POST | `/agentes/{id}/versiones` | admin | Crea versión nueva (`prompt_sistema`, `preguntas_jev`, `notas`). No se activa hasta `publicar`. |
| POST | `/agentes/{id}/versiones/{n}/publicar` | admin | Activa la versión. Auditoría. |
| POST | `/agentes/{id}/versiones/{n}/revertir` | admin | Publica una versión anterior. |
| POST | `/agentes/{id}/playground` | admin, operador | `{entrada, version_numero?, modelo_override?, stream?}` → salida + traza + costo. Con `stream=true` responde SSE. Límite 30/min/usuario. |
| GET | `/agentes/{id}/playground/historial` | mismo usuario | |

Validaciones del prompt: tamaño máximo 32 KB, sin secretos (regex), placeholders permitidos (`{{asunto}}`, `{{cuerpo}}`, `{{remitente}}`, `{{categoria}}`, `{{historial}}`), linter que advierte si el prompt pide ejecutar instrucciones del correo.

## 8. Taxonomía

`GET/POST /taxonomias`, `GET/PATCH /taxonomias/{id}`, `POST /taxonomias/{id}/categorias`, `PATCH/DELETE /categorias/{id}`, `PUT /categorias/{id}/acciones`. Cambiar la taxonomía genera automáticamente una nueva versión de `preguntas_jev` en el agente Clasificador (previa confirmación).

## 9. Ejecuciones y observabilidad

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/ejecuciones` | operador, auditor | Filtros por agente, estado, origen, rango. |
| GET | `/ejecuciones/{id}` | operador, auditor | Estado, entrada redactada, salida, llamadas LLM, checkpoints (pasos del grafo). |
| GET | `/metricas/resumen?desde&hasta&cuenta_id` | todos | KPIs: procesados, clasificados, precisión (con correcciones), costo, latencia p50/p95, tasa error, pendientes de aprobación. |
| GET | `/metricas/series?metrica=&intervalo=` | todos | Series temporales para gráficas. |
| GET | `/metricas/costos?agrupar=proveedor|modelo|agente|cuenta` | admin, auditor | |
| GET | `/metricas/categorias` | todos | Distribución y confianza media por categoría. |
| GET | `/auditoria` | admin, auditor | Registro append-only con filtros. |
| GET | `/salud` | público | Liveness; no consulta dependencias. 200 `{"estado":"vivo"}`. |
| GET | `/salud/listo` | público | Readiness. 200 `{"estado":"listo","comprobaciones":{"base_datos":"ok","migraciones":"ok"}}`; si alguna comprobación falla o excede `SALUD_BD_TIMEOUT_S`, 503 `no_listo` con `comprobaciones` (p. ej. `{"base_datos":"ok","migraciones":"falla"}`) y sin detalles de la dependencia ni revisiones. `migraciones` (E0.2) exige que `alembic_version` coincida con la revisión `head` del código; E1.1 añade `proveedores`. |
| GET | `/metrics` | red interna | Prometheus (protegido por red/basic auth). |

## 10. Webchat

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/webchat/sesiones` | Desde el widget con `clave_publica` del sitio y `Origin` validado → `{sesion_id, token_ws}` (JWT 1 h, audiencia `webchat`). |
| WS | `/ws/chat?token=` | Mensajes JSON: `{"tipo":"usuario","texto":...}` → eventos `{"tipo":"token","texto":...}`, `{"tipo":"fin"}`, `{"tipo":"escalado"}`, `{"tipo":"error"}`. Límite 20 msg/min/sesión, 4 KB por mensaje. |
| GET | `/webchat/sesiones` (operador) | Listado y transcripciones. |
| POST | `/webchat/sesiones/{id}/tomar` (operador) | El operador toma el control; el agente deja de responder. |
| GET/POST/PATCH | `/webchat/sitios` (admin) | Configuración del widget: orígenes permitidos, agente, textos, colores. |

## 11. Esquemas principales (Pydantic)

```python
class ClasificacionOut(BaseModel):
    categoria: str
    confianza: float          # 0..1
    probabilidades: dict[str, float]
    urgencia: float           # 0..2 (score esperado)
    requiere_respuesta: float # 0..1
    riesgo: RiesgoOut
    motor: Literal["jev", "llm"]
    version_prompt: int
    explicacion: str | None   # breve, generada solo si motor == "llm"

class RiesgoOut(BaseModel):
    jailbreak: float; phishing: float; inyeccion: float
    spf: Literal["pass","fail","none"]; dkim: ...; dmarc: ...
    nivel: Literal["bajo","medio","alto"]

class PlaygroundIn(BaseModel):
    entrada: dict            # {asunto, cuerpo, remitente} o {texto} según agente
    version_numero: int | None = None
    modelo_override: str | None = Field(None, pattern=r"^[a-z]+:[A-Za-z0-9.\-]+$")
    stream: bool = False
```

## 12. Códigos de error

| HTTP | `type` | Cuándo |
|---|---|---|
| 400 | `validacion` | Body inválido (detalle por campo). |
| 401 | `no_autenticado` | Token ausente/expirado. |
| 403 | `sin_permiso` | Rol insuficiente. |
| 404 | `no_encontrado` | Ruta o recurso inexistente. |
| 405 | `metodo_no_permitido` | La ruta existe pero no admite el método; incluye cabecera `Allow`. |
| 409 | `conflicto` | Versión ya publicada, cuenta duplicada, idempotencia. |
| 422 | `proveedor_rechazo` | El proveedor de IA rechazó la petición (incluye `stop_reason=refusal`). |
| 429 | `limite_excedido` | Rate limit (`Retry-After`). |
| 502 | `proveedor_no_disponible` | Falla upstream tras reintentos. |
| 500 | `error_interno` | Excepción no manejada. `detail` fijo ("Error interno. Cite el identificador al reportarlo."); nunca incluye mensaje ni traza. |
| 503 | `no_listo` | Migraciones o BD no disponibles. Extensión `comprobaciones`. |
| otros | `error_http` | Otros códigos HTTP del framework; `title` es la frase estándar del código. |

Formato de todo error (`Content-Type: application/problem+json`):

```json
{
  "type": "validacion",
  "title": "Petición inválida",
  "status": 400,
  "detail": "La petición contiene campos inválidos.",
  "instance": "urn:uuid:3f2b8c1e-6d4a-4f7e-9a51-2b0c8d7e6f10",
  "errores": [{"campo": "body.email", "mensaje": "Field required"}]
}
```

- `instance` es `urn:uuid:<X-Request-ID>` de la petición.
- `validacion` usa 400 (no 422) y `errores[]` solo lleva `campo` y `mensaje`: nunca el valor recibido.
- Extensiones por tipo: `errores` (400), `comprobaciones` (503).
