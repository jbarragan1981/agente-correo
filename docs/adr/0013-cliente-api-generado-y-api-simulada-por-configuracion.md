# ADR-0013 · Cliente de API generado desde un OpenAPI versionado y API simulada por configuración de build

**Estado:** Aceptada · 2026-09-28 · Épica E0.4

## Contexto

`docs/06-frontend-angular.md` pide un cliente tipado generado desde el OpenAPI y `docs/09-testing-y-calidad.md` exige regenerarlo en cada cambio de endpoint. Hoy el backend solo publica `/api/v1/salud` y `/api/v1/salud/listo`; la autenticación (E0.3) no existe, pero el panel necesita login, guards y shell para avanzar en paralelo.

Verificación del arquitecto (2026-09-28):

- `crear_app(Settings(_env_file=None, env="test")).openapi()` genera el esquema sin servidor, sin BD y sin leer `.env`; es idéntico (byte a byte tras ordenar claves) a `GET /api/v1/openapi.json` de `uvicorn --factory app.main:crear_app` con `ENV=test`. OpenAPI 3.1.0.
- `ng-openapi-gen` 1.1.0 genera funciones por operación sobre `HttpClient` (los interceptores de Angular se aplican), un servicio `Api` con `invoke()` y modelos; compila con TypeScript 6.0 (el que exige Angular 22) y no declara `typescript` como peer.
- `openapi-typescript` 7.13 declara `typescript ^5.x` como peer y choca con TypeScript 6.0; `@hey-api/openapi-ts` no ofrece cliente Angular publicado.
- Los `operationId` que FastAPI genera por defecto son largos (`vivo_api_v1_salud_get`).

## Decisión

1. **Contrato versionado.** `frontend/openapi/openapi.json` es una instantánea del esquema exportada con `npm run api:exportar` (script que ejecuta la fábrica del backend vía `uv run --directory ../backend`, sin servidor ni `.env`, y escribe JSON con claves ordenadas). Alternativa documentada: descargarlo de un backend local en marcha.
2. **Generación.** `ng-openapi-gen` (versión exacta) con `ng-openapi-gen.json` genera `src/app/core/api/generado/`, que se versiona, no se edita a mano y se excluye de ESLint, Prettier y cobertura. `npm run api:verificar` reexporta, regenera y falla si `git diff` detecta cambios (lo usará CI en E0.5).
3. **Uso.** Las features llaman a las funciones generadas con `inject(Api).invoke(fn, params)` dentro de `resource()`, sin fachadas intermedias. Si cambia un `operationId`, el compilador señala cada uso.
4. **Contratos aún no publicados** (auth de E0.3) se escriben a mano en `core/auth/contrato-auth.ts`, marcados como provisionales, y se sustituyen por los modelos generados cuando el backend los publique.
5. **API simulada por configuración de build.** Un interceptor `apiSimuladaInterceptor` (el más interno de la cadena) responde `/api/v1/auth/*` con usuarios de ejemplo y errores `problem+json`. Solo se incluye por `fileReplacements` en las configuraciones `mocks` (desarrollo) y `e2e` (Playwright). `production` y `development` importan un archivo que no referencia el código simulado, así que esbuild no lo empaqueta. Cada respuesta simulada lleva la cabecera `X-Api-Simulada: 1` y el shell muestra un aviso "Modo simulado" a través del token de inyección `MODO_SIMULADO`.

## Alternativas descartadas

- Tipos escritos a mano para todo: se desincronizan con el backend y no detectan cambios de contrato.
- Generar en cada build desde un backend en marcha: acopla el build del frontend a Python y a la BD; el Dockerfile del panel dejaría de ser autónomo.
- Mocks con MSW (service worker): añade un worker y una dependencia; la CSP y el ciclo de vida del service worker complican el e2e sin beneficio frente a un interceptor.
- Activar los mocks con una variable en tiempo de ejecución: el código simulado viajaría en el bundle de producción.

## Consecuencias

- (+) El frontend avanza sin E0.3 con el mismo camino de código (interceptores, store, guards) que usará con el backend real.
- (+) La deriva de contrato se detecta en `api:verificar`.
- (−) Regenerar exige `uv` y el backend en el repo; el Dockerfile del panel no lo necesita porque usa el código ya generado.
- (−) Se solicita al backend (fuera de E0.4) `generate_unique_id_function` para que el `operationId` sea el nombre de la función de la ruta (`vivo`, `listo`, `login`…); hasta entonces se usan los nombres largos.
