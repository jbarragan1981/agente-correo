---
name: angular-viamatica
description: >-
  Convenciones del frontend Angular 22 de Agente Correo y del sistema de diseño Viamatica: proyecto zoneless con signals, Signal Forms, stores @ngrx/signals, Angular Material con tema M3 personalizado, Tailwind 4 con tokens de marca, componentes base shared/ui, gráficas ECharts con paleta corporativa, accesibilidad, seguridad del cliente, pruebas Vitest/Playwright y presupuestos de bundle. Úsalo al crear o modificar cualquier cosa en frontend/.
---

# Angular 22 · estilo Viamatica

Referencia completa: `docs/06-frontend-angular.md`.

## Proyecto (creado en E0.4)
Node ≥ 22.22.3 (`frontend/.nvmrc` = 22.23.3; con Node anterior: `npx -y -p node@22.23.3 -- npm run <script>`), TypeScript 6.0, dependencias con versión exacta (`save-exact`, `engine-strict`), `package-lock.json` obligatorio. ECharts y `ngx-echarts` no se instalan hasta E1.10.

`app.config.ts`: `provideZonelessChangeDetection()`, `provideRouter(routes, withComponentInputBinding(), withViewTransitions())`, `provideHttpClient(withFetch(), withInterceptors([correlacionInterceptor, authInterceptor, erroresInterceptor, ...interceptoresEntorno]))`, `provideApiConfiguration('')` (mismo origen), `TituloStrategy`, `DEFAULT_CURRENCY_CODE` `USD`, `provideAppInitializer(() => inject(SesionStore).restaurar())`. Material 22 no necesita `provideAnimationsAsync()`.

Piezas existentes que se reutilizan: `core/errores` (`ErrorApp`, `aErrorApp`, `errorDeRecurso`, contexto `SIN_TOKEN`/`SILENCIAR_ERRORES`/`REINTENTADA`), `core/auth` (`SesionStore`, guards `autenticadoGuard`/`invitadoGuard`/`rolGuard`, `rutaInternaSegura`), `core/layout/navegacion.ts` (única fuente de secciones y roles), `shared/forms/validadores.ts` (única entrada a Signal Forms), `shared/ui/shell` (`vm-shell`). Cliente de API: `npm run api:exportar && npm run api:generar` (ng-openapi-gen, ADR-0013); en features, `inject(Api).invoke(fn, params)` dentro de `resource()`. API simulada de auth en `npm run start:mocks` (usuarios `*@viamatica.test`, ver `frontend/README.md`).

## Tokens (`src/styles/tokens.css`)
```css
:root {
  --vm-azul-oscuro:#1B3A5C; --vm-azul-medio:#2E86C1; --vm-azul-marca:#3AAFDE; --vm-azul-claro:#5BC0EB;
  --vm-cyan:#00D4FF; --vm-blanco:#FFFFFF; --vm-gris-fondo:#F0F6FA; --vm-gris-texto:#4A5568;
  --vm-oscuro:#0D1B2A; --vm-oscuro-footer:#0A1628; --vm-exito:#1E9E6A; --vm-alerta:#E0A100; --vm-error:#D64545;
  --vm-radio-card:12px; --vm-radio-control:8px;
  --vm-sombra:0 1px 2px rgba(13,27,42,.06),0 4px 12px rgba(13,27,42,.06);
  --vm-fuente:"Inter",system-ui,sans-serif;
}
:root[data-tema="oscuro"] { --vm-blanco:#0D1B2A; --vm-gris-fondo:#122240; --vm-gris-texto:#B8C7D6; --vm-azul-oscuro:#E6F1F8; --vm-azul-marca:#00D4FF; }
```
Además, variantes AA para texto (`--vm-texto-sobre-marca`, `--vm-enlace`, `--vm-error-texto`, `--vm-exito-texto`, `--vm-alerta-texto`, `--vm-foco`, `--vm-foco-inverso`) y tokens semánticos por tema (`--vm-fondo-pagina`, `--vm-superficie`, `--vm-texto`, `--vm-texto-secundario`, `--vm-sidebar-*`, `--vm-topbar-*`); ver `docs/06-frontend-angular.md` §3.1. Blanco sobre `#3AAFDE` no cumple AA: la marca va como relleno con `--vm-texto-sobre-marca`.

Tema Material M3: paleta generada en `src/styles/_paleta-m3.scss` (`ng generate @angular/material:theme-color`, primario `#3AAFDE`, terciario `#1B3A5C`, error `#D64545`, neutro `#F0F6FA`; no se edita) + `mat.theme-overrides` / `mat.<componente>-overrides` con `var(--vm-*)`. Tipografía Inter variable y Material Icons autoalojadas (`@fontsource`). Tailwind 4 va en `src/styles/tailwind.css` (CSS aparte, Tailwind no admite Sass; sin preflight) con `@theme { --color-*: initial; --color-vm-marca: var(--vm-azul-marca); … }`: solo existen colores `vm-*`. No se aplican clases de color de Tailwind sobre componentes Material.

