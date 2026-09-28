# 01 · Arquitectura

## 1. Vista de contexto (C4 nivel 1)

```
┌──────────────┐   IMAP/SMTP    ┌──────────────────────────────┐    HTTPS/WSS   ┌─────────────────┐
│ Servidores   │◄──────────────►│                              │◄──────────────►│ Panel Angular    │
│ de correo    │                │   Agente Correo (backend)    │                │ (operadores)     │
└──────────────┘                │   FastAPI + LangGraph        │                └─────────────────┘
                                │                              │    WSS         ┌─────────────────┐
┌──────────────┐   HTTPS        │  ┌────────────────────────┐  │◄──────────────►│ Widget webchat   │
│ Proveedores  │◄──────────────►│  │  Enjambre de agentes   │  │                │ (sitio cliente)  │
│ IA: Anthropic│                │  └────────────────────────┘  │                └─────────────────┘
│ OpenAI,Gemini│                │                              │
│ TypeSafe Jev │                └──────────────┬───────────────┘
└──────────────┘                               │ SQL
                                       ┌───────▼────────┐
                                       │  PostgreSQL 17 │
                                       └────────────────┘
```

## 2. Vista de contenedores (C4 nivel 2)

| Contenedor | Tecnología | Responsabilidad |
|---|---|---|
| `api` | FastAPI + Uvicorn | REST, WebSocket de webchat, autenticación, configuración, métricas. |
| `worker` | Mismo código, entrypoint distinto | Sincronización IMAP (IDLE), cola de trabajos, ejecución del enjambre. Escala horizontal. |
| `web` | Angular 22 servido por Nginx | Panel de operación y widget. |
| `db` | PostgreSQL 17 | Datos de negocio, cola (`SKIP LOCKED`), checkpoints de LangGraph, auditoría. |
| `otel-collector` (opcional) | OpenTelemetry Collector | Exporta trazas/métricas a Grafana Tempo/Prometheus o Langfuse. |

`api` y `worker` comparten imagen. En desarrollo un solo proceso levanta ambos (`make dev`). El único servicio obligatorio es PostgreSQL.

## 3. Arquitectura interna del backend (hexagonal)

```
backend/app/
├── domain/            # Entidades, value objects, reglas. Cero dependencias externas.
│   ├── mail/          # Mensaje, Cuenta, Etiqueta, Política
│   ├── agents/        # Agente, VersiónPrompt, Ejecución, Decisión
│   └── chat/          # SesiónChat, Turno
├── application/       # Casos de uso y puertos (interfaces).
│   ├── ports/         # MailboxPort, ChatModelPort, ClassifierPort, SecretsPort, ClockPort...
│   ├── use_cases/     # SincronizarCuenta, ProcesarMensaje, ProbarAgente (playground)...
│   └── policies/      # Umbrales, reglas de escalamiento, aprobación
├── agents/            # Grafo LangGraph del enjambre (orquestación, nodos, herramientas).
│   ├── graph.py       # StateGraph compilado con checkpointer Postgres
│   ├── state.py       # SwarmState (TypedDict / Pydantic)
│   ├── nodes/         # ingestor, guardian, clasificador, enrutador, redactor, webchat
│   └── tools/         # herramientas acotadas (buscar_hilo, crear_borrador, escalar)
├── providers/         # Adaptadores de IA: anthropic, openai, gemini, jev. Registro por nombre.
├── infrastructure/    # Adaptadores técnicos: IMAP/SMTP, SQLAlchemy, cifrado, cola, OTel.
├── api/               # Routers FastAPI, esquemas Pydantic de entrada/salida, dependencias.
├── core/              # Configuración, seguridad, logging, errores.
└── main.py            # Arranque: migraciones automáticas, semillas, app.
```

Reglas de dependencia: `api` y `infrastructure` dependen de `application`; `application` depende de `domain`; `agents` depende de `application` (puertos) y nunca de `infrastructure` directamente. `providers` implementa puertos y se inyecta por el registro.

## 4. El enjambre de agentes

### 4.1 Topología

Se usa un **grafo LangGraph con coordinador explícito y traspasos directos** (híbrido supervisor + swarm, ver ADR-0001):

