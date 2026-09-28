# 00 · Visión y alcance del producto

**Proyecto:** Agente Correo · Sistema multiagente de correo electrónico y webchat
**Cliente / marca:** Viamatica
**Versión del documento:** 1.0 · 2026-09-28
**Estado:** Aprobado para construcción (Fase 0 → Fase 1)

---

## 1. Problema

Los buzones corporativos reciben cientos de correos diarios mezclando solicitudes de clientes, facturas, soporte, spam, phishing e intentos de manipulación. Hoy la clasificación y priorización es manual, lenta y sin trazabilidad. El webchat corporativo vive aparte del correo, con reglas duplicadas.

## 2. Solución

Una plataforma que conecta una o varias cuentas de correo y un canal de webchat a un **enjambre de agentes** que:

1. Ingesta cada mensaje y lo trata como **dato no confiable**.
2. Lo pasa por un **guardián** que detecta jailbreak, prompt injection y phishing.
3. Lo **clasifica** con un modelo de decisión (Jev) barato, rápido y calibrado, con respaldo en un LLM económico (Claude Haiku 4.5 o equivalente).
4. Lo **enruta** al agente especializado correcto (respuesta, extracción, escalamiento humano).
5. Redacta **borradores de respuesta** que un operador aprueba desde el panel (human-in-the-loop por defecto).
6. Expone un **panel Angular** con dashboard de observabilidad, configuración de agentes (prompt, modelo, proveedor), playground y gestión de cuentas de correo.

El enjambre es **agnóstico al proveedor de IA**: Anthropic, OpenAI, Google Gemini y TypeSafe Jev se intercambian por configuración sin tocar código de negocio. La primera entrega se construye sobre Anthropic + Jev.

## 3. Objetivos medibles (Fase 1)

| Objetivo | Métrica | Meta |
|---|---|---|
| Clasificación automática | % de correos clasificados sin intervención | ≥ 95 % |
| Precisión de categoría | exactitud contra set etiquetado (≥ 300 correos) | ≥ 92 % |
| Costo por correo clasificado | USD por correo (Jev) | ≤ 0,0005 |
| Latencia de clasificación | p95 desde recepción hasta etiqueta | ≤ 3 s |
| Detección de jailbreak/phishing | recall sobre set adversarial | ≥ 90 % con falsos positivos ≤ 5 % |
| Tiempo de configuración de cuenta | desde el panel hasta el primer correo procesado | ≤ 5 min |
| Arranque limpio | `docker compose up` crea la base de datos y migra sin pasos manuales | 100 % |

## 4. Usuarios y roles

| Rol | Qué hace |
|---|---|
| **Administrador** | Configura cuentas de correo, proveedores de IA, usuarios y políticas. Ve todo. |
| **Operador** | Trabaja la bandeja: revisa clasificaciones, aprueba o edita borradores, escala casos. |
| **Auditor** | Solo lectura: dashboard, trazas, costos, registro de auditoría. |
| **Visitante de webchat** | Usuario externo que conversa con el agente desde el widget. Sin acceso al panel. |

## 5. Alcance funcional

### 5.1 Incluido en Fase 1 (MVP productivo)

