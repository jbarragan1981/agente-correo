---
name: jev-clasificador
description: >-
  Uso de TypeSafe Jev (typesafe-sdk, langchain-typesafe) como clasificador y guardián en Agente Correo: contrato de System One, tipos Noul/Choice/Score, construcción del estado desde un correo, generación de preguntas desde la taxonomía, interpretación de probabilidades y confianza, umbrales y respaldo con LLM, costos, límites y pruebas. Úsalo al tocar providers/jev, el Guardián, el Clasificador o las preguntas de un agente de decisión.
---

# Jev (TypeSafe AI) en Agente Correo

## Contrato
- Endpoint: `POST https://api.typesafe.ai/v1/systemone` · Auth `Authorization: Bearer $TYPESAFE_API_KEY` · modelo `jev-latest` (`GET /v1/models` lista alias).
- Body: `{"model": "jev-latest", "state": <str | objeto | lista JSON>, "questions": {"<nombre>": <pregunta>}}`.
- Preguntas:
  - `{"type":"noul","instructions":"¿…?","criteria":{"true":"…","false":"…"}}` → `{"type":"noul","noul":0.98}` (probabilidad de sí).
  - `{"type":"choice","instructions":"…","criteria":{"etiqueta":"descripción"|null,…}}` → `{"type":"choice","choice":"etiqueta","confidence":0.9,"probabilities":{…}}`.
  - `{"type":"score","instructions":"…","criteria":["nivel 0","nivel 1",…]}` → `{"type":"score","score":1.7,"confidence":0.9,"legend":{"0":"…"},"probabilities":{"0":0.1,…}}`.
- Respuesta: `{"model": "...", "usage": {"input_tokens": n, "output_tokens": m}, "answers": {...}}`. Salida gratuita; entrada USD 0,042 / M tokens.
- Límites publicados: 64K de contexto (≈32K para el estado), 1.200 req/min. Latencia típica ~0,1 s. Solo texto.
- SDK: `typesafe-sdk>=0.7` (`TypeSafeClient`/`AsyncTypeSafeClient`, `Noul`, `Choice`, `Score`, `NoulCriteria`, `RetryPolicy`, errores `TypeSafeRateLimitError`, `TypeSafeAPITimeoutError`, `TypeSafeAPIConnectionError`, `TypeSafeBadRequestError`). Variables: `TYPESAFE_API_KEY`, `TYPESAFE_BASE_URL`, `TYPESAFE_DEFAULT_MODEL`. Timeout por defecto 10 s; usar 5 s en el guardián.

```python
from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, Score, RetryPolicy
async with AsyncTypeSafeClient(api_key=clave, model="jev-latest", timeout=5.0, retry=RetryPolicy(max_retries=2)) as c:
    r = await c.system_one(state={"asunto": asunto, "remitente": remitente, "cuerpo": cuerpo},
                           questions={"categoria": Choice(instructions="¿De qué trata?", criteria={"soporte": "Fallas técnicas", "facturacion": "Pagos y facturas", "otro": None}),
                                      "urgencia": Score(instructions="¿Qué tan pronto requiere atención?", criteria=["Puede esperar", "Esta semana", "Hoy"]),
                                      "requiere_respuesta": Noul(instructions="¿El remitente espera respuesta?")})
    r.choices["categoria"].choice, r.choices["categoria"].confidence, r.scores["urgencia"].score, r.nouls["requiere_respuesta"].noul, r.usage.input_tokens
```

## Construir el estado desde un correo
Enviar JSON estructurado, no texto plano concatenado: `{"remitente": {"nombre","direccion","dominio"}, "asunto", "fecha", "cuerpo": <texto saneado y recortado>, "urls": [dominios], "adjuntos": [{"nombre","mime"}], "autenticacion": {"spf","dkim","dmarc"}, "hilo": {"es_respuesta": bool, "ultimo_turno": "..."}}`. Recorte: máx. 12.000 caracteres del cuerpo, conservando las primeras 8.000 y las últimas 4.000; eliminar firmas repetidas y citas de hilos anteriores (regex `^>` y "El … escribió:"). Nunca enviar adjuntos ni HTML crudo.

## Preguntas desde la taxonomía
`application/use_cases/generar_preguntas_clasificador.py`: para cada `categoria` activa → entrada en `criteria` de la `Choice` `categoria` con `descripcion_para_modelo` (o `None`). Añadir siempre `otro: None`. Preguntas fijas: `urgencia` (Score de 3 niveles), `requiere_respuesta` (Noul), `idioma` (Choice). Guardar como nueva `versiones_prompt.preguntas_jev` y pedir publicación. Escribir descripciones en la misma lengua de los correos predominantes y con criterios contrastantes (qué sí y qué no).

## Interpretación y umbrales
- Categoría ganadora = `choice`; `confianza = confidence`. Regla de respaldo: `confidence < umbral_categoria` **o** `top1 - top2 < 0,15` → `LLMClasificador`.
- Urgencia: `score` esperado (0..2) → `alta` si ≥ 1,5, `media` si ≥ 0,75.
- Noul: umbral 0,6 para "requiere respuesta"; para riesgo (`jailbreak`, `phishing`) umbral 0,5 y cualquier ≥ 0,8 → `alto`.
- Guardar `probabilities` completo en `clasificaciones.probabilidades` para el panel.

## Guardián: Jev + reglas deterministas
Jev es susceptible a texto diseñado para desplazar su respuesta. Siempre combinar: `riesgo_final = max(jev_score, reglas)`. Reglas mínimas en `application/policies/riesgo.py`: SPF/DKIM/DMARC fail; dominio de remitente ≠ dominio de URLs de la firma; URL acortada o con punycode; adjunto `.exe/.js/.html/.iso/.lnk`; patrones (`ignore (all )?previous`, `system prompt`, `you are now`, secuencias base64 > 200 chars, texto con `color:#fff`/`font-size:0` en el HTML original). Registrar qué regla disparó.

## Costo
`costo_usd = input_tokens × 0.042 / 1_000_000`. Un correo típico (~1,5K tokens de estado + preguntas) ≈ USD 0,00008. Métrica `ia_costo_usd_total{proveedor="jev"}`.

## Errores
Mapear: `TypeSafeRateLimitError` → reintento con `retry-after` (máx. 2) → respaldo LLM; `TypeSafeAPITimeoutError`/`ConnectionError` → respaldo LLM y métrica `correo_respaldo_llm_total{motivo="jev_no_disponible"}`; `TypeSafeBadRequestError` (estado demasiado grande, pregunta inválida) → recortar y reintentar una vez, luego error de ejecución (bug de construcción, no de red).

## Pruebas
- Unitarias: `construir_estado_jev`, `interpretar`, `necesita_respaldo` con tablas de casos.
- Contrato: `respx` sobre `https://api.typesafe.ai/v1/systemone` con cassettes en `tests/cassettes/jev/*.json` (respuestas reales anonimizadas); verificar cabecera `Authorization` y cuerpo.
- Adversariales: fixtures `tests/fixtures/correos/adversarial_*.eml`; el Guardián debe marcar `alto` aunque Jev devuelva bajo (por reglas).
- Evals: `evals/clasificador.py` calcula exactitud, matriz de confusión, recall/FP de riesgo y costo medio; falla si exactitud < 0,92.