```
                 ┌──────────┐
   correo/chat ─►│ Ingestor │ (sin LLM: normaliza, deduplica, sanea HTML, extrae adjuntos meta)
                 └────┬─────┘
                      ▼
                 ┌──────────┐   riesgo alto   ┌──────────────┐
                 │ Guardián │────────────────►│ Cuarentena / │──► fin (notifica admin)
                 │ (Jev)    │                 │ Escalamiento │
                 └────┬─────┘                 └──────────────┘
                      ▼ riesgo bajo/medio
                 ┌─────────────┐  confianza < umbral  ┌───────────────────┐
                 │ Clasificador│─────────────────────►│ Clasificador LLM  │
                 │ (Jev)       │                      │ (Haiku, respaldo) │
                 └────┬────────┘                      └─────────┬─────────┘
                      ▼◄────────────────────────────────────────┘
                 ┌──────────┐
                 │ Enrutador│ (reglas + políticas; sin LLM salvo empate)
                 └─┬──┬──┬──┘
       ┌───────────┘  │  └──────────────┐
       ▼              ▼                 ▼
 ┌──────────┐   ┌───────────┐    ┌──────────────┐
 │ Redactor │   │ Extractor │    │ Acción       │
 │ (LLM)    │   │ (Fase 2)  │    │ directa      │ (etiquetar/mover/webhook)
 └────┬─────┘   └───────────┘    └──────────────┘
      ▼
 ┌────────────────┐  interrupt()  ┌──────────────┐
 │ Aprobación     │◄─────────────►│ Operador     │
 │ humana         │               │ (panel)      │
 └────┬───────────┘               └──────────────┘
      ▼
   Enviar (SMTP) / Descartar
```

El **Agente de Webchat** reutiliza Guardián → Clasificador → Enrutador → Redactor, con `canal = "webchat"`, memoria de sesión (checkpointer) y respuesta por streaming. Cuando la política lo permite, responde sin aprobación; si detecta intención sensible, crea un ticket y escala.

### 4.2 Estado compartido

```python
class SwarmState(TypedDict):
    canal: Literal["correo", "webchat"]
    mensaje: MensajeNormalizado          # cuerpo saneado, metadatos, adjuntos (solo metadatos)
    riesgo: RiesgoEvaluado | None        # jailbreak, phishing, inyección, puntajes y fuente
    clasificacion: Clasificacion | None  # categoría, urgencia, requiere_respuesta, idioma, probabilidades
    ruta: str | None                     # agente destino decidido por el enrutador
    borrador: Borrador | None            # asunto, cuerpo, citas, herramientas usadas
    aprobacion: Aprobacion | None        # estado, operador, comentarios
    trazas: list[TrazaLLM]               # proveedor, modelo, tokens, costo, latencia, prompt_version
    errores: list[str]
```

### 4.3 Principios del enjambre

- **Nodos deterministas donde se pueda.** Ingestor y Enrutador no usan LLM. El Guardián y el Clasificador usan Jev (decisión tipada). Solo el Redactor y el Agente de Webchat generan texto.
- **Traspaso por `Command(goto=...)`** con estado explícito. Nada de mensajes libres entre agentes.
- **Herramientas mínimas y de solo lectura por defecto.** El Redactor puede `buscar_hilo`, `consultar_base_conocimiento`, `crear_borrador`. Enviar correo nunca es una herramienta del LLM: lo ejecuta el caso de uso tras aprobación.
- **Checkpointing en PostgreSQL** (`langgraph-checkpoint-postgres`) para reanudar tras `interrupt()` y para depurar en el playground.
- **Cada nodo registra una `TrazaLLM`** con proveedor, modelo, versión de prompt, tokens y costo.

## 5. Capa agnóstica de proveedores

Dos puertos distintos porque son capacidades distintas:

| Puerto | Qué hace | Adaptadores Fase 1 | Adaptadores posteriores |
|---|---|---|---|
| `ChatModelPort` | Generación de texto, herramientas, salida estructurada, streaming | `anthropic` (via `langchain-anthropic` / `init_chat_model`) | `openai`, `gemini` |
| `ClassifierPort` | Responde preguntas tipadas sobre un estado: `Noul`, `Choice`, `Score` | `jev` (`typesafe-sdk`), `llm` (usa cualquier `ChatModelPort` con salida estructurada) | — |

El **registro de proveedores** resuelve `"anthropic:claude-opus-5-5"`, `"openai:gpt-4o-mini"`, `"gemini:gemini-2.5-flash"`, `"jev:jev-latest"`. La UI lista modelos disponibles por proveedor (`GET /providers/{p}/models`) consultando la API del proveedor cuando existe (`/v1/models`).

Detalles en `05-agentes-y-proveedores.md` y ADR-0002 / ADR-0003.

## 6. Flujo de un correo (secuencia)

1. `worker` mantiene una conexión IMAP IDLE por cuenta (o polling cada N s si el servidor no soporta IDLE).
2. Al llegar un UID nuevo, descarga cabeceras + cuerpo, calcula `hash_contenido`, inserta `mensajes` en estado `recibido` y encola trabajo `procesar_mensaje` (misma transacción → outbox).
3. Un worker toma el trabajo con `SELECT ... FOR UPDATE SKIP LOCKED`, invoca el grafo con `thread_id = mensaje.id`.
4. Cada nodo persiste su resultado en tablas de dominio (`clasificaciones`, `ejecuciones_agente`, `llamadas_llm`) además del checkpoint.
5. Si el enrutador decide "responder", el Redactor produce un borrador y el grafo se detiene en `interrupt()`; el panel muestra el borrador en "Pendientes de aprobación".
6. El operador aprueba/edita → `POST /runs/{id}/resume` → el caso de uso envía por SMTP, marca el correo en IMAP (`\Seen`, etiqueta `$AgenteProcesado`) y cierra la ejecución.
7. Métricas y trazas se exportan por OTel; el dashboard lee agregados de PostgreSQL.

