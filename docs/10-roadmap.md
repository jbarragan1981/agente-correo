# 10 · Roadmap y plan de construcción

Cada épica se ejecuta con el flujo de orquestación de Claude Code (`/orquestar <épica>`): el agente **arquitecto** desglosa y decide, **backend** y **frontend** implementan en paralelo, **qa** prueba, **seguridad** revisa y se abre el PR.

## Fase 0 · Cimientos (semana 1)

| # | Épica | Entregable | Agentes |
|---|---|---|---|
| E0.1 ✅ | Esqueleto backend | `uv` project, FastAPI, settings, logging, salud, Dockerfile, Compose con PostgreSQL | backend |
| E0.2 ✅ | Base de datos autoconfigurable | Bootstrap (crear BD, advisory lock, Alembic programático, semillas), modelos SQLAlchemy de `03-modelo-de-datos.md` | backend, qa |
| E0.3 | Autenticación y RBAC | login/refresh/logout, Argon2id, roles, auditoría base, rate limit | backend, seguridad |
| E0.4 ✅ | Esqueleto frontend | Angular 22 zoneless, shell Viamatica, tokens, login, guards, cliente OpenAPI | frontend |
| E0.5 | CI | Workflows de lint, pruebas, seguridad | qa |

## Fase 1 · MVP (semanas 2–6)

| # | Épica | Entregable | Agentes |
|---|---|---|---|
| E1.1 | Capa de proveedores | Puertos, registro, adaptador Anthropic, adaptador Jev, clasificador LLM de respaldo, proveedores falsos, precios y costo | backend, qa |
| E1.2 | Gestión de secretos | Cifrado envelope, credenciales de proveedor, endpoints de proveedores y prueba | backend, seguridad |
| E1.3 | Cuentas de correo | CRUD, cifrado, prueba de conexión, sync IMAP IDLE/polling, cola con procrastinate, outbox | backend, qa |
| E1.4 | Enjambre v1 | Grafo LangGraph: Ingestor, Guardián, Clasificador, Enrutador, checkpointer; acciones (etiquetar/mover/webhook/cuarentena) | backend, qa |
| E1.5 | Agentes y prompts | CRUD de agentes, versiones, publicación, preguntas Jev, taxonomía → preguntas | backend, frontend |
| E1.6 | Redactor + aprobación | Nodo Redactor con herramientas de solo lectura, `interrupt()`, borradores, aprobar/editar/rechazar, envío SMTP | backend, frontend, seguridad |
| E1.7 | Panel: bandeja y aprobaciones | Bandeja virtualizada, detalle con explicación, cola de aprobación con editor | frontend, qa |
| E1.8 | Panel: agentes y playground | Editor de prompt con versiones/diff/linter, selector de modelos, playground con streaming y comparación | frontend, backend |
| E1.9 | Panel: cuentas, taxonomía, proveedores, usuarios | Formularios Signal Forms, prueba de conexión, acciones drag & drop | frontend |
| E1.10 | Observabilidad | OTel, métricas, vistas materializadas, endpoints `/metricas`, dashboard ECharts, auditoría | backend, frontend |
| E1.11 | Webchat | Endpoint WS, agente de webchat con streaming, widget embebible, sesiones en el panel, tomar control | backend, frontend, seguridad |
| E1.12 | Evaluación y endurecimiento | Dataset de 300 correos, evals en CI, pruebas adversariales, ZAP, Trivy, checklist de producción | qa, seguridad |

## Fase 2 · Expansión (semanas 7–12)

OAuth2 Gmail API y Microsoft Graph · adaptadores OpenAI y Gemini con pruebas de contrato · Agente Extractor con salida estructurada · Agente Evaluador y evaluación automática antes de publicar prompts · MFA y SSO OIDC · envío automático por políticas · multi-tenant · Helm chart · rotación de clave maestra con KMS.

## Hitos

| Hito | Criterio |
|---|---|
| M0 · Arranca solo | `docker compose up` → BD creada, migrada, admin listo, panel responde. |
| M1 · Clasifica | Una cuenta real de prueba recibe correos y aparecen clasificados con explicación en < 3 s. |
| M2 · Responde con aprobación | Un correo de soporte genera borrador, el operador lo aprueba y se envía. |
| M3 · Configurable | Cambiar prompt/modelo desde el panel altera el comportamiento sin reinicio; playground funcional. |
| M4 · Observable y seguro | Dashboard con costos y latencias; checklist de producción completa; evals ≥ metas. |
| M5 · Webchat | Widget en un sitio de prueba conversando con el enjambre y escalando a operador. |
