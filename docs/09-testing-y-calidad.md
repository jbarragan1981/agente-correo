# 09 · Estrategia de pruebas y calidad

## 1. Pirámide

| Nivel | Backend | Frontend | Objetivo |
|---|---|---|---|
| Unitarias | pytest; dominio y casos de uso con puertos falsos | Vitest; stores, pipes, componentes con `TestBed` zoneless | ≥ 85 % en `domain/`, `application/`, `agents/nodes/`; ≥ 80 % en `core/`, `shared/` |
| Contrato de proveedores | pytest + `respx` con respuestas grabadas (Anthropic, Jev, OpenAI, Gemini) | — | Cada adaptador cumple `ChatModelPort`/`ClassifierPort`; se ejecuta sin red |
| Integración | pytest + testcontainers (PostgreSQL 17, GreenMail IMAP/SMTP) | — | Migraciones desde cero, cola, checkpointer, sync IMAP real, envío SMTP |
| API | httpx `AsyncClient` contra la app | Cliente generado desde OpenAPI (tipos) | Autorización por rol en cada endpoint, esquemas, errores `problem+json` |
| Grafo de agentes | pytest con proveedores falsos deterministas | — | Rutas del grafo: riesgo alto → cuarentena; baja confianza → respaldo; interrupt/resume |
| Evaluación de IA | `evals/` con dataset etiquetado (≥ 300 correos sintéticos + adversariales) | — | Exactitud ≥ 92 %, recall jailbreak ≥ 90 %, FP ≤ 5 %; corre en CI nocturno con claves reales de staging |
| E2E | — | Playwright contra Compose completo con proveedores falsos (`FAKE_PROVIDERS=true`) | Login, configurar cuenta, ver correo clasificado, aprobar borrador, editar y publicar prompt, playground |
| Seguridad | bandit, semgrep (reglas OWASP + LLM), pip-audit, pruebas de autorización negativas, ZAP baseline en staging | npm audit, eslint-plugin-security | Sin hallazgos altos/críticos |
| Rendimiento | Locust: 10 correos/s por worker, 200 sesiones de webchat concurrentes | Lighthouse CI | p95 clasificación ≤ 3 s; API p95 ≤ 300 ms |

## 2. Proveedores falsos

`providers/fake/` implementa ambos puertos con comportamiento configurable (respuesta fija, latencia, error, refusal) y se activa con `FAKE_PROVIDERS=true`. Sirve para pruebas, demos y desarrollo sin costo. Las pruebas de contrato usan grabaciones (`tests/cassettes/*.json`) regeneradas manualmente con `make grabar-cassettes` (requiere claves).

## 3. Datos de prueba

- `tests/fixtures/correos/`: 60 correos `.eml` sintéticos en español e inglés por categoría, incluyendo 15 adversariales (inyección en texto, en HTML oculto, en asunto, base64, phishing con dominio homógrafo).
- `evals/dataset.jsonl`: 300+ ejemplos etiquetados `{entrada, categoria, urgencia, riesgo}` generados y revisados manualmente; nunca correos reales de clientes.
- Fábricas con `polyfactory` para entidades.

## 4. Definición de terminado (DoD) por historia

1. Código con tipos completos (pyrefly/tsc estricto sin errores) y lint limpio.
2. Pruebas unitarias e integración añadidas; cobertura no baja.
3. Migración Alembic incluida y reversible (`downgrade` probado).
4. Endpoint documentado en OpenAPI con ejemplos; cliente frontend regenerado.
5. Auditoría y métricas añadidas si la historia cambia estado de negocio.
6. Revisión del agente `qa` (pruebas) y del agente `seguridad` (checklist) sin hallazgos bloqueantes.
7. Documentación en `docs/` actualizada si cambia el contrato o la arquitectura (ADR si es decisión).

## 5. CI (GitHub Actions)

```
lint-y-tipos  → ruff, pyrefly, eslint, tsc
pruebas-back  → pytest (unit + contrato + integración con servicios en contenedor), cobertura
pruebas-front → vitest, build de producción con presupuestos
seguridad     → bandit, semgrep, pip-audit, npm audit, gitleaks, trivy (imagen)
e2e           → docker compose up (FAKE_PROVIDERS=true) + playwright
evals (nocturno) → dataset contra Jev/Anthropic de staging; publica reporte
```
Todo PR requiere los cuatro primeros verdes; `e2e` en PRs a `main`; `evals` no bloquea pero abre issue si hay regresión.

## 6. Convenciones

- Nombres de pruebas en español descriptivo: `test_clasificador_usa_respaldo_cuando_confianza_baja`.
- Una aserción de comportamiento por prueba; datos mínimos; sin `sleep`.
- Marcadores pytest: `unit`, `contrato`, `integracion`, `e2e`, `eval`, `lento`.
- Commits convencionales (`feat:`, `fix:`, `docs:`, `test:`, `sec:`), ramas `feature/<epica>-<historia>`.
