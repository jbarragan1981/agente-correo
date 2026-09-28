# Plan E0.4 · Esqueleto frontend

**Fase:** 0 · Cimientos · **Agentes:** frontend, qa (revisión de seguridad antes del PR) · **Rama:** `feature/e0-4-esqueleto-frontend`
**Referencias:** `docs/10-roadmap.md` (E0.4), `docs/06-frontend-angular.md`, `docs/04-api.md` §1, §9 y §12, `docs/07-seguridad.md` §1 y §5, `docs/09-testing-y-calidad.md`, skill `angular-viamatica`, `docs/planes/e0-1-esqueleto-backend.md` §10 (B5), ADR-0005, **ADR-0012 y ADR-0013 (nuevas)**.

## 1. Objetivo

Dejar el panel Angular 22 arrancable, probado y desplegable: proyecto zoneless con el sistema de diseño Viamatica (tokens, Inter, tema Material M3, Tailwind 4), shell con sidebar colapsable y topbar, login con `SesionStore` en memoria, guards por rol, cliente tipado generado desde el OpenAPI real del backend, manejo uniforme de errores `problem+json`, i18n en español, pruebas Vitest y Playwright, presupuestos de bundle y la imagen `web` con una CSP estricta que cierra la observación B5.

Como E0.3 (autenticación) no existe, el login funciona contra una **API simulada activable por configuración de build** (ADR-0013). La única llamada real al backend en esta épica es `/api/v1/salud` y `/api/v1/salud/listo`, que se consumen con el cliente generado desde la pantalla de inicio.

**Fuera de alcance:** pantallas de negocio (dashboard, bandeja, aprobaciones, agentes, cuentas, taxonomía, webchat, proveedores, usuarios, auditoría; en esta épica son rutas con una página "En construcción"), buscador global y estado de cuentas del topbar (E1.7/E1.3), ECharts y `ngx-echarts` (E1.10), widget de webchat (E1.11), componentes de `shared/ui` que no usa el shell (`vm-kpi-tile`, `vm-tabla`, etc.), refresh proactivo del token, endpoints de auth reales (E0.3), CI (E0.5), Lighthouse (E0.5).

## 2. Criterios de aceptación (medibles)

| # | Criterio | Cómo se verifica |
|---|---|---|
| CA1 | `cd frontend && npm ci` termina sin errores con Node ≥ 22.22.3 y `package-lock.json` versionado. Todas las dependencias directas con versión exacta (sin `^`/`~`), `engines.node` = `^22.22.3 \|\| ^24.15.0` y `.npmrc` con `engine-strict=true`. | Comando; `node -e` que recorre `package.json` y falla si hay rangos. |
| CA2 | Sin `zone.js`: `grep -c '"node_modules/zone.js"' package-lock.json` = 0 y ningún `provideZoneChangeDetection` en `src/`. | Comandos. |
| CA3 | `npm run verificar` en verde: `ng lint` con 0 errores y 0 avisos, `tsc --noEmit` de app y spec con 0 errores, Vitest sin fallos, build de producción dentro de presupuestos, `i18n:verificar` sin diferencias, `node scripts/verificar-estilos.mjs` y `node scripts/verificar-csp.mjs` con código 0. | Salida del comando. Tras aplicar el cambio de §8.1, `make check-frontend` ejecuta lo mismo. |
| CA4 | Cobertura Vitest ≥ 80 % de líneas y ramas en `src/app/core/**` y `src/app/shared/**`, excluyendo `core/api/generado/**` y `core/mocks/**`. | `coverageThresholds` en `angular.json`; `npm run test:ci` falla si no se cumple. |
| CA5 | Presupuestos: inicial ≤ 500 kB aviso / 600 kB error (tamaño bruto); cualquier script perezoso ≤ 250 kB error; estilos por componente 4 kB aviso / 8 kB error. El build de producción no emite avisos de presupuesto. | `ng build --configuration production`. |
| CA6 | El access token solo vive en el estado de `SesionStore`: ninguna llamada a `localStorage`, `sessionStorage`, `document.cookie` ni IndexedDB lo recibe; no aparece en URLs ni en consola. Tras recargar la página con sesión iniciada en modo simulado, la app vuelve a `/login`. | Vitest con espías sobre `Storage.prototype` y `console`; Playwright compara el token contra `localStorage`, `sessionStorage` y `document.cookie`. |
| CA7 | `Authorization: Bearer` solo se adjunta a URLs relativas que empiezan por `/api/` y nunca a `/api/v1/auth/login` ni `/api/v1/auth/refresh`. Un 401 dispara un único refresh compartido (N peticiones concurrentes → 1 llamada a `/auth/refresh`) y un único reintento; si el refresh falla o el reintento vuelve a dar 401, se cierra la sesión local y se navega a `/login?volver=<ruta actual>`. | Vitest con `HttpTestingController`. |
| CA8 | Toda petición lleva `X-Request-ID` UUID v4 distinto. | Vitest. |
| CA9 | `aErrorApp()` convierte cada `type` de `docs/04-api.md` §12 (`validacion`, `no_autenticado`, `sin_permiso`, `no_encontrado`, `metodo_no_permitido`, `conflicto`, `proveedor_rechazo`, `limite_excedido`, `proveedor_no_disponible`, `error_interno`, `no_listo`, `error_http`), el estado 0 (red) y respuestas no `problem+json` en un `ErrorApp` con mensaje en español; conserva `errores[]` (400), `comprobaciones` (503), `Retry-After` (429) y el UUID de `instance`. Nunca muestra el cuerpo de una respuesta que no sea `problem+json`. | Vitest parametrizado (≥ 15 casos). |
| CA10 | Guards: matriz rol × ruta de §4.8 (3 roles × 11 rutas) cubierta; sin sesión, un enlace profundo lleva a `/login?volver=<ruta>`; tras login se vuelve a esa ruta; `volver` externo o malformado (`//evil.test`, `https://evil.test`, `/\evil.test`, `javascript:alert(1)`, `%2F%2Fevil.test`) se sustituye por `/inicio`. Un rol sin permiso ve `/sin-permiso`. | Vitest (guards, `rutaInternaSegura`) + Playwright. |
| CA11 | Login: validación en español bajo cada campo con `aria-describedby`; botón deshabilitado mientras la petición está en curso; 401 → "Correo o contraseña incorrectos." sin distinguir cuál; 429 → mensaje con los segundos de `Retry-After`; red → "No se pudo contactar con el servidor."; la contraseña se vacía tras un fallo; `autocomplete="username"` y `autocomplete="current-password"`. | Vitest del componente + Playwright. |
| CA12 | Shell: sidebar 256 px expandida / 72 px colapsada con tooltips; preferencia persistida en `localStorage` (`vm.sidebar.colapsado`, sin datos de sesión); con ancho < 1024 px el sidenav pasa a modo `over` cerrado con botón de menú en el topbar; el menú lista solo las secciones permitidas al rol; menú de usuario con nombre, roles y "Cerrar sesión"; aviso "Modo simulado" visible solo con `MODO_SIMULADO`. | Vitest + Playwright. |
| CA13 | Inicio consume `/api/v1/salud/listo` con la función generada: estado "listo" con comprobaciones; 503 `no_listo` muestra cada comprobación en falla sin detalles técnicos; error de red muestra "Reintentar". | Vitest + Playwright contra backend real (`@backend`). |
| CA14 | `frontend/openapi/openapi.json` coincide con el esquema exportado del backend y `npm run api:verificar` termina con código 0 sin diferencias en `openapi/` ni en `src/app/core/api/generado/`. | Comando (requiere `uv`). |
| CA15 | API simulada: `grep -l "X-Api-Simulada" dist/panel/browser/*.js` sin resultados en builds `production` y `development`; con resultados en el build `e2e`. | Script de QA sobre los tres builds. |
| CA16 | CSP (cierra B5): `infra/nginx-cabeceras-panel.conf` contiene exactamente la política de ADR-0012; `connect-src` es `'self'`; no aparecen `https:`, `wss:`, `http:`, `*`, `'unsafe-inline'` ni `'unsafe-eval'`. En Playwright contra el servidor del panel, 0 eventos `securitypolicyviolation` y 0 errores de consola en `/login`, `/inicio`, `/sin-permiso`, una ruta perezosa y un 404; el nonce cambia entre dos cargas de `index.html`. | `scripts/verificar-csp.mjs` + `e2e/csp.spec.ts`. |
| CA17 | i18n: `<html lang="es">`, `sourceLocale` `es`, `DEFAULT_CURRENCY_CODE` `USD`; la regla `@angular-eslint/template/i18n` (con `checkId: true`) activa y sin avisos; `src/locale/messages.es.xlf` al día. | `ng lint` + `npm run i18n:verificar`. |
| CA18 | Estilos: ningún hex fuera de `src/styles/tokens.css` y del archivo generado `src/styles/_paleta-m3.scss`; sin atributos `style=` en plantillas; `!important` solo con comentario `// override-material:`. Los pares de color de §4.3.2 cumplen AA. | `scripts/verificar-estilos.mjs` + prueba unitaria de contraste sobre los tokens. |
| CA19 | Accesibilidad: axe sin violaciones `serious` ni `critical` en `/login`, `/inicio` y `/sin-permiso`, en tema claro y oscuro; foco visible en todos los controles del shell; navegación completa con teclado (Tab/Shift+Tab/Enter/Escape). | `e2e/a11y.spec.ts`. |
| CA20 | Seguridad de código: sin `bypassSecurityTrust*`, `innerHTML`, `[innerHTML]`, `eval`, `new Function` ni `console.*` en `src/` (reglas ESLint); `npm audit --audit-level=high` sin hallazgos. | `ng lint` + `npm audit`. |
| CA21 | Imagen `web`: `docker build -f infra/Dockerfile.web .` construye; `nginx -t` pasa; el contenedor corre como usuario sin privilegios con `read_only`; `curl -sI /` devuelve la CSP con nonce distinto en cada petición y `Cache-Control: no-store`; `/main-*.js` devuelve `Cache-Control: public, max-age=31536000, immutable`; `/api/v1/salud` llega al backend con sus propias cabeceras. | Comandos en una máquina con Docker (pendiente en este entorno, ver §3). |

