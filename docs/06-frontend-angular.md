# 06 · Frontend Angular · Panel de operación (estilo Viamatica)

## 1. Base técnica

- **Angular 22.2**, proyecto standalone, **zoneless** (`provideZonelessChangeDetection()`), signals en todo el estado local, `resource()`/`httpResource()` para datos, **Signal Forms** para formularios, control flow `@if/@for`.
- **@ngrx/signals** para stores de dominio (`AgentesStore`, `CuentasStore`, `MensajesStore`, `MetricasStore`, `SesionStore`).
- **Angular Material 22** con tema personalizado (M3) + **Tailwind 4** para layout y utilidades. Sin CSS ad hoc fuera de los tokens.
- **ECharts 6** vía `ngx-echarts` para el dashboard (carga diferida del módulo).
- **Rutas con carga perezosa** por feature, guards por rol, `withComponentInputBinding()`.
- **Vitest** para unitarias, **Playwright** para e2e (flujos críticos: login, aprobar borrador, editar prompt, playground).
- i18n: `@angular/localize` con `es` por defecto; textos en `src/locale/messages.es.xlf`.
- Accesibilidad: componentes Material, foco visible, contraste AA validado con los tokens de abajo.

## 2. Estructura

```
frontend/src/app/
├── core/            # auth (interceptor, guards, SesionStore), api client generado desde OpenAPI, manejo de errores, layout shell
├── shared/          # ui kit Viamatica (botones, cards, kpi-tile, badge-categoria, tabla-datos, dialogo-confirmar), pipes, directivas
├── features/
│   ├── dashboard/   # KPIs, series, costos, categorías, salud de cuentas
│   ├── bandeja/     # lista de mensajes clasificados, detalle, hilo, corrección de categoría
│   ├── aprobaciones/# cola de borradores, editor, aprobar/rechazar/regenerar
│   ├── agentes/     # lista, detalle, editor de prompt con versiones y diff, parámetros de modelo, playground
│   ├── cuentas/     # alta/edición de cuentas de correo, prueba de conexión, estado de sync
│   ├── taxonomia/   # categorías, umbrales, acciones
│   ├── webchat/     # sesiones, transcripciones, tomar control, configuración de sitios
│   ├── proveedores/ # credenciales (solo escritura), prueba, modelos disponibles, precios
│   ├── usuarios/    # gestión de usuarios y roles
│   └── auditoria/   # registro con filtros
└── widget/          # aplicación separada (build independiente): widget embebible del webchat
```

## 3. Sistema de diseño Viamatica

### 3.1 Tokens de color (CSS variables, `styles/tokens.css`)

| Token | Hex | Uso |
|---|---|---|
| `--vm-azul-oscuro` | `#1B3A5C` | Títulos, sidebar, texto principal sobre claro |
| `--vm-azul-medio` | `#2E86C1` | Subtítulos, enlaces, estados informativos |
| `--vm-azul-marca` | `#3AAFDE` | Color primario: botones, tabs activos, foco |
| `--vm-azul-claro` | `#5BC0EB` | Bordes, chips, hover |
| `--vm-cyan` | `#00D4FF` | CTA sobre fondo oscuro, acentos de gráficas |
| `--vm-blanco` | `#FFFFFF` | Fondo principal |
| `--vm-gris-fondo` | `#F0F6FA` | Fondo de cards y paneles |
| `--vm-gris-texto` | `#4A5568` | Texto secundario |
| `--vm-oscuro` | `#0D1B2A` | Fondo modo oscuro / topbar |
| `--vm-oscuro-footer` | `#0A1628` | Footer / sidebar en oscuro |
| `--vm-exito` | `#1E9E6A` | Estados OK |
| `--vm-alerta` | `#E0A100` | Advertencias, confianza media |
| `--vm-error` | `#D64545` | Errores, riesgo alto |