- Conexión a **N cuentas de correo** vía IMAP (IDLE + polling de respaldo) y SMTP para envío. Gmail y Microsoft 365 con contraseña de aplicación; OAuth2 en Fase 2.
- Enjambre de agentes: Ingestor, Guardián, Clasificador, Enrutador, Redactor, Agente de Webchat.
- Clasificador con **Jev** (`jev-latest`) como motor principal y **LLM de respaldo** configurable (por defecto `claude-haiku-4-5`).
- Taxonomía de clasificación configurable desde el panel (categorías, umbrales, acciones: etiquetar, mover, marcar, notificar webhook, escalar).
- Panel Angular con: login, dashboard de observabilidad, bandeja clasificada, detalle de correo con explicación de la decisión, gestión de agentes (crear, editar prompt y modelo, versionar, activar/desactivar), **playground** por agente, gestión de cuentas de correo, usuarios y auditoría.
- Webchat: endpoint WebSocket + widget embebible Angular que conversa con el mismo enjambre.
- Observabilidad: trazas por ejecución de agente, tokens y costo por llamada, latencias, tasa de error, métricas OpenTelemetry, logs estructurados.
- **Seguridad por defecto** (ver `07-seguridad.md`): secretos cifrados en reposo, RBAC, JWT + refresh rotativo, rate limiting, CSP, correos tratados como datos no confiables, aprobación humana antes de enviar.
- PostgreSQL como única dependencia de infraestructura. La base se crea y migra sola en el primer arranque.

### 5.2 Fase 2

- OAuth2 para Gmail API y Microsoft Graph (sin contraseñas).
- Agente Extractor (facturas, órdenes, tickets) con salida estructurada.
- Agente Evaluador (LLM como juez muestral) y bucle de mejora de prompts con dataset etiquetado.
- SSO corporativo (OIDC: Entra ID / Google Workspace).
- Envío automático sin aprobación para categorías de bajo riesgo, con políticas.
- Multi-tenant (varias organizaciones en una instalación).

### 5.3 Fuera de alcance

- Cliente de correo completo (redacción libre, calendario, contactos).
- Entrenamiento de modelos propios.
- Canales distintos de correo y webchat (WhatsApp, Teams) en esta etapa.

## 6. Requisitos no funcionales

| Área | Requisito |
|---|---|
| Disponibilidad | 99,5 % mensual en Fase 1 (un nodo + PostgreSQL con respaldo diario). |
| Escalabilidad | Horizontal por proceso: API y workers separables; cola sobre PostgreSQL (`SKIP LOCKED`) sin Redis en MVP. |
| Rendimiento | 10 correos/s sostenidos por worker; webchat con respuesta inicial por streaming < 1,5 s. |
| Portabilidad | Docker Compose para on-premise y nube; sin dependencia de servicios gestionados propietarios. |
| Cumplimiento | Datos personales en correos: minimización, retención configurable, borrado por cuenta, registro de auditoría inmutable. |
| Idioma | Interfaz y prompts en español; el clasificador soporta español e inglés. |
| Accesibilidad | WCAG 2.1 AA en el panel. |

## 7. Principios de diseño

1. **Correo = entrada hostil.** Nada que llegue por correo o webchat se interpreta como instrucción para un agente.
2. **Decisiones baratas primero.** Jev decide en milisegundos; el LLM solo entra cuando hace falta generar texto o la confianza es baja.
3. **Proveedor intercambiable.** Puertos y adaptadores: el dominio no importa `anthropic`, `openai` ni `typesafe_sdk`.
4. **Humano en el bucle por defecto.** Enviar, borrar o escalar requiere aprobación hasta que una política lo relaje.
5. **Todo trazable.** Cada decisión guarda entrada, versión de prompt, modelo, probabilidades, costo y quién aprobó.
6. **Arranque en un comando.** Sin pasos manuales de base de datos ni semillas a mano.
7. **Seguro por defecto.** Deny-by-default en permisos, CORS, herramientas de agentes y red.

## 8. Glosario

- **Enjambre (swarm):** conjunto de agentes especializados que se pasan el control entre sí bajo un grafo de estado compartido.
- **Jev / System One:** modelo de decisión de TypeSafe AI que responde preguntas tipadas (sí/no, opción, puntaje) con probabilidades calibradas, sin generar texto.
- **Noul / Choice / Score:** los tres tipos de pregunta de Jev.
- **Guardián:** agente que evalúa riesgo (jailbreak, phishing, inyección) antes de que el contenido llegue a cualquier LLM con herramientas.
- **Playground:** vista del panel para probar un agente con una entrada arbitraria y ver la traza completa.
