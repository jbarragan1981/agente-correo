---
name: proveedor-llm
description: Añadir o modificar un proveedor de IA en Agente Correo (Anthropic, OpenAI, Gemini, Jev u otro) respetando los puertos ChatModelPort y ClassifierPort, el registro de proveedores, precios, capacidades, manejo de errores, caché de prompt, streaming, salida estructurada y pruebas de contrato con respuestas grabadas. Úsalo al tocar backend/app/providers/.
---

# Proveedores de IA

Referencias: `docs/05-agentes-y-proveedores.md`, ADR-0002. Los SDKs de proveedores solo se importan dentro de `backend/app/providers/`.

## Puertos (no los cambies sin ADR)
- `ChatModelPort`: `generar(PeticionChat) -> RespuestaChat`, `generar_estructurado(PeticionChat, esquema) -> BaseModel`, `stream(PeticionChat) -> AsyncIterator[EventoChat]`.
- `ClassifierPort`: `decidir(estado, preguntas) -> Decision`.
- `PeticionChat`: `sistema: list[BloqueSistema]` (bloques con `cacheable: bool`), `mensajes`, `herramientas`, `max_tokens`, `effort`, `metadatos` (agente, ejecución). Sin campos específicos de un proveedor: eso va en `parametros_proveedor: dict` validado por el adaptador.
- `RespuestaChat`: `texto`, `bloques`, `llamadas_herramienta`, `stop_reason` (`fin`|`herramienta`|`max_tokens`|`refusal`|`otro`), `uso` (`tokens_entrada`, `tokens_salida`, `tokens_cache_lectura`, `tokens_cache_escritura`), `modelo`, `request_id`, `latencia_ms`, `costo_usd`.

## Pasos para un proveedor nuevo
1. `providers/<nombre>/proveedor.py`: clase `<Nombre>Proveedor(ChatModelPort)` con `@classmethod crear(modelo, credenciales, config)`. Usa `langchain_<nombre>` vía `init_chat_model(f"<nombre>:{modelo}")` para herramientas/streaming; usa el SDK oficial directamente solo para capacidades que LangChain no exponga.
2. `providers/<nombre>/errores.py`: mapea excepciones del SDK a `ErrorProveedor(tipo=rate_limit|timeout|auth|peticion_invalida|refusal|servidor, reintentable: bool, retry_after_s)`.
3. `providers/precios.yaml`: `<nombre>: {<modelo>: {entrada: usd/M, salida: usd/M, cache_lectura: usd/M}}`. El cálculo de `costo_usd` vive en `providers/costos.py` (común).
4. `providers/capacidades.py`: declara `streaming, herramientas, salida_estructurada, cache_prompt, decision_tipada, vision`.
5. `providers/registry.py`: añade al `REGISTRO`. Extra opcional en `pyproject.toml` (`[project.optional-dependencies].<nombre>`). Import perezoso: si falta el paquete, el proveedor aparece como "no instalado" en `/proveedores`.
6. `providers/<nombre>/modelos.py`: `listar_modelos(credenciales)` para `GET /proveedores/<nombre>/modelos` (caché 1 h) y validación al guardar un agente.
7. Pruebas de contrato `tests/contrato/test_<nombre>.py` parametrizadas con la suite común `suite_chat_model_port` (generar, estructurado, stream, herramienta, error 429, error auth, refusal) usando `respx` y cassettes en `tests/cassettes/<nombre>/`.
8. Documenta en `docs/05-agentes-y-proveedores.md` §2 el adaptador y sus particularidades.

## Anthropic (referencia de implementación)
- SDK `anthropic>=1.9`; modelos actuales: `claude-opus-5-5` (por defecto para agentes generativos), `claude-sonnet-5-5`, `claude-haiku-4-5` (respaldo del clasificador). Nunca añadir sufijos de fecha.
- Modelos 4.6+: `thinking={"type":"adaptive"}`; profundidad con `output_config={"effort": "low|medium|high|xhigh|max"}`; sin `budget_tokens`, sin prefill del asistente, sin `tool_choice` `any`/`tool` (usar `auto` + instrucción + `strict: true`). Haiku 4.5: omitir `thinking` (o `budget_tokens` si se activa) y sin `effort`.
- Salida estructurada: `output_config={"format": {...}}` (o `client.messages.parse`) para el clasificador LLM y el borrador del Redactor.
- Caché de prompt: bloques de sistema estables primero (`cache_control: {"type": "ephemeral"}`), contenido volátil (correo) al final; verificar `usage.cache_read_input_tokens` en pruebas.
- Refusals: `betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"`; si aun así `stop_reason == "refusal"`, devolver `ErrorProveedor(tipo="refusal", reintentable=False)`.
- Streaming: `client.messages.stream(...)` para respuestas largas y para el webchat; `eager_input_streaming: true` en herramientas cliente cuando se hace streaming.
- Errores: `RateLimitError` → reintentable con `retry-after`; `APIStatusError` 5xx → reintentable; 4xx → no; `APIConnectionError`/timeout → reintentable.

## OpenAI / Gemini (Fase 2)
Misma plantilla con `langchain-openai` / `langchain-google-genai`. Modelos económicos de referencia para el respaldo: `gpt-4o-mini`, `gemini-2.5-flash`. Salida estructurada con `with_structured_output(esquema, method="json_schema")`. Registrar límites específicos (tamaño de sistema, herramientas paralelas) en `capacidades`.

## Reglas
- Ningún adaptador lee variables de entorno: recibe `credenciales` desde `SecretsPort`.
- Reintentos con `tenacity` (máx. 2, backoff exponencial con jitter, respeta `retry_after_s`), pero solo cuando `reintentable=True`.
- Todo adaptador emite span OTel `ia.llamada` con atributos `proveedor, modelo, tokens_*, costo_usd, stop_reason` y contador de errores.
- El adaptador nunca registra el contenido del prompt ni la respuesta en logs; solo metadatos.
