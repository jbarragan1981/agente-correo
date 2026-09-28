# Agente Correo

Sistema multiagente de correo electrónico y webchat para Viamatica. Conecta una o varias cuentas de correo, trata cada mensaje como dato no confiable, lo pasa por un guardián anti-jailbreak/phishing, lo clasifica con **TypeSafe Jev** (respaldo automático en un LLM económico), lo enruta a agentes especializados y redacta borradores que un operador aprueba desde un panel Angular con dashboard de observabilidad, configuración de agentes (prompt, modelo, proveedor), playground y gestión de cuentas.

**Stack:** Python 3.12 · FastAPI · LangGraph · LangChain (capa de modelos) · PostgreSQL 17 (única dependencia; se crea sola al arrancar) · Angular 22 zoneless + Material + Tailwind · Docker Compose. Proveedor de IA agnóstico: Anthropic primero; OpenAI, Gemini y Jev intercambiables por configuración.

## Documentación
| Documento | Contenido |
|---|---|
| [docs/00-vision-y-alcance.md](docs/00-vision-y-alcance.md) | Problema, objetivos medibles, roles, alcance por fases, principios |
| [docs/01-arquitectura.md](docs/01-arquitectura.md) | C4, hexagonal, enjambre de agentes, flujos, bootstrap de BD |
| [docs/02-stack-tecnologico.md](docs/02-stack-tecnologico.md) | Elecciones, versiones verificadas, justificación, modelos por defecto |
| [docs/03-modelo-de-datos.md](docs/03-modelo-de-datos.md) | Tablas, índices, retención, roles de BD |
| [docs/04-api.md](docs/04-api.md) | Contrato REST/WebSocket, roles, errores |
| [docs/05-agentes-y-proveedores.md](docs/05-agentes-y-proveedores.md) | Puertos, registro, adaptadores Anthropic/Jev, agentes por defecto y prompts |
| [docs/06-frontend-angular.md](docs/06-frontend-angular.md) | Sistema de diseño Viamatica, pantallas, criterios de aceptación, widget |
| [docs/07-seguridad.md](docs/07-seguridad.md) | Modelo de amenazas, controles ASVS + OWASP LLM, checklist de producción |
| [docs/08-observabilidad.md](docs/08-observabilidad.md) | Logs, métricas, trazas, costos, alertas |
| [docs/09-testing-y-calidad.md](docs/09-testing-y-calidad.md) | Pirámide de pruebas, DoD, CI |
| [docs/10-roadmap.md](docs/10-roadmap.md) | Épicas por fase, hitos |
| [docs/adr/](docs/adr/) | Decisiones de arquitectura |

## Construcción con Claude Code
El repositorio incluye un enjambre de agentes de desarrollo en `.claude/`: `arquitecto`, `backend`, `frontend`, `qa` y `seguridad`, con skills de dominio, hooks de seguridad y el comando de orquestación:

```
/orquestar E0.1     # primera épica: esqueleto backend (ver docs/10-roadmap.md)
```
Detalles en [CLAUDE.md](CLAUDE.md).

## Arranque local (cuando exista el código de E0.x)
```
cp .env.example .env && make keys   # pega las claves generadas en .env
make dev
```