## 7. Flujo del webchat

1. El widget abre `WSS /ws/chat` con un token de sesión anónimo firmado (sin PII).
2. Cada turno entra por Guardián (Jev, < 200 ms) antes del LLM.
3. El Agente de Webchat responde con streaming (`astream_events`), con herramientas de solo lectura.
4. Si la intención es "hablar con humano" o el riesgo es alto, se crea un ticket y se corta la generación automática.
5. La sesión se persiste con TTL configurable; el operador puede verla en el panel.

## 8. Arranque automático de la base de datos (ADR-0004, ADR-0008, ADR-0010)

El bootstrap es el comando idempotente `python -m app.bootstrap`. En Compose lo ejecuta el servicio one-shot `migrador` con las credenciales de `agente_migrador`; `api` y `worker` arrancan después (`service_completed_successfully`) y se conectan como `agente_app`, sin privilegios DDL. En desarrollo lo ejecuta `make dev` (`make bootstrap`).

1. Espera a que PostgreSQL acepte conexiones (backoff exponencial, máx. `DB_ESPERA_MAX_S`, 60 s por defecto).
2. Si la base indicada no existe y `DB_AUTO_CREATE=true` (prohibido con `ENV=production`), se conecta a `postgres` y ejecuta `CREATE DATABASE`.
3. Toma `pg_try_advisory_lock(0xA6E17E)` con reintentos hasta `DB_BOOTSTRAP_LOCK_TIMEOUT_S` para que un solo proceso migre.
4. Ejecuta `alembic upgrade head` de forma programática (driver psycopg): extensiones, esquemas `langgraph` y `procrastinate`, tablas propias y esquema versionado de procrastinate.
5. Ejecuta `AsyncPostgresSaver.setup()` en el esquema `langgraph` y concede privilegios al rol de aplicación.
6. Con `DB_ROLES_SEPARADOS=true` (obligatorio en producción), verifica que el rol de la aplicación no es superusuario, no tiene DDL ni `UPDATE`/`DELETE` sobre `auditoria`; si no, falla cerrado.
7. Siembra datos mínimos idempotentes: roles, usuario admin inicial si `usuarios` está vacía (contraseña aleatoria escrita una sola vez en `stderr`, fuera del log estructurado, si no se define `ADMIN_INITIAL_PASSWORD`; cambio obligatorio en el primer login), proveedores deshabilitados, taxonomía base, agentes por defecto con su prompt v1 publicado y configuración por defecto. Cada inserción efectiva deja auditoría.
8. Libera el lock y termina con código 0 (1 configuración inválida, 2 fallo de bootstrap).

La readiness (`/api/v1/salud/listo`) incluye la sonda `migraciones`: `alembic_version` de la base debe coincidir con la revisión `head` del código.

## 9. Decisiones registradas (ADR)

| ADR | Decisión |
|---|---|
| 0001 | LangGraph como motor de orquestación; LangChain solo para abstracción de modelos. |
| 0002 | Capa de proveedores agnóstica con dos puertos (`ChatModelPort`, `ClassifierPort`). |
| 0003 | Jev como clasificador primario con respaldo LLM económico y umbrales de confianza. |
| 0004 | PostgreSQL única dependencia; auto-creación, migración y cola nativa. |
| 0005 | Angular 22 zoneless + signals + Angular Material + Tailwind con tokens Viamatica. |
| 0006 | Secretos con cifrado envelope (AES-256-GCM) y clave maestra fuera de la base. |
| 0007 | Configuración validada con pydantic-settings: fallo cerrado en producción, sin eco de valores en errores, `extra="ignore"` y fábrica `crear_app`. |
| 0008 | Bootstrap de BD como comando dedicado (`python -m app.bootstrap`, servicio `migrador`), roles separados obligatorios en producción, `DB_AUTO_CREATE` prohibido en producción, admin inicial con contraseña mostrada una vez en `stderr`. |
| 0009 | Auditoría append-only con `secuencia`, hash encadenado calculado por trigger, triggers de inmutabilidad y `REVOKE` al rol de aplicación. |
| 0010 | procrastinate en esquema `procrastinate` versionado por Alembic (SQL copiado), checkpointer en esquema `langgraph` vía `setup()`, bootstrap con driver psycopg y privilegios explícitos por esquema. |
| 0011 | Pruebas de integración con PostgreSQL efímero: `PRUEBAS_PG_DSN`, Docker (testcontainers) o binarios locales con clúster temporal; nunca `skip`. |