Modo oscuro: mismos tokens con fondos `--vm-oscuro`/`--vm-oscuro-footer`, texto `#E6F1F8`, primario `--vm-cyan`. Se activa con `prefers-color-scheme` y toggle persistido.

**Variantes de texto con contraste AA** (E0.4). Varios colores de marca no alcanzan 4,5:1 como texto: blanco sobre `#3AAFDE` = 2,51; `#2E86C1` sobre blanco = 3,97; `#D64545` sobre blanco = 4,38; blanco sobre `#1E9E6A` = 3,41. Por eso existen estos tokens y los componentes los usan para texto:

| Token | Claro | Oscuro | Uso |
|---|---|---|---|
| `--vm-texto-sobre-marca` | `#0D1B2A` (6,93 sobre `#3AAFDE`) | `#0D1B2A` | Texto de botones primarios rellenos. |
| `--vm-enlace` | `#1F6FA3` | `#5BC0EB` | Enlaces y texto informativo pequeño. |
| `--vm-error-texto` | `#B83232` | `#FF8A8A` | Mensajes de error bajo campos. |
| `--vm-exito-texto` | `#157A52` | `#5FD3A2` | Texto de estado OK. |
| `--vm-alerta-texto` | `#8A6300` | `#F2C94C` | Texto de advertencia. |
| `--vm-foco` | `#1B3A5C` | `#00D4FF` | Anillo de foco (2 px + 2 px de separación). `--vm-foco-inverso` (`#00D4FF`) sobre sidebar y topbar. |

Reglas: `#3AAFDE` solo como relleno con texto `--vm-texto-sobre-marca`, bordes e indicadores; `#2E86C1` solo en texto ≥ 24 px o iconos; `#D64545` y `#1E9E6A` como fondo de chips con texto oscuro o como borde/icono. Además hay tokens semánticos (`--vm-fondo-pagina`, `--vm-superficie`, `--vm-texto`, `--vm-texto-secundario`, `--vm-sidebar-*`, `--vm-topbar-*`, `--vm-aviso-*`) que cambian con el tema. La prueba `core/layout/tokens-contraste.spec.ts` calcula todos los pares en claro y oscuro desde `tokens.css` y exige ≥ 4,5 (texto) / ≥ 3 (UI). El primario de Material se mantiene en el tono M3 generado (`_paleta-m3.scss`, que cumple AA como texto); la marca se aplica a botones rellenos con `mat.button-overrides`.

Paleta categórica para gráficas (orden fijo): `#3AAFDE, #1B3A5C, #00D4FF, #2E86C1, #5BC0EB, #4A5568, #E0A100, #1E9E6A`. Secuencial: `#F0F6FA → #5BC0EB → #2E86C1 → #1B3A5C`. Divergente (riesgo): `#1E9E6A → #F0F6FA → #D64545`.

### 3.2 Tipografía

- Familia: **Inter variable** autoalojada (`@fontsource-variable/inter`, `font-display: swap`), fallback `system-ui`. Iconos con **Material Icons** autoalojados (`@fontsource/material-icons`, ligaduras en `<mat-icon>`). Sin Google Fonts: la CSP no admite orígenes externos (ADR-0012).
- Utilidades Tailwind: `vm-titulo-pagina`, `vm-titulo-seccion`, `vm-cuerpo`, `vm-etiqueta`, `vm-kpi` (en `src/styles/tailwind.css`, que va separado de `styles.scss` porque Tailwind 4 no admite Sass).
- Escala: título de página 28/36 semibold, sección 20/28 semibold, cuerpo 14/20, etiquetas 12/16 medium, KPI 32/40 bold con `font-variant-numeric: tabular-nums`.

### 3.3 Componentes base (`shared/ui`)

