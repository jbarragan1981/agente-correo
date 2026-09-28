# shared/ui · componentes base Viamatica

Componentes presentacionales (`OnPush`, sin servicios inyectados): reciben estado con `input()` / `input.required()` y avisan con `output()`. Colores solo con `var(--vm-*)` de `src/styles/tokens.css`. Cada componente tiene prueba Vitest junto al código y un ejemplo aquí.

## `vm-shell`

Topbar, sidebar colapsable (256 px / 72 px con tooltips) y área de contenido. En móvil (`movil = true`, < 1024 px) la sidebar pasa a modo `over` y aparece el botón de menú. Incluye "Saltar al contenido" como primer elemento enfocable y el aviso "Modo simulado".

| Entrada | Tipo | Descripción |
|---|---|---|
| `navegacion` | `EntradaMenu[]` (requerida) | `{ ruta, etiqueta, icono }` ya filtradas por rol. |
| `usuario` | `UsuarioSesion` (requerida) | Nombre, correo y roles del menú de usuario. |
| `colapsado` | `boolean` (requerida) | Sidebar colapsada en escritorio. |
| `movil` | `boolean` | Modo `over` con botón de menú. |
| `modoSimulado` | `boolean` | Muestra el aviso "Modo simulado". |
| `temaOscuro` | `boolean` | Estado del conmutador de tema (`aria-pressed`). |

| Salida | Cuándo |
|---|---|
| `alternarColapso` | Botón de colapsar/expandir. |
| `alternarTema` | Conmutador de tema. |
| `cerrarSesion` | "Cerrar sesión" del menú de usuario. |

```html
<vm-shell
  [navegacion]="navegacion()"
  [usuario]="usuario"
  [colapsado]="colapsado()"
  [movil]="movil()"
  [modoSimulado]="modoSimulado"
  [temaOscuro]="temaOscuro()"
  (alternarColapso)="alternarColapso()"
  (alternarTema)="alternarTema()"
  (cerrarSesion)="cerrarSesion()"
>
  <router-outlet />
</vm-shell>
```

El contenedor que lo usa es `core/layout/layout-principal.ts` (sesión, preferencias en `localStorage` `vm.sidebar.colapsado`/`vm.tema`, `BreakpointObserver`).

Pendientes (épicas posteriores): `vm-kpi-tile`, `vm-card`, `vm-badge-categoria`, `vm-barra-confianza`, `vm-riesgo-chip`, `vm-tabla`, `vm-editor-prompt`, `vm-diff`, `vm-timeline-ejecucion`, `vm-dialogo-confirmar`, `vm-estado-vacio`.
