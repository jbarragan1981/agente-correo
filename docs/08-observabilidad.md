# 08 · Observabilidad

## 1. Tres señales + trazas de LLM

| Señal | Herramienta | Qué se captura |
|---|---|---|
| Logs | structlog → JSON a stdout | `nivel, evento, trace_id, span_id, usuario_id, cuenta_id, mensaje_id, ejecucion_id, agente, duracion_ms`. PII redactada. |
| Métricas | OpenTelemetry → Prometheus (`/metrics`) | Contadores, histogramas y gauges de negocio y técnicos (abajo). |
| Trazas | OpenTelemetry (FastAPI, SQLAlchemy, httpx, nodos LangGraph instrumentados a mano) → OTLP | Un trace por mensaje/turno; un span por nodo del grafo y por llamada a proveedor. |
| Trazas LLM | Tablas propias (`ejecuciones_agente`, `llamadas_llm`) + Langfuse opcional | Prompt versionado, entrada redactada, salida, tokens, costo, latencia, stop_reason. |

Correlación: `trace_id` de OTel se guarda en `ejecuciones_agente.traza_otel_id` y se muestra en el panel para saltar a Grafana Tempo/Langfuse.

### 1.1 Formato de logs (desde E0.1)

- Una línea JSON por evento en stdout, tanto de la app como de `uvicorn`, `uvicorn.error`, `sqlalchemy` y `asyncio` (misma cadena de procesadores). Campos base: `timestamp` (ISO 8601 UTC), `nivel`, `evento`, `logger` y `correlation_id` cuando hay una petición en curso (igual a la cabecera `X-Request-ID`).
- Log de acceso propio `evento="http.peticion"` con `metodo`, `ruta` (**sin query string**), `estado` y `duracion_ms`. El access log de Uvicorn está deshabilitado (`--no-access-log`) y `httpx`/`httpcore` solo registran avisos, para que ninguna URL con parámetros llegue a los logs.
- Excepciones no manejadas: `evento="http.error_inesperado"` con `exception` (traza redactada; si excede 8 000 caracteres se conserva el final, donde están el tipo y el mensaje).
- Redacción (`app/core/logging.py`, procesador `redactar`, aplicado tras formatear excepciones): claves que contienen `password`, `contrasena`, `contraseña`, `secreto`, `secret`, `token`, `authorization`, `api_key`, `apikey`, `cookie`, `master_key`, `jwt`, `database_url` o `dsn` (sin distinguir mayúsculas ni `-`/`_`) → `[REDACTADO]`; en cualquier texto se reemplazan JWT, `Bearer …`, `sk-ant-…`, `sk-…`, `ts_…`, contraseñas en URL (`://usuario:***@`) y parámetros de query sensibles; emails → `j***@dominio`; `SecretStr` → `**********`; textos > 2 000 caracteres se truncan.
- Hasta E1.10 (OpenTelemetry y `/metrics`) el log de acceso (`estado`, `duracion_ms`) es la señal de latencia y errores HTTP disponible.

## 2. Métricas (nombres OTel)

**Negocio**
- `correo_mensajes_recibidos_total{cuenta}`
- `correo_mensajes_clasificados_total{cuenta, categoria, motor}`
- `correo_clasificacion_confianza` (histograma, buckets 0.1)
- `correo_respaldo_llm_total{motivo}` (baja confianza, jev_no_disponible)
- `correo_riesgo_detectado_total{tipo, nivel}`
- `correo_borradores_total{estado}` y `correo_tiempo_aprobacion_segundos` (histograma)
- `correo_enviados_total{cuenta, resultado}`
- `webchat_sesiones_activas` (gauge), `webchat_turnos_total`, `webchat_escalados_total`
- `ia_costo_usd_total{proveedor, modelo, agente}`
- `ia_tokens_total{proveedor, modelo, direccion}`

**Técnicas**
- `ia_llamada_duracion_segundos{proveedor, modelo}` (histograma)
- `ia_llamada_errores_total{proveedor, tipo}` (rate_limit, timeout, refusal, 5xx)
- `agente_nodo_duracion_segundos{agente}`
- `imap_sync_duracion_segundos{cuenta}`, `imap_conexion_errores_total{cuenta}`
- `cola_trabajos_pendientes{cola}` (gauge), `cola_trabajo_duracion_segundos`, `cola_reintentos_total`
- `http_server_*` (instrumentación FastAPI), `db_client_*` (SQLAlchemy)

## 3. Dashboard del panel (fuente: PostgreSQL)

El panel Angular consume `/metricas/*`, que leen `mv_metricas_diarias` y agregados en caliente de las últimas 24 h. Así el dashboard funciona sin Grafana. Grafana/Tempo/Langfuse son opcionales para el equipo de plataforma.

## 4. Alertas recomendadas (Prometheus/Alertmanager o el propio panel)

| Alerta | Condición | Severidad |
|---|---|---|
| Cuenta sin sincronizar | `time() - imap_ultimo_sync > 15 min` | alta |
| Tasa de error de proveedor | `rate(ia_llamada_errores_total[10m]) > 5 %` | alta |
| Respaldo LLM elevado | `respaldo_llm / clasificados > 25 %` durante 1 h | media (Jev degradado o taxonomía ambigua) |
| Presupuesto de costo | `ia_costo_usd_total` diario > umbral por cuenta | alta (corta procesamiento generativo) |
| Cola atascada | `cola_trabajos_pendientes > 500` durante 10 min | alta |
| Cuarentena anómala | picos de `riesgo_detectado{nivel="alto"}` | media |
| Aprobaciones envejecidas | borradores pendientes > 4 h | media |

## 5. Costos

`llamadas_llm.costo_usd` se calcula en el adaptador con `providers/precios.yaml` (entrada, salida, lectura de caché). Jev: `input_tokens × 0,042 / 1e6`. Anthropic: precios por modelo de la tabla de `02-stack-tecnologico.md`. El panel muestra costo por día, proveedor, modelo, agente y cuenta, y el costo medio por correo.

## 6. Trazas de una ejecución (lo que ve el operador)

```
Ejecución 019a… · correo · 1,84 s · USD 0,00031
├─ ingestor        12 ms
├─ guardian (jev)  98 ms   jailbreak 0.02 · phishing 0.01 · riesgo 0.1 → bajo
├─ clasificador    104 ms  soporte 0.91 · urgencia 1.6 · requiere_respuesta 0.88  (jev, 2.1K tok, USD 0.00009)
├─ enrutador       3 ms    → redactor (regla: requiere_respuesta ≥ 0.6)
├─ redactor        1.62 s  claude-opus-5-5 · effort medium · 3.4K in / 210 out · USD 0.0179 · tools: buscar_hilo
└─ aprobacion      interrumpido · pendiente
```

## 7. Registro de eventos de negocio (auditoría)

Acciones auditadas: login/logout, cambios de configuración, alta/baja de cuentas, publicación de versiones de prompt, cambio de modelo/proveedor, aprobación/rechazo/edición de borradores, envíos, correcciones de clasificación, toma de control de chat, exportaciones. Cada fila con actor, IP, entidad, diff antes/después (redactado).
