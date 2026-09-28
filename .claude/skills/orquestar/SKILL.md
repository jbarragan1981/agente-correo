---
name: orquestar
description: Orquesta la construcción de una épica o historia de Agente Correo con el enjambre de agentes de Claude Code (arquitecto → backend + frontend en paralelo → qa → seguridad → PR). Úsalo con /orquestar <épica o descripción>, por ejemplo "/orquestar E1.3 cuentas de correo". También cuando el usuario pida "construye", "implementa la épica" o "haz la historia" de este proyecto.
---

# Orquestación de una épica

Argumento recibido: `$ARGUMENTS` (código de épica de `docs/10-roadmap.md` o descripción libre).

Sigue estas fases en orden. Cada fase usa el agente indicado mediante la herramienta `Agent` (`subagent_type`). Pasa siempre a cada agente: la épica, la ruta del plan, y el resumen de lo que hicieron los agentes anteriores. No hagas tú el trabajo de un agente salvo que sea trivial.

## Fase 0 · Preparación (tú)
1. Confirma rama de trabajo: `git status`, `git branch --show-current`. Si estás en `main`, crea `feature/<epica-slug>`.
2. Lee `docs/10-roadmap.md` para ubicar la épica y sus dependencias. Si una épica previa requerida no existe en el código, dilo y propón el orden.
3. Crea tareas con `TaskCreate` para cada fase.

## Fase 1 · Arquitecto
Lanza `arquitecto` con: "Épica: … Produce `docs/planes/<slug>.md` con diseño, tareas por agente, dependencias y pruebas. Registra ADRs si decides algo nuevo." Espera el resultado. Lee el plan. Si el plan cambia contratos (`docs/04-api.md`, `docs/03-modelo-de-datos.md`), verifica que los actualizó.

## Fase 2 · Implementación en paralelo
Lanza **en la misma respuesta** (para que corran en paralelo):
- `backend` con las tareas de backend del plan, en orden, indicando qué endpoints/esquemas debe exponer primero porque el frontend los consume.
- `frontend` con las tareas de frontend del plan, indicando que use mocks para endpoints aún no disponibles y que regenere el cliente OpenAPI al final si el backend ya expone el contrato.
Si el plan marca dependencias duras (p. ej. migración antes de endpoint), respétalas en el orden interno de cada agente, no serializando los agentes.

Cuando ambos terminen, revisa sus reportes: comandos de verificación ejecutados y verdes, desviaciones del plan. Si alguno reporta pruebas rojas o pendientes, relánzalo con `SendMessage` para que lo cierre antes de seguir.

## Fase 3 · QA
Lanza `qa` con el plan y el resumen de cambios. Si reporta defectos de severidad Alta o Crítica, reenvíalos al agente responsable (`backend`/`frontend`) con la reproducción, y vuelve a lanzar `qa` sobre lo corregido. Repite hasta que no haya Altos/Críticos. Los Medios/Bajos se anotan en el reporte final.

## Fase 4 · Seguridad
Lanza `seguridad`. Con veredicto `BLOQUEADO`, devuelve los hallazgos al agente responsable y repite Fase 4. Con `APROBADO CON OBSERVACIONES`, crea issues/tareas para las observaciones.

## Fase 5 · Cierre (tú)
1. Ejecuta `make check` (o los comandos equivalentes de `CLAUDE.md`) una última vez y confirma verde.
2. Actualiza `docs/10-roadmap.md` marcando la épica y `docs/planes/<slug>.md` con el estado final.
3. Commit(s) convencionales por área (`feat(backend): …`, `feat(frontend): …`, `test: …`, `docs: …`) y push a la rama.
4. Si el usuario pidió PR, créalo con: objetivo, resumen por agente, cómo probar, veredicto de seguridad, capturas si hay UI. Si no lo pidió, ofrece crearlo.
5. Reporte final al usuario: qué se construyó, cómo verificarlo, hallazgos abiertos, siguiente épica sugerida.

## Reglas
- Nunca saltes QA ni Seguridad, aunque la épica parezca pequeña.
- Nunca fusiones a `main` ni hagas `push --force`.
- Si un agente pide credenciales reales, respóndele que use proveedores falsos (`FAKE_PROVIDERS=true`) y fixtures.
- Si la épica es demasiado grande (más de ~12 tareas por agente), pide al arquitecto dividirla y orquesta la primera parte.
