# Frontend · Agente Correo (Angular 22)

Panel de operación: Angular 22.2 zoneless, Angular Material 22 (M3) + Tailwind 4 con los tokens Viamatica, `@ngrx/signals`, Signal Forms, Vitest y Playwright. Convenciones en `docs/06-frontend-angular.md` y en el skill `.claude/skills/angular-viamatica`; decisiones en ADR-0005, ADR-0012 (mismo origen y CSP con nonce) y ADR-0013 (cliente generado y API simulada).

## Requisitos

- **Node ≥ 22.22.3** (`^22.22.3 || ^24.15.0`); versión recomendada en `.nvmrc` (22.23.3). `engine-strict=true` hace fallar `npm ci` con un Node anterior.
  - Con nvm: `nvm install && nvm use`.
  - Sin cambiar el Node del sistema: `npx -y -p node@22.23.3 -- npm run <script>`.
  - `make check-frontend` (desde la raíz) elige solo la opción adecuada.
- `uv` y `backend/` solo para regenerar el cliente de API.

```
cd frontend
npm ci
```

## Modos de ejecución

| Comando               | Qué hace                                                                                                                                                             |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm start`           | `ng serve` con la API real vía `proxy.conf.json` (`/api` → `http://localhost:8000`).                                                                                 |
| `npm run start:mocks` | `ng serve --configuration mocks`: la autenticación la responde la **API simulada** y el shell muestra "Modo simulado". `/api/v1/salud*` sigue yendo al backend real. |
| `npm run build`       | Build de producción en `dist/panel/browser` (lo que copia `infra/Dockerfile.web`).                                                                                   |

### API simulada (solo `mocks` y `e2e`)

Mientras E0.3 no publique la autenticación, el login funciona con un interceptor que solo se incluye en los builds `mocks` y `e2e` (`fileReplacements`; `production` y `development` no lo empaquetan). Usuarios de ejemplo, dominio reservado `.test`, contraseña común `prueba-panel-local`:

| Correo                    | Rol      |
| ------------------------- | -------- |
| `admin@viamatica.test`    | admin    |
| `operador@viamatica.test` | operador |
| `auditor@viamatica.test`  | auditor  |

Tras 5 fallos seguidos responde 429 con `Retry-After: 60`. El refresh siempre da 401 (no hay cookie real), así que recargar la página devuelve a `/login`. Estas credenciales no existen en el backend real.

## Scripts de calidad

| Script                                                                         | Qué hace                                                                                                                                                                                     |
| ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm run verificar`                                                            | Todo lo que ejecuta `make check-frontend`: Node, lint, formato (`prettier --check .`), tipos, pruebas con cobertura, build de producción e i18n.                                             |
| `npm run lint`                                                                 | `ng lint` (0 avisos) + `scripts/verificar-estilos.mjs` (hex solo en `tokens.css`, sin `style=`, `!important` marcado, sin `[innerHTML]`) + `scripts/verificar-csp.mjs` (CSP de ADR-0012).    |
| `npm run typecheck`                                                            | `tsc --noEmit` de app y de pruebas.                                                                                                                                                          |
| `npm run test` / `npm run test:ci`                                             | Vitest en modo interactivo / una vez con cobertura (≥ 80 % global y en `core/` y `shared/`).                                                                                                 |
| `npm run i18n:extraer` / `npm run i18n:verificar`                              | Actualiza / comprueba `src/locale/messages.es.xlf`. Ejecuta `i18n:extraer` tras cambiar textos.                                                                                              |
| `npm run e2e`                                                                  | Playwright 1.56.1: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers npm run e2e`. Compila el build `e2e` y lo sirve con `e2e/servidor-panel.mjs`, que reproduce las cabeceras y el nonce de Nginx. |
| `API_DESTINO=http://127.0.0.1:8000 PUERTO=4301 npm run e2e -- --grep @backend` | e2e contra el backend real (arranca uvicorn con `ENV=test`).                                                                                                                                 |

## Cliente de API (ADR-0013)

`openapi/openapi.json` es una instantánea versionada del esquema del backend y `src/app/core/api/generado/` es código generado (no se edita; excluido de lint, Prettier y cobertura).

```
npm run api:exportar     # uv run --directory ../backend … (sin servidor ni .env) → openapi/openapi.json
npm run api:generar      # ng-openapi-gen → src/app/core/api/generado
npm run api:verificar    # ambos + git diff --exit-code (lo usará CI)
node scripts/exportar-openapi.mjs --desde-url http://localhost:8000/api/v1/openapi.json   # alternativa con backend en marcha
```

Uso en una feature: `resource({ loader: () => inject(Api).invoke(listoApiV1SaludListoGet) })`.

## Estructura

```
src/app/core/       api/generado · auth (SesionStore, guards, interceptor) · errores · http · layout · mocks
src/app/shared/     forms/validadores.ts · ui/shell (vm-shell)
src/app/features/   login · inicio · sistema (sin permiso, no encontrado, en construcción)
src/styles/         tokens.css (única fuente de color) · _paleta-m3.scss (generado) · tailwind.css
e2e/                Playwright + servidor del panel
scripts/            verificaciones y exportación de OpenAPI
```
