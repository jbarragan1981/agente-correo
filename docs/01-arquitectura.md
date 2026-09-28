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

## 8. Arranque automático de la base de datos (ADR-0004)

Al iniciar `api` o `worker`:

1. Espera a que PostgreSQL acepte conexiones (backoff exponencial, máx. 60 s).
2. Si la base indicada en `DATABASE_URL` no existe y `DB_AUTO_CREATE=true`, se conecta a `postgres` y ejecuta `CREATE DATABASE`.
3. Toma un advisory lock (`pg_advisory_lock(0xA6E17E)`) para que un solo proceso migre.
4. Ejecuta `alembic upgrade head` de forma programática.
5. Ejecuta el setup del checkpointer de LangGraph (`AsyncPostgresSaver.setup()`).
6. Siembra datos mínimos idempotentes: roles, usuario admin inicial (contraseña generada y mostrada una sola vez en logs si no se define `ADMIN_INITIAL_PASSWORD`), agentes por defecto con sus prompts v1, taxonomía base.
7. Libera el lock y arranca.

## 9. Decisiones registradas (ADR)

| ADR | Decisión |
|---|---|
| 0001 | LangGraph como motor de orquestación; LangChain solo para abstracción de modelos. |
| 0002 | Capa de proveedores agnóstica con dos puertos (`ChatModelPort`, `ClassifierPort`). |
| 0003 | Jev como clasificador primario con respaldo LLM económico y umbrales de confianza. |
| 0004 | PostgreSQL única dependencia; auto-creación, migración y cola nativa. |
| 0005 | Angular 22 zoneless + signals + Angular Material + Tailwind con tokens Viamatica. |
| 0006 | Secretos con cifrado envelope (AES-256-GCM) y clave maestra fuera de la base. |
