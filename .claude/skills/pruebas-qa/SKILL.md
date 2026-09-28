---
name: pruebas-qa
description: >-
  Cómo escribir y ejecutar pruebas en Agente Correo: pytest (unitarias, contrato con respx y cassettes, integración con testcontainers PostgreSQL 17 y GreenMail, API con httpx, grafo LangGraph con proveedores falsos), Vitest para Angular zoneless, Playwright e2e con proveedores falsos, evaluaciones del clasificador con dataset etiquetado, fixtures adversariales, cobertura y convenciones. Úsalo al añadir pruebas, reproducir defectos o preparar datos de prueba.
---

# Pruebas y calidad

Referencia: `docs/09-testing-y-calidad.md`.

## Backend (pytest)
Estructura `backend/tests/{unit,contrato,integracion,api,agentes}/`, `conftest.py` raíz con:
- `settings_prueba` (`ENV=test`, `FAKE_PROVIDERS=true`, `APP_MASTER_KEY` fija de prueba).
- `reloj_falso` (`ClockPort` con `avanzar()`), `uuid_secuencial`.
- `postgres` (testcontainers `postgres:17-alpine`, alcance sesión) + `bd_limpia` (transacción con rollback por prueba) + `bootstrap` ejecutado una vez.
- `greenmail` (testcontainers `greenmail/standalone:2.1.x`, puertos 3143 IMAP / 3025 SMTP, `GREENMAIL_OPTS=-Dgreenmail.setup.test.all -Dgreenmail.users=soporte:clave@viamatica.test`).
- `cliente_api` (`httpx.AsyncClient(transport=ASGITransport(app))`) y `token_de(rol)`.
- `proveedor_falso` (`ProveedorFalso` con `programar("categoria", choice="soporte", confidence=0.93)` y `fallar_con(ErrorProveedor(...))`).
Marcadores: `unit`, `contrato`, `integracion`, `api`, `agentes`, `e2e`, `eval`, `lento` (declarados en `pyproject.toml`, `--strict-markers`). `asyncio_mode = "auto"`.

Patrones:
- Nombres `test_<sujeto>_<condicion>_<resultado>` en español.
- Tablas de casos con `pytest.mark.parametrize(ids=...)`.
- Contrato: `respx.mock(base_url="https://api.anthropic.com")` y cassettes JSON en `tests/cassettes/<proveedor>/`; verificar cuerpo enviado (modelo, `thinking`, ausencia de `budget_tokens`) y mapeo de errores 429/401/500/refusal.
- Grafo: `grafo_prueba = construir_grafo(deps_falsas, checkpointer=MemorySaver())`; afirmar la secuencia de nodos con `astream(..., stream_mode="updates")`.
- API: para cada endpoint, casos 200/201, 400 (body inválido y `extra` desconocido), 401, 403 (rol inferior), 404 y 409 cuando aplique.
- Sin `time.sleep`; esperar con `asyncio.wait_for` sobre eventos.

Comandos:
```
cd backend
uv run pytest -q -m "unit or contrato or api or agentes"          # rápido, sin contenedores
uv run pytest -q -m integracion                                    # requiere Docker
uv run pytest -q --cov=app --cov-report=term-missing --cov-fail-under=85
```

## Frontend (Vitest + Playwright)
- Vitest configurado por Angular CLI (`ng test` → Vitest). `TestBed` con `provideZonelessChangeDetection()`; `await fixture.whenStable()` tras cambiar signals; `provideHttpClientTesting()`; stores probados como servicios.
- Cada componente de `shared/ui`: render, inputs requeridos, eventos, accesibilidad básica (`role`, `aria-*`).
- Playwright `frontend/e2e/`: `docker compose -f infra/docker-compose.yml -f infra/docker-compose.e2e.yml up -d` (`FAKE_PROVIDERS=true`, semillas de demo) → flujos: login; alta de cuenta + probar conexión (GreenMail); correo llega y aparece clasificado; aprobar borrador y verificar envío en GreenMail; editar prompt, publicar, verificar en playground; a11y con `@axe-core/playwright` en 6 páginas.
- Page objects por pantalla; sin selectores CSS frágiles (usar `getByRole`, `data-testid`).

## Evaluaciones del clasificador (`evals/`)
- `evals/dataset.jsonl`: `{ "id", "entrada": {"remitente","asunto","cuerpo","autenticacion"}, "categoria", "urgencia", "requiere_respuesta", "riesgo": {"jailbreak","phishing"} }`. ≥ 300 ejemplos, ≥ 15 % adversariales, español/inglés, generados sintéticamente y revisados; jamás correos reales.
- `uv run python -m evals.clasificador --motor jev|llm --limite 300` → exactitud, F1 por categoría, matriz de confusión, recall/FP de riesgo, costo total y por correo, latencia p50/p95; guarda `evals/reportes/<fecha>-<motor>.json` y falla si exactitud < 0,92 o recall jailbreak < 0,90 o FP > 0,05.
- Corre en CI nocturno con claves de staging; en PR se ejecuta un subconjunto de 30 con proveedores falsos para validar el pipeline.

## Fixtures adversariales mínimas (`tests/fixtures/correos/`)
`adversarial_ignore_previous.eml`, `adversarial_html_oculto.eml` (texto blanco), `adversarial_base64.eml`, `adversarial_asunto.eml`, `phishing_homografo.eml`, `phishing_urgencia_pago.eml`, `newsletter.eml`, `soporte_es.eml`, `soporte_en.eml`, `facturacion_adjunto.eml`, `sin_asunto.eml`, `html_gigante.eml` (2 MB), `codificacion_latin1.eml`, `sin_message_id.eml`.

## Reporte de defectos
`BUG-nn · <título>` · Severidad (Crítica: seguridad/pérdida de datos; Alta: función principal rota; Media: función secundaria; Baja: cosmético) · Pasos · Esperado/Obtenido · Evidencia (salida real) · Sospecha `archivo:línea` · Prueba que lo reproduce (`xfail(strict=True, reason="BUG-nn")`).
