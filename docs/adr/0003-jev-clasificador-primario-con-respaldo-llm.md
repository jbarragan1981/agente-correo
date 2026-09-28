# ADR-0003 · Jev como clasificador primario con respaldo LLM y umbrales

**Estado:** Aceptada · 2026-09-28

## Contexto
Clasificar cientos o miles de correos al día con un LLM generativo cuesta y tarda (referencia publicada: ~8,5 s y USD 0,014 por correo) frente a Jev (~0,11 s y USD 0,00008). Jev devuelve probabilidades calibradas y `confidence`, pero TypeSafe documenta que texto diseñado para manipularlo puede desplazar la respuesta.

## Decisión
1. Guardián y Clasificador usan **Jev** (`jev:jev-latest`) por defecto, con una sola llamada que agrupa todas las preguntas del agente.
2. Umbral de confianza por categoría (default 0,70) y regla de margen (top1 − top2 ≥ 0,15). Si no se cumplen, o Jev falla/agota reintentos, se invoca el **clasificador LLM de respaldo** (`anthropic:claude-haiku-4-5` por defecto, sustituible por `openai:gpt-4o-mini` o `gemini:gemini-2.5-flash`).
3. El Guardián combina Jev con verificaciones deterministas (SPF/DKIM/DMARC, dominios, URLs, patrones de inyección) tomando el máximo riesgo.
4. Todo resultado guarda `motor` (`jev`|`llm`) y probabilidades para medir precisión y costo por motor.
5. El estado enviado a Jev se recorta a ~12K caracteres priorizando asunto, primeras líneas y última respuesta.

## Consecuencias
- (+) Costo por correo dominado por Jev; el LLM solo en casos ambiguos (meta < 15 % de los correos).
- (+) Cambiar Jev por Haiku/GPT es cambiar el modelo del agente en el panel.
- (−) Dos motores implican dos comportamientos; se controla con el dataset de evaluación y la métrica de "respaldo LLM".
- (−) Dependencia de un proveedor joven (SDK 0.7); mitigada por el puerto y el respaldo automático.