`vm-shell` (sidebar colapsable + topbar con buscador global y estado de cuentas), `vm-kpi-tile` (valor, delta, sparkline), `vm-card`, `vm-badge-categoria` (color por categoría, icono), `vm-barra-confianza` (0..1 con umbral marcado), `vm-riesgo-chip` (bajo/medio/alto), `vm-tabla` (CDK table virtualizada, ordenable, con filtros persistidos en la URL), `vm-editor-prompt` (Monaco ligero o textarea con resaltado de placeholders, contador de tokens estimado, linter de seguridad), `vm-diff` (diff entre versiones), `vm-timeline-ejecucion` (pasos del grafo con tiempos y costo), `vm-dialogo-confirmar` (acciones destructivas con texto de confirmación).

Radio de bordes 12 px en cards, 8 px en controles; sombras suaves (`0 1px 2px rgba(13,27,42,.06), 0 4px 12px rgba(13,27,42,.06)`); densidad cómoda por defecto, compacta en tablas.

## 4. Pantallas y criterios de aceptación

### 4.1 Login
Email + contraseña, mensajes de error genéricos, bloqueo tras 5 intentos (backend), soporte de "recordar sesión" solo vía refresh cookie. Sin auto-completar de secretos en campos de configuración.

### 4.2 Dashboard (observabilidad)
- Fila de KPIs (24 h / 7 d / 30 d): correos procesados, % clasificados automáticamente, precisión (según correcciones), pendientes de aprobación, costo USD, latencia p95, tasa de error, sesiones de webchat.
- Gráficas: volumen por hora apilado por categoría; costo por proveedor/modelo (barras); latencia p50/p95 por agente (líneas); distribución de confianza (histograma) con umbral; salud de cuentas (tabla con último sync y errores); top remitentes/dominios; riesgo detectado (cuarentena vs. revisados).
- Filtros globales: rango de fechas, cuenta, canal. Auto-refresh cada 60 s con `resource()` y `reload()`.
- Criterio: carga inicial < 2 s con 30 días de datos (usa vistas materializadas).

### 4.3 Bandeja
Lista virtualizada con columnas: fecha, cuenta, remitente, asunto, categoría (badge), confianza (barra), urgencia, riesgo, estado. Panel de detalle lateral: cuerpo saneado (HTML en `iframe sandbox` sin scripts), explicación de la decisión (probabilidades de Jev, verificaciones deterministas), traza de ejecución, acciones (reclasificar, corregir categoría, archivar, cuarentena, abrir borrador).

### 4.4 Aprobaciones
Cola de borradores con vista dividida: correo original (izquierda) y borrador editable (derecha) con citas y confianza. Botones: Aprobar y enviar, Editar y enviar, Regenerar con instrucciones, Rechazar. Atajos de teclado. Confirmación con resumen antes de enviar.

### 4.5 Agentes
- Lista: nombre, tipo, proveedor:modelo, versión activa, habilitado, métricas 24 h.
- Detalle en pestañas: **Configuración** (proveedor, modelo con selector alimentado por `/proveedores/{p}/modelos`, effort/max_tokens/umbrales, herramientas permitidas, modelo de respaldo), **Prompt** (editor, placeholders, linter, guardar como nueva versión, publicar, historial con diff y revertir), **Preguntas Jev** (editor visual de Noul/Choice/Score para agentes de decisión, sincronizado con la taxonomía), **Playground**, **Métricas**.
- Crear agente: asistente en 3 pasos (tipo y proveedor → prompt/preguntas → revisión).

### 4.6 Playground
Entrada según tipo de agente (correo sintético: remitente/asunto/cuerpo; o texto libre; o seleccionar un mensaje real anonimizado). Selector de versión y modelo override. Salida con streaming, panel de traza (pasos, tokens, costo, latencia), y comparación lado a lado con la versión activa. Historial personal.

### 4.7 Cuentas de correo
Formulario con Signal Forms: nombre, dirección, IMAP (host, puerto, TLS), SMTP, usuario, contraseña (campo de solo escritura, nunca se rellena desde el servidor), carpeta, modo de sync, taxonomía, política (envío automático, firma). Botón "Probar conexión" con resultado detallado. Estado en vivo (último UID, último sync, errores) vía polling de 15 s.

