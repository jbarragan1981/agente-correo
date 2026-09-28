# ADR-0005 · Angular 22 zoneless con signals, Angular Material y Tailwind

**Estado:** Aceptada · 2026-09-28

## Contexto
Se pide la última versión de Angular con un diseño empresarial estilo Viamatica, dashboard de observabilidad y formularios de configuración complejos.

## Decisión
Angular 22.2 standalone y zoneless; signals, `resource()` y Signal Forms; `@ngrx/signals` para stores; Angular Material 22 con tema M3 personalizado a partir de los tokens de marca (`#3AAFDE`, `#1B3A5C`, `#00D4FF`, `#F0F6FA`...) y Tailwind 4 para layout; ECharts para gráficas; Vitest y Playwright.

## Alternativas descartadas
- PrimeNG: buen kit, pero Material ofrece mejor accesibilidad de base y el equipo lo conoce.
- Solo Tailwind + componentes propios: más lento para el nivel de accesibilidad requerido.
- RxJS-first con NgRx Store clásico: más boilerplate para el tamaño del proyecto.

## Consecuencias
- (+) Rendimiento y bundles menores sin zone.js; código más simple.
- (−) Signal Forms sigue marcada experimental en 21/22: se aísla en `shared/forms` para poder volver a Reactive Forms si cambia la API.