## 3. Verificación del entorno local (hecha por el arquitecto el 2026-09-28)

| Comprobación | Resultado |
|---|---|
| Node del sistema | `/opt/node22/bin/node` **v22.22.2**, npm 10.9.7. |
| `npx @angular/cli@22` | **Falla con el Node del sistema**: todas las versiones 22.x (22.0.0 a 22.2.0) exigen `node ^22.22.3 \|\| ^24.15.0 \|\| >=26.0.0` ("The Angular CLI requires a minimum Node.js version of v22.22.3"). |
| Node compatible | Disponible por dos vías: (a) `npx -y -p node@22.23.3 -- <comando>` (el paquete `node` se descarga del registro npm; probado con `ng new`, `ng test`, `ng build` y Playwright); (b) `nvm` en `/opt/nvm` (función de shell, v0.39.7) con `nodejs.org` accesible (HTTP 200 al tarball `v22.23.3-linux-x64`). |
| Versiones npm (registro accesible) | `@angular/*` 22.2.0, `@angular/material`/`cdk` 22.2.0, `@angular/localize` 22.2.0, `@ngrx/signals` 22.0.1, `tailwindcss` y `@tailwindcss/postcss` 4.3.3, `vitest` 5.0.2, `@vitest/coverage-v8` 5.0.2, `jsdom` 30.1.1, `angular-eslint` 22.5.0, `typescript-eslint` 8.69.0, `eslint` 10.x, `prettier` 3.9.9, `ng-openapi-gen` 1.1.0, `@fontsource-variable/inter` 5.3.0, `@fontsource/material-icons` 5.3.0, `@axe-core/playwright` 4.13.0. |
| TypeScript | Angular 22.2 exige `typescript >=6.0 <6.1` (peer de `@angular/compiler-cli` y `@angular/build`); `ng new` instala `~6.0.2` (última 6.0.3). `docs/02-stack-tecnologico.md` dice `~7.0`: **se corrige a 6.0** en esta épica. |
| Proyecto de prueba | En el scratchpad: `ng new panel --standalone --style=scss --routing --ssr=false --skip-git --package-manager=npm --defaults` genera un proyecto sin `zone.js`, con builder `@angular/build:unit-test` (Vitest + jsdom). `ng test --watch=false` y `ng build` pasan. `npm run test -- --run` **falla** (`Unknown argument: run`): el `Makefile` actual no sirve para este builder (§8.1). Cobertura requiere `@vitest/coverage-v8`. `ng add angular-eslint@22.5.0` y `ng add @angular/localize@22.2.0` funcionan sin interacción. |
| Material + Tailwind + Inter | `mat.theme` M3 en `styles.scss` + Tailwind 4 en un CSS aparte (Tailwind 4 no admite Sass) + `@fontsource-variable/inter` compilan; con toolbar y sidenav el inicial fue 290 kB brutos / 75 kB transferidos. |
| CSP | Build de producción servido con la CSP de ADR-0012 y Chromium: 0 violaciones con `inlineCritical: false`, `base-uri 'self'` y Trusted Types, incluidas rutas perezosas, `MatSnackBar` y `MatTooltip`. Con la CSP de E0.1, `base-uri 'none'` bloquea `<base href>`. |
| OpenAPI | `uv run --frozen python -c` con `crear_app(Settings(_env_file=None, env="test")).openapi()` exporta el esquema sin servidor ni `.env`; idéntico al de `uvicorn --factory app.main:crear_app` con `ENV=test` en `/api/v1/openapi.json`. Operaciones: `vivo_api_v1_salud_get`, `listo_api_v1_salud_listo_get`; esquemas `SaludOut`, `PreparacionOut`, `Problema`. `ng-openapi-gen` 1.1.0 lo genera y compila. |
| Playwright | `/opt/pw-browsers` contiene **chromium-1194** (Chromium 141), que corresponde a Playwright **1.56.x**. Playwright 1.63 (el de `docs/02`) necesita chromium-1243 y el CDN de navegadores está bloqueado por el proxy (403). `@playwright/test@1.56.1` con `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers` funciona (probado con axe). Se fija 1.56.1 y E0.5 decide la subida junto con la imagen de CI. |
| Docker | CLI 29.3.1 sin daemon: no se pueden ejecutar `docker build` de `web` ni `nginx -t`. Tampoco hay binario `nginx` local. |

**Cómo verificará cada agente en local:**
1. Obtener Node ≥ 22.22.3 en cada comando (las llamadas Bash no conservan estado): prefijo `npx -y -p node@22.23.3 --` (p. ej. `cd frontend && npx -y -p node@22.23.3 -- npm run verificar`), o `source /opt/nvm/nvm.sh && nvm install 22.23.3 && nvm use 22.23.3` al inicio de cada comando. Nunca se desactiva la comprobación de `engines`.
2. `npm run verificar`; e2e con `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers npm run e2e`.
3. `npm run api:verificar` (usa `uv` y `backend/` en solo lectura).
4. CA21 queda "pendiente de ejecutar con Docker" en el reporte; no se simula.
5. Si el registro npm no responde, no se edita `package-lock.json` a mano (el hook lo bloquea): se detiene la tarea y se informa.

## 4. Diseño

### 4.1 Estructura de archivos

```
frontend/
├── .nvmrc                      # 22.23.3
├── .npmrc                      # engine-strict=true, save-exact=true
├── .postcssrc.json             # {"plugins":{"@tailwindcss/postcss":{}}}
├── .prettierrc · .prettierignore (src/app/core/api/generado, openapi, src/locale)
├── angular.json · package.json · package-lock.json · tsconfig*.json · eslint.config.js
├── ng-openapi-gen.json         # input openapi/openapi.json → output src/app/core/api/generado
├── proxy.conf.json             # /api → http://localhost:8000 (solo ng serve)
├── playwright.config.ts
├── openapi/openapi.json        # instantánea versionada (ADR-0013)
├── scripts/
│   ├── exportar-openapi.mjs    # uv run --directory ../backend … → openapi/openapi.json (claves ordenadas)
│   ├── verificar-node.mjs      # mensaje claro si Node < 22.22.3
│   ├── verificar-estilos.mjs   # hex fuera de tokens, style= en plantillas, !important sin marca
│   ├── verificar-csp.mjs       # directivas de infra/nginx-cabeceras-panel.conf, ngCspNonce, inlineCritical
│   └── verificar-i18n.mjs      # extrae a un temporal y compara con src/locale/messages.es.xlf
├── e2e/
│   ├── servidor-panel.mjs      # sirve dist/panel/browser con las cabeceras y el nonce de Nginx; proxy /api opcional
│   ├── ayudas.ts · login.spec.ts · shell.spec.ts · guards.spec.ts · csp.spec.ts · a11y.spec.ts · salud.backend.spec.ts
└── src/
    ├── index.html              # lang="es", <app-root ngCspNonce="__CSP_NONCE__">
    ├── main.ts
    ├── locale/messages.es.xlf
    ├── environments/
    │   ├── proveedores-entorno.ts        # export const interceptoresEntorno = []; export const proveedoresEntorno = []
    │   └── proveedores-entorno.mocks.ts  # [apiSimuladaInterceptor], {provide: MODO_SIMULADO, useValue: true}
    ├── styles/
    │   ├── tokens.css          # única fuente de hex (+ tema oscuro)
    │   ├── _paleta-m3.scss     # generado por ng generate @angular/material:theme-color (no se edita)
    │   └── tailwind.css        # theme + utilities, sin preflight; @theme con --color-vm-*
    ├── styles.scss             # @use material; mat.theme(...); overrides con var(--vm-*); @fontsource
    ├── testing/                # ayudas de prueba (proveedores, sesión de prueba, fábrica de problem+json)
    └── app/
        ├── app.ts · app.html · app.config.ts · app.routes.ts
        ├── core/
        │   ├── api/generado/             # ng-openapi-gen (no editar)
        │   ├── auth/                     # contrato-auth.ts, auth-api.ts, sesion.store.ts, auth.interceptor.ts,
        │   │                             # guards.ts, ruta-segura.ts, restaurar-sesion.ts
        │   ├── errores/                  # error-app.ts, errores.interceptor.ts, notificador-errores.ts, contexto-http.ts
        │   ├── http/                     # correlacion.interceptor.ts
        │   ├── layout/                   # layout-principal.ts, navegacion.ts, titulo.strategy.ts, tema.service.ts,
        │   │                             # preferencias-ui.ts
        │   └── mocks/                    # api-simulada.interceptor.ts, usuarios-simulados.ts, modo-simulado.ts
        ├── shared/
        │   ├── forms/validadores.ts      # aísla Signal Forms (ADR-0005)
        │   └── ui/shell/                 # vm-shell presentacional + README.md de shared/ui
        └── features/
            ├── login/                    # login.page.ts/.html
            ├── inicio/                   # inicio.page.ts/.html (salud)
            └── sistema/                  # sin-permiso.page, no-encontrado.page, en-construccion.page
```

