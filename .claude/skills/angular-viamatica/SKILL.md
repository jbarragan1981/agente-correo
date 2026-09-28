---
name: angular-viamatica
description: >-
  Convenciones del frontend Angular 22 de Agente Correo y del sistema de diseño Viamatica: proyecto zoneless con signals, Signal Forms, stores @ngrx/signals, Angular Material con tema M3 personalizado, Tailwind 4 con tokens de marca, componentes base shared/ui, gráficas ECharts con paleta corporativa, accesibilidad, seguridad del cliente, pruebas Vitest/Playwright y presupuestos de bundle. Úsalo al crear o modificar cualquier cosa en frontend/.
---

# Angular 22 · estilo Viamatica

Referencia completa: `docs/06-frontend-angular.md`.

## Arranque del proyecto (una vez)
```
cd frontend
npx @angular/cli@22 new panel --standalone --style=scss --routing --ssr=false --skip-git --package-manager=npm
npm i @angular/material@22 @angular/cdk@22 @ngrx/signals@22 echarts@6 ngx-echarts@22 tailwindcss@4 @tailwindcss/postcss
ng add @angular/material  # tema personalizado, tipografía Inter, animaciones
```
`app.config.ts`: `provideZonelessChangeDetection()`, `provideRouter(routes, withComponentInputBinding(), withViewTransitions())`, `provideHttpClient(withInterceptors([authInterceptor, errorInterceptor]))`, `provideAnimationsAsync()`, `provideEchartsCore({ echarts: () => import('echarts') })`.

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
Tema Material M3: `primary` desde `#3AAFDE`, `tertiary` desde `#1B3A5C`, `error` `#D64545`, superficie `#F0F6FA`, tipografía Inter. Tailwind: `@theme { --color-vm-marca: var(--vm-azul-marca); … }` para usar `bg-vm-marca`, `text-vm-oscuro`.

Prohibido: hex fuera de `tokens.css`, estilos inline, `!important` salvo override documentado de Material.

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
npm run lint && npx tsc --noEmit -p tsconfig.app.json && npm run test -- --run && npm run build -- --configuration production
```
Presupuestos en `angular.json`: inicial 600 KB warn / 800 KB error; por ruta 250 KB. Accesibilidad: `npx playwright test e2e/a11y.spec.ts` (axe) en flujos críticos.