### 4.8 Taxonomía
CRUD de categorías con descripción para el modelo, umbral por categoría (slider), color, acciones ordenables (drag & drop CDK). Al guardar, propone regenerar la versión de preguntas del Clasificador.

### 4.9 Webchat
Sesiones activas y cerradas, transcripción con marcas de riesgo, botón "Tomar control" que abre un chat de operador. Configuración de sitios: orígenes permitidos, agente asignado, textos de bienvenida, colores del widget con vista previa.

### 4.10 Proveedores, Usuarios, Auditoría
Proveedores: tarjetas por proveedor con estado, credencial enmascarada, botón probar, tabla de precios editable. Usuarios: CRUD con roles y desactivación. Auditoría: tabla con filtros por actor/acción/entidad y exportación CSV.

## 5. Widget de webchat

Build separado (`ng build widget`) que produce un único `widget.js` (< 80 KB gz) con Shadow DOM, sin dependencias de Material. Se integra con `<script src=".../widget.js" data-sitio="clave_publica"></script>`. Usa los tokens Viamatica configurables por sitio. Reconexión automática del WebSocket, indicador de escritura, mensajes con Markdown limitado (sin HTML crudo).

## 6. Seguridad en el frontend

- Access token en memoria (signal), nunca en `localStorage`; refresh por cookie httpOnly.
- Interceptor con reintento único tras refresh y cierre de sesión en 401 persistente.
- Mismo origen: el panel llama solo a rutas relativas `/api/v1/...` (Nginx del contenedor `web` o `proxy.conf.json` en `ng serve` hacen de proxy). Sin CORS para el panel.
- CSP estricta por nonce (ADR-0012), única fuente `infra/nginx-cabeceras-panel.conf`: `default-src 'self'; script-src 'self'; style-src 'self' 'nonce-$request_id'; font-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; worker-src 'self'; manifest-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; require-trusted-types-for 'script'; trusted-types angular angular#bundler`. `index.html` lleva `<app-root ngCspNonce="__CSP_NONCE__">`, que Nginx sustituye por petición (`sub_filter`) y sirve con `Cache-Control: no-store`; producción usa `inlineCritical: false`. `npm run lint` ejecuta `scripts/verificar-csp.mjs` y `e2e/csp.spec.ts` comprueba 0 violaciones en Chromium.
- API simulada (ADR-0013): los builds `mocks` (`npm run start:mocks`) y `e2e` sustituyen `src/environments/proveedores-entorno.ts` por `proveedores-entorno.mocks.ts`, que añade `apiSimuladaInterceptor` (solo `/api/v1/auth/*`, respuestas con `X-Api-Simulada: 1`) y el aviso "Modo simulado". `production` y `development` no empaquetan ese código.
- Contenido de correos siempre en `iframe sandbox=""` con `srcdoc` saneado por el backend; sin `bypassSecurityTrust*`.
- Formularios de secretos con `autocomplete="new-password"` y sin eco del valor.
- Dependencias auditadas en CI (`npm audit --audit-level=high`).

## 7. Calidad

- ESLint con `angular-eslint` estricto, Prettier, `strictTemplates`, `noImplicitAny`.
- Cobertura mínima 80 % en `core` y `shared`; e2e para los 5 flujos críticos.
- Presupuestos de bundle en `angular.json`: inicial 500 kB aviso / 600 kB error (tamaño bruto), cualquier script ≤ 250 kB, estilos por componente 4 kB aviso / 8 kB error.
- Verificación local: `cd frontend && npm run verificar` (lint + estilos + CSP, tsc de app y spec, Vitest con cobertura y umbral por directorio, build de producción, i18n al día); e2e con `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers npm run e2e`.
- Lighthouse en CI (rendimiento ≥ 90, accesibilidad ≥ 95).