`app.config.ts`:
```ts
providers: [
  provideBrowserGlobalErrorListeners(),
  provideZonelessChangeDetection(),            // explícito aunque sea el valor por defecto
  provideRouter(routes, withComponentInputBinding(), withViewTransitions()),
  provideHttpClient(withFetch(), withInterceptors([
    correlacionInterceptor, authInterceptor, erroresInterceptor, ...interceptoresEntorno, // simulada = la más interna
  ])),
  provideApiConfiguration(''),                 // mismo origen (ADR-0012)
  { provide: TitleStrategy, useClass: TituloStrategy },
  { provide: DEFAULT_CURRENCY_CODE, useValue: 'USD' },
  provideAppInitializer(() => inject(SesionStore).restaurar()),
  ...proveedoresEntorno,
]
```
`provideAnimationsAsync()` solo si la versión instalada de Material lo sigue requiriendo; si está deprecado en 22.2, se omite.

### 4.2 Toolchain y configuración

- **Generación:** en el scratchpad, `npx -y -p node@22.23.3 -p @angular/cli@22.2.0 ng new panel --directory <scratch>/panel --standalone --style=scss --routing --ssr=false --skip-git --skip-install --package-manager=npm --defaults`; copiar a `frontend/` sin sobrescribir `frontend/README.md`; `npm install` dentro de `frontend/`. Nombre del proyecto `panel` (el Dockerfile copia `dist/panel/browser`).
- **Dependencias** (versión exacta): las de §3 + `rxjs` 7.8.x, `tslib`, `postcss` 8.5.x, `typescript` 6.0.3, `@playwright/test` 1.56.1. **No** se instalan `echarts` ni `ngx-echarts` (E1.10).
- **`tsconfig.json`:** `strict: true` explícito, `noImplicitAny`, `noUncheckedIndexedAccess`, `noPropertyAccessFromIndexSignature`, `exactOptionalPropertyTypes: false` (el código generado no lo soporta); `angularCompilerOptions`: `strictTemplates`, `strictInjectionParameters`, `strictInputAccessModifiers`, `strictStandalone`.
- **ESLint** (`angular-eslint` flat config): recomendadas de TS y Angular + `template/accessibility`, `@angular-eslint/prefer-on-push-component-change-detection`, `@angular-eslint/template/i18n` (`checkId: true`, `checkText: true`, `checkAttributes: true`, ignorar atributos técnicos), `no-console: error`, `no-eval`, `no-implied-eval`, `no-new-func`, `no-restricted-syntax` para `innerHTML`/`outerHTML`/`insertAdjacentHTML`/`document.write`, `@angular-eslint/template/no-inline-styles`, `@typescript-eslint/no-explicit-any: error`. Ignora `src/app/core/api/generado/**`.
- **`angular.json`:**
  - `i18n.sourceLocale: "es"`; target `extract-i18n`.
  - `build.options.styles`: `["src/styles/tokens.css", "src/styles/tailwind.css", "src/styles.scss"]`; `polyfills: ["@angular/localize/init"]`.
  - `production`: `optimization: {scripts: true, styles: {minify: true, inlineCritical: false}, fonts: true}`, `outputHashing: "all"`, `budgets`: `initial` 500 kB/600 kB, `anyScript` —/250 kB, `anyComponentStyle` 4 kB/8 kB.
  - `development`: sin optimización, sourcemaps.
  - `mocks`: como `development` + `fileReplacements` `src/environments/proveedores-entorno.ts` → `proveedores-entorno.mocks.ts`.
  - `e2e`: como `production` + el mismo `fileReplacements`.
  - `serve`: `proxyConfig: "proxy.conf.json"`; configuraciones `development` y `mocks`.
  - `test` (`@angular/build:unit-test`): `coverageInclude: ["src/app/**/*.ts"]`, `coverageExclude: ["src/app/core/api/generado/**", "src/app/core/mocks/**", "**/*.spec.ts"]`, `coverageThresholds` 80 % (líneas, ramas, funciones, sentencias) con `providersFile: "src/testing/proveedores-prueba.ts"`. Si los umbrales globales no permiten limitarlos a `core/` y `shared/`, QA añade un paso que lee `coverage/coverage-summary.json` y falla por directorio.
- **`package.json` scripts:**

| Script | Comando |
|---|---|
| `start` | `ng serve` (API real vía proxy) |
| `start:mocks` | `ng serve --configuration mocks` |
| `build` | `ng build` |
| `lint` | `ng lint && node scripts/verificar-estilos.mjs && node scripts/verificar-csp.mjs` |
| `typecheck` | `tsc --noEmit -p tsconfig.app.json && tsc --noEmit -p tsconfig.spec.json` |
| `test` | `ng test` |
| `test:ci` | `ng test --watch=false --coverage` |
| `i18n:extraer` | `ng extract-i18n --output-path src/locale --out-file messages.es.xlf --format xlf2` |
| `i18n:verificar` | `node scripts/verificar-i18n.mjs` |
| `api:exportar` | `node scripts/exportar-openapi.mjs` |
| `api:generar` | `ng-openapi-gen -c ng-openapi-gen.json` |
| `api:verificar` | `npm run api:exportar && npm run api:generar && git diff --exit-code -- openapi src/app/core/api/generado` |
| `e2e` | `playwright test` |
| `verificar` | `node scripts/verificar-node.mjs && npm run lint && npm run typecheck && npm run test:ci && npm run build -- --configuration production && npm run i18n:verificar` |

### 4.3 Sistema de diseño

#### 4.3.1 Tokens (`src/styles/tokens.css`)
Los de `docs/06-frontend-angular.md` §3.1 y el skill, más **variantes de texto AA** (nuevas; el resto de hex se mantiene):

| Token nuevo | Hex | Contraste medido | Uso |
|---|---|---|---|
| `--vm-texto-sobre-marca` | `#0D1B2A` (= `--vm-oscuro`) | 6,93 sobre `#3AAFDE` | Texto de botones primarios rellenos. |
| `--vm-enlace` | `#1F6FA3` | 5,44 sobre blanco · 4,99 sobre `#F0F6FA` | Enlaces y texto informativo pequeño. |
| `--vm-error-texto` | `#B83232` | 5,93 · 5,44 | Mensajes de error bajo campos. |
| `--vm-exito-texto` | `#157A52` | 5,33 · 4,89 | Texto de estado OK. |
| `--vm-alerta-texto` | `#8A6300` | 5,43 · 4,98 | Texto de advertencia. |
| `--vm-foco` | `#1B3A5C` | 11,63 sobre blanco | Anillo de foco (2 px + 2 px de separación). En oscuro, `#00D4FF`. |

Tema oscuro: `:root[data-tema="oscuro"]` del skill + los equivalentes de texto (`--vm-enlace: #5BC0EB`, `--vm-error-texto: #FF8A8A`, `--vm-exito-texto: #5FD3A2`, `--vm-alerta-texto: #F2C94C`; QA verifica ≥ 4,5 sobre `#0D1B2A` y `#122240`). `TemaService` aplica `data-tema` desde `prefers-color-scheme` y un conmutador persistido en `localStorage` (`vm.tema`).

#### 4.3.2 Reglas de contraste (medidas)
- Blanco sobre `#3AAFDE` = 2,51 y `#2E86C1` sobre blanco = 3,97: **no** cumplen AA para texto. `#3AAFDE` se usa solo como relleno con texto `--vm-texto-sobre-marca`, bordes e indicadores; `#2E86C1` solo en texto ≥ 24 px o iconos.
- `#D64545` sobre blanco = 4,38 y blanco sobre `#1E9E6A` = 3,41: se usan como fondo de chips con texto oscuro o como borde/icono; el texto usa las variantes `-texto`.
- Sidebar: fondo `--vm-azul-oscuro`, texto blanco (11,63), ítem activo con barra `--vm-cyan` y fondo `color-mix` del cyan al 12 %.
- Prueba unitaria `tokens-contraste.spec.ts` calcula los pares de esta sección a partir de un mapa de tokens exportado por `core/layout/tokens-contraste.ts` (sin hex en componentes) y exige ≥ 4,5 texto / ≥ 3 UI.

#### 4.3.3 Tema Material M3 y Tailwind
- `_paleta-m3.scss` se genera con `ng generate @angular/material:theme-color` (primario `#3AAFDE`, terciario `#1B3A5C`, error `#D64545`, neutro desde `#F0F6FA`); es la única excepción de hex fuera de `tokens.css` y lleva cabecera "Generado; no editar".
- `styles.scss`: `html { color-scheme: light; @include mat.theme((color: (primary: paleta.$primary-palette, tertiary: paleta.$tertiary-palette), typography: 'Inter Variable', density: 0)); }`, `html[data-tema="oscuro"] { color-scheme: dark; }`; `mat.theme-overrides` y `mat.<componente>-overrides` con `var(--vm-*)` para: `on-primary` → `--vm-texto-sobre-marca`, `surface` → `--vm-gris-fondo`, `error` → `--vm-error-texto`, `corner-medium` → `--vm-radio-card`, `corner-small` → `--vm-radio-control`; `mat.sidenav-overrides` y `mat.toolbar-overrides` para los colores del shell.
- Material se colorea con overrides; Tailwind se usa para layout, espaciado y tipografía. No se aplican clases `bg-*`/`text-*` de Tailwind sobre componentes Material (Material las sobrescribe; comprobado).
- `tailwind.css`: `@layer theme, base, components, utilities; @import "tailwindcss/theme.css" layer(theme); @import "tailwindcss/utilities.css" layer(utilities);` (sin preflight para no romper Material) y `@theme { --color-vm-marca: var(--vm-azul-marca); --color-vm-oscuro: var(--vm-oscuro); … ; --font-sans: var(--vm-fuente); }`.
- Tipografía: `--vm-fuente: "Inter Variable", system-ui, sans-serif`; escala de §3.2 como utilidades `@utility vm-titulo-pagina` (28/36 600), `vm-titulo-seccion` (20/28 600), `vm-cuerpo` (14/20), `vm-etiqueta` (12/16 500). Iconos: `@fontsource/material-icons` y `<mat-icon>` con ligaduras (sin `MatIconRegistry.addSvgIcon*`).

### 4.4 Sesión (`core/auth`)