Prohibido: hex fuera de `tokens.css` (y del generado `_paleta-m3.scss`), estilos inline, `[innerHTML]`, `!important` salvo con comentario `// override-material:`. Lo comprueba `scripts/verificar-estilos.mjs` dentro de `npm run lint`.

## Patrones
- **Datos**: `resource({ params: () => filtros(), loader: ({params}) => api.listar(params) })`; estados `isLoading()`, `error()`, `value()`; botón "Reintentar" en error; `reload()` en auto-refresh (dashboard cada 60 s con `interval` + `takeUntilDestroyed`).
- **Stores**: `signalStore({ providedIn: 'root' }, withState(...), withComputed(...), withMethods(...))`; un store por dominio compartido; los componentes de una sola pantalla usan signals locales.
- **Formularios**: Signal Forms (`form(model, schema)`), validadores en `shared/forms/validadores.ts` (host sin esquema, puerto 1–65535, email, tamaño de prompt ≤ 32 KB), mensajes de error en español bajo el campo, `aria-describedby`.
- **Tablas**: `cdk-virtual-scroll-viewport` + `mat-table`, ordenación y filtros en query params, selección múltiple con acciones en lote solo donde el plan lo pida.
- **Diálogos**: `MatDialog` con `vm-dialogo-confirmar` para destructivos (escribir el nombre para confirmar), foco inicial en "Cancelar".
- **Rutas**: por feature con `loadChildren`; `canMatch: [rolGuard('admin')]`; títulos con `TitleStrategy` ("Agentes · Agente Correo").
- **Errores HTTP**: interceptor convierte `problem+json` en `ErrorApp` y muestra `MatSnackBar`; 401 → refresh una vez → logout.

## Componentes base obligatorios (`shared/ui`)
`vm-shell`, `vm-kpi-tile`, `vm-card`, `vm-badge-categoria`, `vm-barra-confianza`, `vm-riesgo-chip`, `vm-tabla`, `vm-editor-prompt`, `vm-diff`, `vm-timeline-ejecucion`, `vm-dialogo-confirmar`, `vm-estado-vacio`. Cada uno: inputs con `input.required()`, `output()`, `host` con clases, prueba Vitest y ejemplo en `shared/ui/README.md`.

## Gráficas (ECharts)
Paleta categórica en orden fijo `['#3AAFDE','#1B3A5C','#00D4FF','#2E86C1','#5BC0EB','#4A5568','#E0A100','#1E9E6A']`; secuencial `['#F0F6FA','#5BC0EB','#2E86C1','#1B3A5C']`; divergente riesgo `['#1E9E6A','#F0F6FA','#D64545']`. Opciones comunes en `shared/charts/tema-viamatica.ts` (tipografía Inter, grid, tooltip, `aria.enabled: true`). Cada gráfica con título, unidad, estado vacío y `@defer (on viewport)`.

## Seguridad del cliente
Token en `SesionStore` (signal) · refresh por cookie · sin `localStorage` para secretos · HTML de correo en `<iframe sandbox="" [srcdoc]>` con contenido saneado por el backend · sin `bypassSecurityTrust*` · `autocomplete="new-password"` en secretos · CSP en `nginx.conf` del contenedor `web`.

## Widget (`projects/widget`)
Sin Material; Shadow DOM (`ViewEncapsulation.ShadowDom`); un solo bundle `widget.js` < 80 KB gz; configuración por atributos `data-*`; WebSocket con reconexión exponencial; Markdown limitado (negrita, listas, enlaces con `rel="noopener"`), nunca HTML crudo.

## Verificación antes de terminar
```
cd frontend && npm run verificar      # lint (+ estilos + CSP), tsc app/spec, vitest con cobertura, build producción, i18n
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers npm run e2e    # Playwright 1.56.1 (login, guards, shell, CSP, axe)
npm run api:verificar                 # OpenAPI y cliente generado al día (requiere uv)
```
Con Node del sistema < 22.22.3: `npx -y -p node@22.23.3 -- npm run verificar` (o `make check-frontend`, que lo resuelve solo). Tras tocar plantillas o `$localize`: `npm run i18n:extraer`. `npm run test -- --run` no existe en el builder de Angular 22: usa `npm run test:ci`.

Presupuestos en `angular.json`: inicial 500 kB aviso / 600 kB error; cualquier script 250 kB error; estilos por componente 4/8 kB. Cobertura ≥ 80 % en `core/` y `shared/` (`scripts/verificar-cobertura.mjs`).
