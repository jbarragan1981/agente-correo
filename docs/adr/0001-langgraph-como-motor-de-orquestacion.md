# ADR-0001 · LangGraph como motor de orquestación del enjambre

**Estado:** Aceptada · 2026-09-28

## Contexto
Necesitamos un enjambre de agentes con nodos deterministas y generativos, aprobación humana (pausar/reanudar), trazabilidad por paso, streaming hacia el webchat y persistencia del estado en PostgreSQL. Las opciones evaluadas: LangGraph (grafo de estado), LangChain "agents" de alto nivel, `langgraph-supervisor`/`langgraph-swarm`, un orquestador propio sobre el SDK de Anthropic, y Managed Agents de Anthropic.

## Decisión
Usar **LangGraph 1.x** con un `StateGraph` propio: coordinador explícito (Enrutador determinista) y traspasos con `Command(goto=...)` al estilo swarm donde un agente deba ceder control. LangChain se usa solo por `init_chat_model` y `langchain-typesafe`. No se adoptan `langgraph-supervisor` ni `langgraph-swarm` como núcleo (están en 0.x y asumen que todos los agentes son LLM con herramientas); sus patrones sí se replican. Managed Agents queda descartado porque el proveedor debe ser intercambiable y los datos de correo deben quedarse en la infraestructura del cliente.

## Consecuencias
- (+) `interrupt()`/`resume` resuelven el human-in-the-loop; `AsyncPostgresSaver` reutiliza la misma base.
- (+) Cada nodo es una función probada de forma aislada; el grafo se prueba con proveedores falsos.
- (+) `astream_events` alimenta el streaming del webchat y del playground.
- (−) Curva de aprendizaje del equipo en LangGraph; mitigada con el skill `langgraph-agentes`.
- (−) Dependencia de la versión mayor 1.x de LangGraph/LangChain; se fija con límites `<2`.