**Contrato provisional** (`contrato-auth.ts`, a sustituir por modelos generados cuando E0.3 publique los endpoints; es la forma que se propone a E0.3, alineada con `docs/04-api.md` §1):
```ts
export type Rol = 'admin' | 'operador' | 'auditor';
export interface LoginIn { email: string; password: string; }
export interface UsuarioSesion { id: string; email: string; nombre: string; roles: Rol[]; }
export interface SesionOut { access_token: string; token_type: 'bearer'; expires_in: number; usuario: UsuarioSesion; }
// POST /api/v1/auth/login → SesionOut + cookie refresh (httpOnly, Secure, SameSite=Strict, Path=/api/v1/auth)
// POST /api/v1/auth/refresh → SesionOut (sin body; usa la cookie)
// POST /api/v1/auth/logout → 204
// GET  /api/v1/auth/me → UsuarioSesion
```

**`AuthApi`** (`auth-api.ts`): servicio con `login(credenciales)`, `refrescar()`, `cerrarSesion()`, `yo()` sobre `HttpClient` con rutas relativas. Marca `login`/`refresh`/`logout` con el contexto `SIN_TOKEN` y `refresh`/`logout` con `SILENCIAR_ERRORES`.

**`SesionStore`** (`signalStore({ providedIn: 'root' })`):
```ts
type EstadoSesion = 'anonima' | 'restaurando' | 'autenticada';
state:    { estado: EstadoSesion; token: string | null; expiraEn: number | null; usuario: UsuarioSesion | null }
computed: autenticada(), roles(), nombreVisible()
methods:  iniciar(LoginIn): Promise<void>      // lanza ErrorApp; nunca guarda la contraseña
          restaurar(): Promise<void>           // al arrancar: refresh silencioso con timeout 5 s → autenticada | anonima
          refrescar(): Promise<string>         // single-flight: una promesa compartida mientras hay un refresh en curso
          cerrar(): Promise<void>              // POST logout (errores ignorados) + limpiar + navegar a /login
          limpiarLocal(): void                 // sin red; usado por el interceptor ante 401 persistente
          tieneAlgunRol(...roles: Rol[]): boolean
```
- El token no se expone a plantillas; `token` solo lo lee `authInterceptor` mediante un método `tokenActual()`.
- Sin temporizador de refresh proactivo: el refresh es reactivo (401 → refresh → reintento).
- `restaurar()` en modo real hoy recibe 404 (E0.3 no existe) y deja la sesión `anonima` sin notificar.

**`authInterceptor`**: si `req.url` empieza por `/api/` y no tiene `SIN_TOKEN`, añade `Authorization`. Ante 401 de una petición sin `REINTENTADA` y distinta de `/auth/*`: `await sesion.refrescar()`, repite con `REINTENTADA`; si el refresh falla o el reintento da 401 → `limpiarLocal()` y `router.navigate(['/login'], { queryParams: { volver: rutaActual } })`.

**`ruta-segura.ts`**: `rutaInternaSegura(valor: string | null): string` devuelve `valor` solo si empieza por `/`, no por `//` ni `/\`, no contiene `\`, esquema ni caracteres de control tras decodificar, y `router.parseUrl` lo acepta; en otro caso `/inicio`.

### 4.5 Errores (`core/errores`)

```ts
export type TipoError = 'validacion' | 'no_autenticado' | 'sin_permiso' | 'no_encontrado' | 'metodo_no_permitido'
  | 'conflicto' | 'proveedor_rechazo' | 'limite_excedido' | 'proveedor_no_disponible' | 'error_interno'
  | 'no_listo' | 'error_http' | 'red' | 'desconocido';
