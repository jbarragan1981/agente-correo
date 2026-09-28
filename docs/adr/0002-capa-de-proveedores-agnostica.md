# ADR-0002 · Capa de proveedores agnóstica con dos puertos

**Estado:** Aceptada · 2026-09-28

## Contexto
El sistema debe funcionar con Anthropic, OpenAI, Gemini y TypeSafe Jev, empezando por Anthropic + Jev, y el panel debe permitir cambiar proveedor y modelo por agente sin desplegar. Jev es un modelo de decisión (preguntas tipadas → probabilidades), distinto de un chat model.

## Decisión
Definir dos puertos en `application/ports`: `ChatModelPort` (generar, generar_estructurado, stream, herramientas) y `ClassifierPort` (decidir sobre `Noul/Choice/Score`). Un `ProviderRegistry` resuelve referencias `proveedor:modelo`. `LLMClasificador` implementa `ClassifierPort` sobre cualquier `ChatModelPort`, así cualquier LLM puede sustituir a Jev. Los precios y capacidades por modelo viven en configuración, editables desde el panel.

## Alternativas descartadas
- Un único puerto "modelo" con métodos opcionales: obliga a `if proveedor == ...` en el dominio.
- LiteLLM/OpenRouter como proxy universal: añade un salto de red y un tercero con acceso a los datos; puede ofrecerse como proveedor adicional (`openrouter`) sin cambiar el diseño.

## Consecuencias
- (+) Añadir un proveedor es crear un adaptador y pruebas de contrato (skill `proveedor-llm`).
- (+) El playground y el selector de modelos son genéricos.
- (−) Las funciones exclusivas de un proveedor (p. ej. `fallbacks` de Anthropic, caché de prompt) se exponen como `capacidades` opcionales y se degradan con elegancia en los demás.