export interface ErrorCampo { campo: string; mensaje: string; }
export interface ErrorApp {
  readonly tipo: TipoError; readonly estado: number; readonly mensaje: string;   // mensaje en español del catálogo i18n
  readonly detalle: string | null;          // `detail` del servidor solo si es problem+json
  readonly idCorrelacion: string | null;    // UUID extraído de `instance` (urn:uuid:…) o de X-Request-ID
  readonly errores: readonly ErrorCampo[];  // solo 400
  readonly comprobaciones: Readonly<Record<string, string>> | null; // solo 503
  readonly reintentarEnS: number | null;    // Retry-After de 429
}
export function aErrorApp(error: unknown): ErrorApp;   // función pura
export function esProblema(cuerpo: unknown): cuerpo is Problema; // guarda de tipo con el modelo generado
```
- Solo se interpreta el cuerpo si `Content-Type` empieza por `application/problem+json` y `esProblema` lo valida; `type` desconocido → `error_http`; estado 0 → `red`; resto → `desconocido` con mensaje genérico.
- `erroresInterceptor`: convierte `HttpErrorResponse` en `ErrorApp` (`throwError(() => errorApp)`) y, salvo `SILENCIAR_ERRORES` o 401 (lo gestiona auth), llama a `NotificadorErrores.mostrar(errorApp)`: `MatSnackBar` con el mensaje y, para 5xx, "Código de referencia: <idCorrelacion>". Nunca muestra cuerpos que no sean `problem+json`.
- `correlacionInterceptor`: `X-Request-ID: crypto.randomUUID()` en cada petición a `/api/`.
- `contexto-http.ts`: `SIN_TOKEN`, `SILENCIAR_ERRORES`, `REINTENTADA` (`HttpContextToken<boolean>`).

### 4.6 Cliente de API (ADR-0013)

- `scripts/exportar-openapi.mjs`: ejecuta con `execFile` (sin shell) `uv run --directory ../backend --frozen python -c <código>` con `ENV=test` y el código:
  ```python
  import json, sys
  from app.core.config import Settings
  from app.main import crear_app
  esquema = crear_app(Settings(_env_file=None, env="test")).openapi()
  open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(esquema, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
  ```
  y escribe `frontend/openapi/openapi.json`. Opción `--desde-url http://localhost:8000/api/v1/openapi.json` para descargarlo de un backend local en marcha.
- `ng-openapi-gen.json`: `{"$schema": "node_modules/ng-openapi-gen/ng-openapi-gen-schema.json", "input": "openapi/openapi.json", "output": "src/app/core/api/generado", "indexFile": true, "removeStaleFiles": true, "ignoreUnusedModels": false, "enumStyle": "alias"}`.
- Uso en inicio: `resource({ loader: () => inject(Api).invoke(listoApiV1SaludListoGet, undefined, new HttpContext().set(SILENCIAR_ERRORES, true)) })`; el 503 llega como `ErrorApp` con `comprobaciones`.

### 4.7 API simulada (ADR-0013)

- `apiSimuladaInterceptor` atiende solo `POST /api/v1/auth/login|refresh|logout` y `GET /api/v1/auth/me`; el resto pasa a `next()` (salud va al backend real).
- Usuarios (`usuarios-simulados.ts`, dominio reservado `.test`): `admin@viamatica.test` (admin), `operador@viamatica.test` (operador), `auditor@viamatica.test` (auditor), contraseña común `prueba-panel-local`. Token opaco `simulado.<uuid>` (no JWT), `expires_in: 900`.
- Credenciales erróneas → 401 `problem+json` `no_autenticado` con `detail` genérico; tras 5 fallos seguidos → 429 `limite_excedido` con `Retry-After: 60`. `refresh` responde 401 (no hay cookie real): recargar la página devuelve a `/login` (CA6).
- Latencia simulada con `delay(300)` para ver el estado "enviando". Toda respuesta con `X-Api-Simulada: 1`.

### 4.8 Rutas, navegación y guards

`navegacion.ts` es la única fuente de secciones, iconos, etiquetas y roles; `app.routes.ts` y el menú la consumen. Los guards son solo de experiencia de usuario: la autorización real la aplica el backend (E0.3). Roles provisionales, alineados con las columnas de rol de `docs/04-api.md`; E0.3 los confirma y el cambio queda en un solo archivo.

| Ruta | Página (carga perezosa) | Guards | Roles |
|---|---|---|---|
| `/login` | `LoginPage` | `invitadoGuard` | público |
| `/sin-permiso` | `SinPermisoPage` | `autenticadoGuard` | todos |
| `/inicio` | `InicioPage` | `autenticadoGuard` | admin, operador, auditor |
| `/dashboard` | `EnConstruccionPage` | `autenticadoGuard`, `rolGuard` | admin, operador, auditor |
| `/bandeja` | idem | idem | admin, operador, auditor |
| `/aprobaciones` | idem | idem | admin, operador |
| `/agentes` | idem | idem | admin, operador, auditor |
| `/cuentas` | idem | idem | admin, operador, auditor |
| `/taxonomia` | idem | idem | admin |
| `/webchat` | idem | idem | admin, operador |
| `/proveedores` | idem | idem | admin, auditor |
| `/usuarios` | idem | idem | admin |
| `/auditoria` | idem | idem | admin, auditor |
| `''` | redirige a `/inicio` | | |
| `**` | `NoEncontradoPage` | | |

- Las rutas autenticadas son hijas de `LayoutPrincipal` (shell), con `canMatch: [autenticadoGuard]` en el padre y `canMatch: [rolGuard(...roles)]` en cada hija.
- `autenticadoGuard`: si `estado() === 'restaurando'` espera a que termine; sin sesión devuelve `UrlTree` `/login?volver=<url>`.
- `rolGuard(...roles)`: `UrlTree` `/sin-permiso` si no tiene ninguno.
- `invitadoGuard`: con sesión, `UrlTree` a `/inicio`.
- `TituloStrategy`: "<título de ruta> · Agente Correo"; títulos con `$localize`.

### 4.9 Shell (`shared/ui/shell` + `core/layout`)

- `vm-shell` (presentacional, `OnPush`): `navegacion = input.required<ItemNavegacion[]>()`, `usuario = input.required<UsuarioSesion>()`, `colapsado = input.required<boolean>()`, `modoSimulado = input<boolean>(false)`, `temaOscuro = input<boolean>(false)`; `output`s `alternarColapso`, `alternarTema`, `cerrarSesion`. `mat-sidenav-container` + `mat-toolbar`; ítems con `routerLink`, `routerLinkActive` (`aria-current="page"`), `matTooltip` solo si está colapsada; `<ng-content>` para el `router-outlet`.
- `LayoutPrincipal` (contenedor en `core/layout`): inyecta `SesionStore`, `PreferenciasUi` (lee/escribe `vm.sidebar.colapsado` y `vm.tema` en `localStorage`, con `try/catch` si no está disponible), `BreakpointObserver` (< 1024 px → modo `over`), `MODO_SIMULADO` (`InjectionToken<boolean>` con valor por defecto `false`).
- Topbar: botón de menú (móvil), marca "Agente Correo" (texto; sin logo binario en esta épica), aviso "Modo simulado" (chip `--vm-alerta` con texto oscuro), conmutador de tema, menú de usuario (`mat-menu`) con nombre, roles y "Cerrar sesión".
- Enlace "Saltar al contenido" como primer elemento enfocable.

### 4.10 Pantallas

- **Login**: tarjeta centrada sobre `--vm-gris-fondo`, título "Iniciar sesión", Signal Forms (`form(modelo, esquema)` con `required` y `email` desde `shared/forms/validadores.ts`), mostrar/ocultar contraseña con `aria-pressed`, `mat-progress-bar` mientras envía, zona `role="alert"` para el error general. Tras éxito navega a `rutaInternaSegura(volver)`. Nota bajo el formulario: "La sesión se mantiene mediante una cookie segura; no se guarda tu contraseña."
- **Inicio**: "Hola, <nombre>", tarjeta "Estado del sistema" con `/salud/listo` (listo / no listo con cada comprobación / sin conexión + Reintentar) y accesos a las secciones permitidas.
- **Sin permiso** (403), **No encontrado** (404), **En construcción** (título de la sección y épica prevista, tomados de `navegacion.ts`).

### 4.11 Nginx e imagen `web` (ADR-0012)

`infra/nginx-cabeceras-panel.conf` (nuevo; se incluye en las `location` del panel):
```nginx
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'nonce-$request_id'; font-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; worker-src 'self'; manifest-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; require-trusted-types-for 'script'; trusted-types angular angular#bundler" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header X-Frame-Options "DENY" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=(), usb=()" always;
add_header Cross-Origin-Opener-Policy "same-origin" always;
add_header Cross-Origin-Resource-Policy "same-origin" always;
```
`infra/nginx.conf`:
```nginx
map $http_upgrade $conexion_upgrade { default upgrade; '' close; }
server {
  listen 8080; server_name _; server_tokens off;
  root /usr/share/nginx/html; index index.html;
  gzip on; gzip_types text/plain text/css application/json application/javascript image/svg+xml;

  location /api/ {                       # sin cabeceras del panel: la API envía las suyas (E0.1)
    client_max_body_size 1m;
    proxy_pass http://api:8000/api/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection $conexion_upgrade;
    proxy_set_header Host $host; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme; proxy_read_timeout 300s;
  }
  location ~* \.(?:js|css|woff2?|ico|svg|png|webp)$ {
    try_files $uri =404;
    include /etc/nginx/cabeceras-panel.conf;
    add_header Cache-Control "public, max-age=31536000, immutable" always;
  }
  location / {
    try_files $uri $uri/ /index.html;
    include /etc/nginx/cabeceras-panel.conf;
    add_header Cache-Control "no-store" always;
    sub_filter_types text/html; sub_filter_once off;
    sub_filter '__CSP_NONCE__' $request_id;
  }
}
```
`infra/Dockerfile.web`: `COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./` (lockfile obligatorio, sin `*`); `npm ci --no-audit --no-fund`; build `production`; en runtime `COPY infra/nginx-cabeceras-panel.conf /etc/nginx/cabeceras-panel.conf` (fuera de `conf.d/` para que no se incluya a nivel `http`); `USER 101` explícito. La imagen base `node:22-alpine` resuelve a ≥ 22.22.3; `engine-strict` hace fallar el build si no.

### 4.12 Métricas y auditoría

La épica no cambia estado de negocio: no añade auditoría ni métricas de backend. Cada petición lleva `X-Request-ID` para correlación con los logs (E0.1). Los errores 5xx muestran el código de referencia al operador. La telemetría de frontend (Web Vitals, OTel web) queda para E1.10.

## 5. Tareas

Cada tarea de frontend incluye sus pruebas Vitest unitarias básicas; QA añade casos límite, e2e y verificación. Todas las órdenes npm con Node ≥ 22.22.3 (§3).

### Frontend

| # | Tarea | Depende de | Paralelo con |
|---|---|---|---|
| F1 | Andamiaje (§4.2): Node 22.23.3, `ng new` en el scratchpad y copia a `frontend/` preservando `README.md`, `.nvmrc`, `.npmrc`, `engines`, versiones exactas, `tsconfig` estricto, `ng add angular-eslint@22.5.0` y reglas de §4.2, Prettier e ignores, scripts de §4.2 (los que dependen de tareas posteriores se añaden como marcador que falla con mensaje claro hasta completarse), `scripts/verificar-node.mjs`, `index.html` con `lang="es"` y `ngCspNonce`, `production` con `inlineCritical: false` y presupuestos. `npm run lint && npm run typecheck && npm run test:ci && npm run build` en verde. **Avisar al orquestador al terminar** (§8.1: `make check` empieza a ejecutar el frontend). | — | F12 |
| F2 | Estilos (§4.3): Material/CDK, `_paleta-m3.scss` generado, `tokens.css` con variantes AA y tema oscuro, `tailwind.css`, `styles.scss` con overrides, Inter y Material Icons autoalojadas, utilidades tipográficas, `TemaService` + `PreferenciasUi`, `scripts/verificar-estilos.mjs`, `tokens-contraste.ts` + prueba. | F1 | F3, F4, F5 |
| F3 | i18n (§4.2): `@angular/localize`, `sourceLocale: es`, `DEFAULT_CURRENCY_CODE`, `TituloStrategy`, `scripts/verificar-i18n.mjs`, regla `template/i18n`. | F1 | F2, F4, F5 |
| F4 | Errores y correlación (§4.5): `ErrorApp`, `aErrorApp`, `esProblema`, contexto HTTP, `erroresInterceptor`, `NotificadorErrores`, `correlacionInterceptor` + pruebas. | F1 | F2, F3, F5 |
| F5 | Cliente API (§4.6): `exportar-openapi.mjs`, `openapi/openapi.json`, `ng-openapi-gen.json`, generación, `provideApiConfiguration('')`, `proxy.conf.json`, exclusiones de lint/prettier/cobertura. `npm run api:verificar` en verde. | F1 | F2, F3, F4 |
| F6 | Sesión (§4.4): `contrato-auth.ts`, `AuthApi`, `SesionStore`, `authInterceptor`, `rutaInternaSegura`, `restaurar` en `provideAppInitializer` + pruebas. | F4 | F7 (tras su inicio), F8 |
| F7 | Rutas y guards (§4.8): `navegacion.ts`, `app.routes.ts`, `autenticadoGuard`, `rolGuard`, `invitadoGuard`, páginas de `features/sistema` + pruebas de la matriz. | F3, F6 | F8, F9 |
| F8 | API simulada (§4.7): interceptor, usuarios, `MODO_SIMULADO`, `proveedores-entorno*.ts`, configuraciones `mocks` y `e2e`, `start:mocks` + pruebas del interceptor. | F6 | F7, F9 |
| F9 | Shell (§4.9): `vm-shell`, `LayoutPrincipal`, responsive, conmutador de tema, menú de usuario, aviso de modo simulado, "Saltar al contenido", `shared/ui/README.md` + pruebas. | F2, F7 | F8, F10 |
| F10 | Login (§4.10): página con Signal Forms, `shared/forms/validadores.ts`, estados y mensajes + pruebas. | F2, F3, F6 | F9, F11 |
| F11 | Inicio (§4.10): tarjeta de salud con `resource()` y la función generada, accesos por rol + pruebas. | F5, F7 | F9, F10 |
| F12 | Infra y documentación: `infra/nginx.conf`, `infra/nginx-cabeceras-panel.conf`, `infra/Dockerfile.web` (§4.11), `scripts/verificar-csp.mjs` (en `lint` tras F1); `frontend/README.md` (Node, scripts, modos, API simulada y credenciales de ejemplo, regeneración del cliente); `docs/02-stack-tecnologico.md` (TypeScript 6.0, Node ≥ 22.22.3, Playwright 1.56.1 y motivo, `ng-openapi-gen`, `@fontsource`, `@vitest/coverage-v8`); `docs/06-frontend-angular.md` (§3.1 tokens AA, §3.2 Inter autoalojada, §6 CSP de ADR-0012, API simulada); `docs/07-seguridad.md` §5 (CSP del panel y mismo origen); skill `angular-viamatica` (comandos de verificación con `npm run verificar`, Tailwind en CSS aparte, sin ECharts hasta E1.10). Cierre: `npm run verificar` con salida real. | Infra: —; scripts y docs: F1–F11 | F1–F11 |

### QA

| # | Tarea | Depende de | Paralelo con |
|---|---|---|---|
| Q1 | Infraestructura de pruebas: `src/testing/` (proveedores de prueba, `crearSesionPrueba(roles)`, `problema(tipo, estado, extras)`, `respuestaNoProblema()`), `providersFile`, umbrales de cobertura por directorio (CA4). | F1, F4 | F2–F5 |
| Q2 | Casos límite de `aErrorApp` e interceptores (CA7–CA9): tabla completa de §12, `Content-Type` con parámetros, cuerpo `problem+json` inválido, 401 concurrentes, 401 tras reintento, URL absoluta externa sin token, `/auth/*` sin token, `X-Request-ID` único. | F4, F6, Q1 | Q3, Q4 |
| Q3 | Guards y `rutaInternaSegura` (CA10): matriz rol × ruta generada desde `navegacion.ts`; vectores de redirección abierta de CA10 más codificaciones dobles y espacios; estado `restaurando`. | F7, Q1 | Q2, Q4 |
| Q4 | Componentes (CA6, CA11, CA12, CA13): login (validación, estados, 401/429/red, contraseña vaciada, `autocomplete`), shell (colapso persistido, filtro por rol, modo simulado, menú), inicio (listo/503/red); espías sobre `Storage.prototype`, `document.cookie` y `console` durante un login completo. | F8–F11, Q1 | Q2, Q3 |
| Q5 | Playwright (§3): `playwright.config.ts` (`@playwright/test` 1.56.1, Chromium de `/opt/pw-browsers`, `webServer` = `ng build --configuration e2e` + `node e2e/servidor-panel.mjs`), `e2e/servidor-panel.mjs` (lee la CSP y cabeceras de `infra/nginx-cabeceras-panel.conf`, sustituye `$request_id` y `__CSP_NONCE__` por un nonce aleatorio por petición, `no-store` en HTML, fallback SPA, proxy de `/api/` a `API_DESTINO` si está definida; si no, 502 `problem+json`). | F1, F12 (cabeceras) | Q2–Q4 |
| Q6 | e2e de flujos (CA6, CA10–CA12): login por cada rol y menú resultante; login fallido genérico; 429 tras 5 fallos; cierre de sesión; enlace profundo → login → vuelta a la ruta; `volver` externo → `/inicio`; `/sin-permiso`; colapso de sidebar persistido; recarga → `/login`; token ausente de almacenamiento y cookies. | Q5, F7–F10 | Q7 |
| Q7 | e2e de seguridad y accesibilidad (CA16, CA19): 0 `securitypolicyviolation` y 0 errores de consola por ruta; nonce distinto en dos cargas; cabeceras presentes; axe en claro y oscuro; recorrido de teclado del shell y foco visible. | Q5, F9–F11 | Q6 |
| Q8 | e2e contra backend real (`salud.backend.spec.ts`, etiqueta `@backend`, CA13–CA14): `webServer` adicional `uv run --directory ../backend uvicorn --factory app.main:crear_app --port 8000 --no-server-header --no-access-log` con `ENV=test` y `API_DESTINO=http://127.0.0.1:8000`; sin BD, `/salud/listo` da 503 y la tarjeta muestra "Base de datos: falla" sin detalles técnicos. Ejecutar `npm run api:verificar`. | Q5, F11 | Q6, Q7 |
| Q9 | Verificaciones de build (CA1, CA2, CA5, CA15, CA18, CA20): versiones exactas, sin `zone.js`, presupuestos, marcador `X-Api-Simulada` en los tres builds, `npm audit --audit-level=high`, `verificar-estilos`, reglas ESLint de seguridad con un archivo de prueba temporal que debe fallar (y se borra). | F1–F12 | Q6–Q8 |
| Q10 | Reporte en §9 de este plan: comandos con salida real, tabla CA → prueba → resultado, cobertura, defectos `BUG-nn` con reproducción, CA21 "pendiente de ejecutar con Docker" con los comandos exactos. | Q1–Q9 | — |

### Seguridad

Sin tareas de implementación. Revisión ASVS/OWASP antes del PR centrada en §7.

### Orden y paralelismo

```
F1 ─┬─ F2 ──────────────┬─ F9 ─┐
    ├─ F3 ──────┐        │      │
    ├─ F4 ─ F6 ─┼─ F7 ───┘      ├─ F12 (scripts/docs) ─┐
    │           ├─ F8           │                      │
    │           └─ F10 ─────────┤                      ├─ Q9 ─ Q10 → seguridad → PR
    ├─ F5 ───────────── F11 ────┘                      │
    └─ Q1 (tras F4) ─ Q2 · Q3 · Q4 (según dependencias)│
F12 (infra) en paralelo desde el inicio ─ Q5 ─ Q6 · Q7 · Q8 ──┘
```
- Tras F1: F2, F3, F4, F5 y F12 (infra) en paralelo.
- F6 tras F4; luego F7 y F8 en paralelo; F10 cuando estén F2, F3 y F6.
- Q5 puede empezar con F1 y la parte de infra de F12; Q6–Q8 esperan a las pantallas.
- Este plan no toca `backend/`, `infra/docker-compose.yml` ni el `Makefile` (E0.2 trabaja en ellos en paralelo). Los cambios necesarios en archivos compartidos están en §8 para el orquestador.

## 6. Pruebas requeridas al terminar

Nombres en español con `describe('<sujeto>')` e `it('<condición> → <resultado>')`; una aserción de comportamiento por prueba; sin esperas fijas (`fixture.whenStable()`, `await expect(...).toBeVisible()`).

**Aviso para quien escriba pruebas:** el hook `proteger-secretos.sh` bloquea literales con forma de JWT (`eyJ….eyJ….…`), `innerHTML =`, `bypassSecurityTrust*` y `localStorage.setItem(` con `token`/`jwt`/`access` en `.ts`. Usa tokens opacos (`'simulado.' + crypto.randomUUID()`), construye cualquier JWT de prueba en tiempo de ejecución y comprueba la ausencia de tokens con espías, sin escribir esas llamadas en el código. No rodees el hook.

### 6.1 Unitarias (Vitest, `*.spec.ts` junto al código)
- `error-app.spec.ts`: cada `type` de §12, estado 0, HTML de 502 de proxy, JSON sin `type`, `instance` sin `urn:uuid:`, `Retry-After` no numérico, `errores[]` sin valores.
- `errores.interceptor.spec.ts`: notifica con mensaje e id; respeta `SILENCIAR_ERRORES`; no notifica 401.
- `correlacion.interceptor.spec.ts`: UUID v4 distinto por petición; solo en `/api/`.
- `auth.interceptor.spec.ts`: matriz de adjuntar token; refresh single-flight; reintento único; limpieza y navegación con `volver`.
- `sesion.store.spec.ts`: transiciones de estado; `restaurar` con 401/404/timeout → `anonima`; `cerrar` limpia aunque logout falle; ningún `Storage.setItem` recibe el token.
- `ruta-segura.spec.ts`: vectores de CA10.
- `guards.spec.ts`: matriz generada desde `navegacion.ts`; espera a `restaurando`.
- `api-simulada.interceptor.spec.ts`: roles, 401 genérico, 429 al sexto intento con `Retry-After`, `X-Api-Simulada`, paso de rutas no auth.
- `vm-shell.spec.ts`, `layout-principal.spec.ts`, `login.page.spec.ts`, `inicio.page.spec.ts`, `tema.service.spec.ts`, `preferencias-ui.spec.ts`, `titulo.strategy.spec.ts`, `tokens-contraste.spec.ts`.

### 6.2 E2E (Playwright, `frontend/e2e/`)
`login.spec.ts`, `guards.spec.ts`, `shell.spec.ts`, `csp.spec.ts`, `a11y.spec.ts` (servidor del panel con build `e2e`) y `salud.backend.spec.ts` (`@backend`, requiere `uv`). Se ejecutan con `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers npm run e2e`.

### 6.3 Pendientes con Docker (no se simulan)
`docker build -f infra/Dockerfile.web -t agente-correo-web .`; `docker run --rm agente-correo-web nginx -t`; `docker compose … up -d web` y `curl -sI http://127.0.0.1:4200/` (dos veces, nonces distintos); `curl -sI http://127.0.0.1:4200/api/v1/salud`.

## 7. Riesgos de seguridad y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| R1 | Robo del access token por XSS o persistencia (ASVS V3, V8). | Token solo en el estado del store (no en storage, URL ni consola); CSP sin `'unsafe-inline'`, con Trusted Types y `connect-src 'self'`; ESLint prohíbe `innerHTML`, `eval`, `console`; hook bloquea `localStorage.setItem` de tokens; CA6 lo verifica en unitarias y e2e. |
| R2 | Exfiltración tras XSS a otro dominio (B5). | `connect-src 'self'`, `form-action 'self'`, sin orígenes externos en ninguna directiva (ADR-0012); `verificar-csp.mjs` en `lint`. |
| R3 | Fuga del token a terceros. | `authInterceptor` solo adjunta a URLs relativas `/api/`; prueba con URL absoluta externa. |
| R4 | Redirección abierta con `?volver=`. | `rutaInternaSegura` con lista de vectores (CA10). |
| R5 | Código de la API simulada en producción (credenciales de ejemplo, bypass de login). | Inclusión solo por `fileReplacements` en `mocks`/`e2e`; CA15 busca el marcador en los bundles `production` y `development`; aviso visible "Modo simulado". Las credenciales simuladas no existen en el backend real. |
| R6 | Enumeración de usuarios y fuerza bruta. | Mensaje único para 401; manejo de 429 con `Retry-After`; el bloqueo real lo aplica el backend (E0.3). |
| R7 | Bucle de refresh o tormenta de peticiones. | Refresh single-flight, marca `REINTENTADA`, un solo reintento, `restaurar` con timeout de 5 s. |
| R8 | Guards interpretados como control de acceso. | Documentado como UX; el backend aplica RBAC (E0.3) y QA de E0.3 prueba 401/403 por endpoint. |
| R9 | Divulgación de detalles internos en errores. | Solo se muestra `problem+json` validado; 5xx con mensaje fijo y código de referencia; nunca cuerpos HTML/texto del proxy. |
| R10 | Clickjacking y fuga de referer. | `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `Referrer-Policy`. |
| R11 | Cadena de suministro npm. | Versiones exactas, `package-lock.json` obligatorio con `npm ci`, `engine-strict`, `npm audit --audit-level=high`; generador de cliente fijado y código generado revisable en el diff. `--ignore-scripts` en la imagen se evalúa en E1.12 (esbuild/lmdb). |
| R12 | Caché de `index.html` con nonce reutilizado. | `Cache-Control: no-store` en la `location /`; los recursos con hash son inmutables. |
| R13 | CSRF sobre `/auth/refresh`. | Mismo origen, cookie `SameSite=Strict` y `Path=/api/v1/auth` (propuesta a E0.3), sin CORS para el panel. |

## 8. Coordinación con otras épicas (archivos compartidos)

Este plan **no edita** `Makefile`, `infra/docker-compose.yml`, `.dockerignore` ni `backend/`. El orquestador aplica estos cambios cuando E0.2 haya cerrado los suyos.

### 8.1 `Makefile` (urgente: al terminar F1)
En cuanto exista `frontend/package.json`, `make check` ejecuta `check-frontend`, que hoy falla por dos motivos: `npm run test -- --run` no es un argumento válido del builder de Angular 22, y `ng` exige Node ≥ 22.22.3 (el sistema tiene 22.22.2). Eso rompería el hook de Stop también para los agentes de E0.2. Cambio propuesto:
```make
NODE_FRONT := $(shell cat frontend/.nvmrc 2>/dev/null)
NPM_FRONT  := $(shell node -e "const [a,b,c]=process.versions.node.split('.').map(Number);process.stdout.write(a>22||(a===22&&(b>22||(b===22&&c>=3)))?'npm':'npx -y -p node@$(NODE_FRONT) -- npm')" 2>/dev/null)

check-frontend: ## eslint + tsc + vitest + build + i18n (Node >= 22.22.3; ver frontend/.nvmrc)
	@if [ -f frontend/package.json ]; then cd frontend && $(NPM_FRONT) run verificar; else echo "frontend no inicializado"; fi
```
Opcional: en `dev`, el texto de ayuda del frontend pasa a `cd frontend && npm start` (API real) o `npm run start:mocks`; objetivo nuevo `e2e-front: cd frontend && $(NPM_FRONT) run e2e`. El objetivo `e2e` basado en Compose (que E0.2 está modificando) queda para E0.5.

### 8.2 `infra/docker-compose.yml`
Servicio `web`: quitar `profiles: ["web"]` para que `docker compose up` sirva el panel (hito M0); `depends_on: { api: { condition: service_healthy } }`; `healthcheck: { test: ["CMD", "wget", "-q", "--spider", "http://127.0.0.1:8080/"], interval: 15s, timeout: 5s, retries: 5 }`. El resto de su configuración (`read_only`, `tmpfs`, `cap_drop`, puerto `127.0.0.1:4200:8080`) se mantiene. No hace falta `CORS_ORIGENES` para el panel.

### 8.3 `.dockerignore` (raíz)
Añadir `frontend/coverage`, `frontend/test-results`, `frontend/playwright-report` y `frontend/e2e`.

### 8.4 Solicitudes al backend (fuera de E0.4)
- `crear_app`: `generate_unique_id_function=lambda ruta: ruta.name` para `operationId` cortos (ADR-0013). Tras el cambio: `npm run api:exportar && npm run api:generar` y ajustar las importaciones en `features/inicio`.
- E0.3: publicar `LoginIn`, `SesionOut`, `UsuarioSesion` con la forma de §4.4 (o avisar del cambio), cookie `refresh` con `Path=/api/v1/auth`, confirmar la tabla de roles de §4.8 (si `admin` hereda permisos de `operador` y `auditor`) y decidir el acceso a OpenAPI en producción.

### 8.5 Entorno
Los agentes necesitan Node ≥ 22.22.3 en cada comando (§3). Si el orquestador prefiere una solución global (`nvm install 22.23.3` y ponerlo en el `PATH` de la sesión), es decisión suya; el plan no modifica la configuración del entorno.

## 9. Resultado de QA

Ejecutado el 2026-09-28 por QA (Q1 a Q10) sobre el commit `feat(frontend)` de E0.4 más los cambios de esta sección (sin commit). Node 22.23.3 vía `npx -y -p node@22.23.3 --`; Playwright 1.56.1 con `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, `CI=1` para no reutilizar servidores previos.

### 9.1 Comandos ejecutados

| Comando | Resultado |
|---|---|
| `npm ci` | 462 paquetes, 0 vulnerabilidades, 10 s. |
| `npm run verificar` (inicial, antes de tocar nada) | rc 0: lint 0 errores y 0 avisos; estilos (76 archivos) y CSP correctos; tsc app y spec; Vitest 22 archivos, 279 pruebas; build de producción sin avisos de presupuesto (inicial 340,12 kB); i18n 80 mensajes al día. |
| `npm run verificar` (final) | rc 0: estilos 81 archivos sin hallazgos; **Vitest 27 archivos, 401 pruebas pasadas + 2 `fail` esperadas (BUG-02, BUG-03)**; inicial 341,39 kB brutos / 95,51 kB transferidos; i18n al día; 38,8 s. |
| `npm run e2e` inicial, 2 ejecuciones | 1.ª: 31 de 31. 2.ª: 30 de 31, falla `a11y.spec.ts` "teclado" (BUG-01, prueba con carrera; 6 de 25 fallos en `--repeat-each=25`). Corregida la sincronización. |
| `npm run e2e` final, 2 ejecuciones | 1.ª: 51 de 52 (fallo de mi propia prueba de tema por leer `data-tema` sin espera; corregida). 2.ª: 52 de 52. Después, `--repeat-each=6` de `calidad` y `a11y`: 168 de 168. Con `API_DESTINO=http://127.0.0.1:8000` (incluye `@backend`): 54 de 54. |
| `npm run api:verificar` | rc 0, sin diferencias en `openapi/` ni `src/app/core/api/generado/` (3 modelos, 1 servicio). |
| `npm audit --audit-level=high` | 0 vulnerabilidades. |
| `npm run bundles:verificar` (script nuevo) | `production`: sin marcadores; `development`: sin marcadores; `e2e`: `X-Api-Simulada`, `prueba-panel-local`, `@viamatica.test`. |
| ESLint con un archivo temporal prohibido (borrado) | Detecta `console`, `eval`, `new Function`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `setTimeout(string)`, `any`, `style=` y atributos sin i18n. `[innerHTML]` lo detecta `verificar-estilos.mjs` (ver BUG-06). |
| Nginx real (paquete `nginx` 1.24 de Ubuntu extraído en el scratchpad, no la imagen 1.27) con `infra/nginx.conf` y `infra/nginx-cabeceras-panel.conf` reales, `root` sobre `dist/panel/browser` y un backend de prueba local | `nginx -t` correcto (los únicos cambios: rutas absolutas, puerto 18080 y `api` reemplazado por `127.0.0.1:18000`). Ver 9.4. |

### 9.2 Criterio de aceptación, prueba y resultado

| CA | Prueba que lo cubre | Resultado |
|---|---|---|
| CA1 | `npm ci`; `node -e` sobre `package.json` (0 rangos; `engines` `^22.22.3 \|\| ^24.15.0`); `.npmrc` `engine-strict=true`, `save-exact=true`; lockfile versionado | Cumple. |
| CA2 | `grep -c '"node_modules/zone.js"' package-lock.json` = 0; sin `provideZoneChangeDetection` ni `zone.js` en `src/`, `angular.json`, `package.json` | Cumple. |
| CA3 | `npm run verificar` completo | Cumple (rc 0 dos veces). |
| CA4 | `verificar-cobertura.mjs`: `core/` líneas 97,91 % y ramas 94,67 %; `shared/` líneas 100 % y ramas 93,75 %; global sentencias 97,69 %, ramas 93,21 %, funciones 96,93 %, líneas 98,2 % | Cumple (≥ 80 %). |
| CA5 | Build de producción sin avisos; inicial 341,39 kB; el chunk perezoso mayor (`login-page`) 150,79 kB | Cumple. |
| CA6 | `sesion.store.spec` y `login.page.spec` (espías sobre `Storage`, cookie y consola); `cadena-http.spec` (token solo en la cabecera); e2e `login.spec` y `calidad.spec` (claves `vm.*` únicas, sin token en URLs, 0 mensajes de consola, recarga vuelve a `/login`) | Cumple. |
| CA7 | `auth.interceptor.spec`; `cadena-http.spec` (URLs absolutas, `//host`, `/apiario`, `api/...`, `/API/...`; login/refresh/logout con query; 401 persistente; reintento con 401 = 3 peticiones y un solo refresh; navegación única a `/login?volver=`) | Cumple. Excepción menor BUG-02 (barra final). |
| CA8 | `correlacion.interceptor.spec`; `cadena-http.spec` (petición, refresh y reintento = 3 UUID v4 distintos; sin cabecera hacia terceros); e2e `calidad` (3 peticiones reales de salud con 3 ids distintos) | Cumple. |
| CA9 | `error-app.spec` (tabla de §12, estado 0, HTML de proxy, `Content-Type` con parámetros, `Retry-After`, `errores[]`, `comprobaciones`); `cadena-http.spec` (500/502/503 con cuerpo ajeno y vacío, `null`, 429, red) | Cumple. |
| CA10 | `guards.spec` (matriz desde `navegacion.ts`); **`matriz-roles-plan.spec` (matriz escrita a mano desde §4.8, 33 casos + roles vacíos, desconocido y combinados)**; `ruta-segura.spec` y `ruta-segura.vectores.spec` (más de 50 vectores); e2e `guards.spec` | Cumple. La matriz de `guards.spec` se generaba desde `navegacion.ts` y no detectaría un error de datos: cubierto por la nueva. |
| CA11 | `login.page.spec`; `login.page.limites.spec` (doble envío síncrono = 1 llamada, correo/contraseña hostiles, 100 000 caracteres); e2e `login.spec` y `calidad` (HTML en el correo, emoji y 5 000 caracteres, doble Enter cuenta un intento) | Cumple. Excepción menor BUG-03 (sin límite de longitud de contraseña). |
| CA12 | `vm-shell.spec`, `layout-principal.spec`, `preferencias-ui.spec`; e2e `shell.spec`; e2e `calidad` (360 px sin scroll horizontal, menú móvil con Escape y foco, tema persistido) | Cumple tras BUG-04. |
| CA13 | `inicio.page.spec`; e2e `calidad` (500, 502 HTML, red caída con recuperación, 503 `no_listo` sin detalles); e2e `salud.backend.spec` con backend real | Cumple. `salud.backend.spec` acepta "listo" o "no listo" (no fuerza la falla); la falla queda cubierta con la respuesta 503 simulada. |
| CA14 | `npm run api:verificar` | Cumple (rc 0). |
| CA15 | **`scripts/verificar-bundles.mjs` (nuevo, `npm run bundles:verificar`)** sobre los tres builds | Cumple. No forma parte de `verificar` (compila tres veces, unos 40 s). |
| CA16 | `verificar-csp.mjs`; `csp.spec`; comprobación propia de que la CSP es idéntica en ADR-0012, `nginx-cabeceras-panel.conf`, `verificar-csp.mjs` y `docs/06`; nginx real (9.4) | Cumple. |
| CA17 | `ng lint` (regla `template/i18n` con `checkId`); `i18n:verificar`; `<html lang="es">`, `sourceLocale` `es`, `DEFAULT_CURRENCY_CODE` `USD` | Cumple. |
| CA18 | `verificar-estilos.mjs`; `tokens-contraste.spec`; recálculo independiente en Python de 24 pares en claro y oscuro (coincide con la prueba: mínimo 4,89 en texto; `--vm-borde` sobre superficie 2,06 en claro no se usa en ningún componente) | Cumple. |
| CA19 | `a11y.spec` (axe en `/login`, `/inicio`, `/sin-permiso`, claro y oscuro; teclado y foco) | Cumple, pero antes de BUG-05 la variante oscura de `/login` se ejecutaba en claro (falso positivo). Ahora es real y pasa. |
| CA20 | `ng lint` con el archivo temporal prohibido; búsqueda en `src/`: solo `preferencias-ui.ts` toca `localStorage`, con claves `vm.*`; `npm audit` 0 | Cumple. |
| CA21 | No ejecutable: Docker sin daemon | **Pendiente de ejecutar con Docker.** Evidencia parcial con Nginx real en 9.4; no la sustituye. |

### 9.3 Defectos

| ID | Severidad | Defecto | Reproducción y evidencia | Estado |
|---|---|---|---|---|
| BUG-04 | Media | La barra superior desborda en 360 px: scroll horizontal y el botón del menú de usuario queda fuera de pantalla. | Viewport 360 x 740, login con cualquier rol: `scrollWidth` 453 frente a `innerWidth` 360 (320 px igual); el botón termina en x = 435. Causa: el nombre de usuario, la marca y el aviso no se contraen. | **Corregido** en `frontend/src/app/shared/ui/shell/vm-shell.scss` (`.vm-marca` con elipsis, `@media (width < 600px)` oculta el nombre visible y reduce el chip). Pruebas: `e2e/calidad.spec.ts` (360 px en `/login`, `/inicio`, `/sin-permiso`). |
| BUG-05 | Media | El tema (preferencia guardada o `prefers-color-scheme`) no se aplica fuera del shell: en `/login` `data-tema` queda sin definir. `TemaService` solo se instanciaba en `LayoutPrincipal`. Además la prueba axe del tema oscuro en `/login` se ejecutaba en claro. | Guardar `vm.tema=oscuro`, abrir `/login`: `document.documentElement.dataset.tema` es `undefined` (`calidad.spec`, 4 fallos antes de la corrección). | **Corregido** en `frontend/src/app/app.ts:9-16` (la raíz inyecta `TemaService`). Pruebas: `app.spec.ts` y `e2e/calidad.spec.ts` (4 casos de tema); axe oscuro de `/login` pasa. |
| BUG-06 | Baja | `verificar-estilos.mjs` no detectaba `bind-innerHTML`, `[attr.innerHTML]`, `[srcdoc]` ni plantillas en línea dentro de `.ts` (CA20). | Probado con `revisarArchivo()` sobre cinco variantes: cuatro sin detección. | **Corregido** en `frontend/scripts/verificar-estilos.mjs` (expresión ampliada y revisión de `.ts` no spec). |
| BUG-01 | Baja | Pulsar Escape durante la animación de apertura del menú de usuario deja el foco en `<body>` en vez de volver al botón (WCAG 2.4.3). La prueba del agente frontend lo golpeaba de forma intermitente. | `a11y.spec.ts` "teclado", `--repeat-each=25`: 6 fallos ("Received: inactive"). Con espera a que el foco esté en el elemento del menú: 25 de 25. | Prueba corregida con una espera de foco (sincronización, no debilitamiento). El comportamiento de Material en esa ventana de milisegundos queda como observación. |
| BUG-02 | Baja | `/api/v1/auth/login/` (barra final) lleva `Authorization` porque `RUTAS_SIN_TOKEN` compara igualdad exacta. La aplicación nunca usa esa forma. | `cadena-http.spec.ts`: `it.fails('BUG-02: ...')`. | Abierto. Arreglo sugerido: normalizar la barra final en `ruta()` de `frontend/src/app/core/auth/auth.interceptor.ts:25`. Al corregirlo, quitar `.fails`. |
| BUG-03 | Baja | La contraseña no tiene límite de longitud en el cliente: 100 000 caracteres viajan al servidor (el correo sí queda acotado por el validador). | `login.page.limites.spec.ts`: `it.fails('BUG-03: ...')`. | Abierto. Arreglo sugerido: `maxlength="1024"` en `login.page.html` y regla `maxLength` en el esquema. |

Observaciones sin numerar:
- `.claude/agents/frontend.md:16` y `.claude/agents/qa.md:18` siguen indicando `npm run test -- --run`, que en Angular 22 falla con `Unknown argument: run`. El skill `angular-viamatica` ya lo corrige (usa `npm run test:ci` o `npm run verificar`). Sin editar; corresponde al orquestador.
- `prettier --check` no forma parte de `verificar` y hay dos archivos sin formato: `src/app/core/auth/auth.interceptor.spec.ts` y `src/app/shared/ui/README.md`.
- `e2e/shell.spec.ts` (prueba de 800 px) encadena `.catch(() => undefined)` tras `iniciarSesion`, lo que oculta un fallo de login. Pasa hoy; conviene quitar el `catch` y esperar al botón de menú.
- `rutaInternaSegura` decodifica hasta tres niveles; un vector con cinco niveles de `%25` se conserva, pero `navigateByUrl` solo decodifica una vez, por lo que no es explotable.
- Los guards son de experiencia de usuario (R8): las pruebas de autorización real (401/403 por endpoint) corresponden a E0.3.

### 9.4 CA21 pendiente y evidencia parcial con Nginx real

Comandos exactos para una máquina con Docker:
```
docker build -f infra/Dockerfile.web -t agente-correo-web .
docker run --rm agente-correo-web nginx -t
docker compose -f infra/docker-compose.yml up -d web
curl -sI http://127.0.0.1:4200/            # dos veces: nonce distinto en la CSP, Cache-Control: no-store
curl -sI http://127.0.0.1:4200/main-<hash>.js   # Cache-Control: public, max-age=31536000, immutable
curl -si http://127.0.0.1:4200/api/v1/salud     # respuesta del backend con sus cabeceras, sin la CSP del panel
docker inspect --format '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}}' <contenedor>
```
Evidencia local (Nginx 1.24 de Ubuntu, configuración real del repositorio con rutas y puerto adaptados; no es la imagen `nginxinc/nginx-unprivileged:1.27`): `nginx -t` correcto; `/` responde 200 con CSP idéntica a ADR-0012 y `Cache-Control: no-store`; tres peticiones a `/agentes` dan tres nonces distintos y en cada respuesta el nonce de la cabecera coincide con `ngcspnonce` del HTML (el atributo sale en minúsculas del build); `__CSP_NONCE__` no queda sin sustituir; `main-*.js` con `public, max-age=31536000, immutable` y CSP; `/api/v1/salud` llega al backend de prueba sin CSP ni `X-Frame-Options` del panel; `/nada.js` 404; con `Accept-Encoding: gzip` `sub_filter` sigue funcionando; un cuerpo de 2 MB a `/api/` recibe 413. Sigue sin verificarse: el build de la imagen, `USER 101`, `read_only` y `tmpfs`, y `nginx -t` con la versión 1.27.

### 9.5 Pruebas y archivos añadidos por QA

- Vitest: `src/app/core/http/cadena-http.spec.ts`, `src/app/core/auth/matriz-roles-plan.spec.ts`, `src/app/core/auth/ruta-segura.vectores.spec.ts`, `src/app/core/auth/sesion.restaurar-limite.spec.ts`, `src/app/features/login/login.page.limites.spec.ts`, caso nuevo en `src/app/app.spec.ts`.
- Playwright: `e2e/calidad.spec.ts` (21 pruebas), sincronización de foco en `e2e/a11y.spec.ts`.
- Scripts: `scripts/verificar-bundles.mjs` y `npm run bundles:verificar` (CA15).
- Correcciones de código: BUG-04 (`vm-shell.scss`), BUG-05 (`app.ts`), BUG-06 (`verificar-estilos.mjs`).

## 10. Cierre y revisión de seguridad

_Pendiente._
