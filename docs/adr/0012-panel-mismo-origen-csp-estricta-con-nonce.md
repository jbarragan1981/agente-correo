# ADR-0012 · Panel en el mismo origen que la API con CSP estricta por nonce y recursos autoalojados

**Estado:** Aceptada · 2026-09-28 · Épica E0.4 · Cierra la observación B5 de E0.1

## Contexto

La CSP de `infra/nginx.conf` heredada de E0.1 tenía `connect-src 'self' http://localhost:8000 ws://localhost:8000 https: wss:` (cualquier host HTTPS o WSS: exfiltración trivial tras un XSS), `style-src 'unsafe-inline' https://fonts.googleapis.com`, `font-src https://fonts.gstatic.com` y `base-uri 'none'`. `docs/06-frontend-angular.md` §6 pedía revisar `'unsafe-inline'` con nonce.

Verificación del arquitecto (2026-09-28, build real de Angular 22.2 + Material 22.2 + Tailwind 4.3 servido con cabeceras equivalentes y Chromium de Playwright):

- `base-uri 'none'` bloquea el `<base href="/">` que Angular necesita para rutas profundas.
- El CSS crítico en línea (`optimization.styles.inlineCritical`, activo por defecto) inyecta un `<script>` en línea y un `<link media="print">` que exigen `'unsafe-inline'` o nonce en `script-src`.
- Con `ngCspNonce` en `<app-root>`, Angular propaga el nonce a sus `<style>` y al `<script type="module">`; con `inlineCritical: false` basta `script-src 'self'`.
- `require-trusted-types-for 'script'; trusted-types angular angular#bundler` no produce violaciones con Material (snackbar, tooltip, sidenav, toolbar) ni con rutas perezosas.
- Inter y Material Icons se sirven desde npm (`@fontsource-variable/inter`, `@fontsource/material-icons`) sin dominios externos. `material-symbols` pesa 4 MB por estilo y se descarta.

## Decisión

1. **Mismo origen.** El panel habla con la API solo por rutas relativas `/api/v1/...`. En contenedor, Nginx del servicio `web` hace de proxy de `/api/` hacia `api:8000`; en desarrollo, `ng serve` usa `proxy.conf.json` hacia `http://localhost:8000`. `rootUrl` del cliente generado es `''`. El panel no necesita CORS; `CORS_ORIGENES` queda para despliegues con otro origen, que no forman parte de la Fase 1.
2. **CSP del panel** (única fuente: `infra/nginx-cabeceras-panel.conf`, incluida en las `location` del panel):
   `default-src 'self'; script-src 'self'; style-src 'self' 'nonce-$request_id'; font-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; worker-src 'self'; manifest-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; require-trusted-types-for 'script'; trusted-types angular angular#bundler`.
3. **Nonce por petición.** `index.html` lleva `<app-root ngCspNonce="__CSP_NONCE__">`; Nginx sustituye el marcador con `sub_filter` por `$request_id` (16 bytes aleatorios) y sirve `index.html` con `Cache-Control: no-store`.
4. **Sin CSS crítico en línea** en producción (`inlineCritical: false`).
5. **Recursos autoalojados**: tipografía Inter variable y Material Icons desde paquetes npm; ningún dominio de terceros en la CSP.
6. Las respuestas de `/api/` conservan sus propias cabeceras (CSP `default-src 'none'` de E0.1); Nginx no añade cabeceras del panel en esa `location`.

## Alternativas descartadas

- `style-src 'unsafe-inline'`: más simple, pero permite inyección de estilos (exfiltración por selectores CSS) y no hace falta, porque Angular soporta nonce.
- `autoCsp` de Angular (hashes en `<meta>`): cubre scripts, pero la etiqueta `<meta>` no admite `frame-ancestors` y los estilos de componentes siguen necesitando nonce.
- API en otro origen con `connect-src https://api.dominio`: exige CORS con credenciales y cookies `SameSite=None`, lo que debilita la protección CSRF del refresh.
- Google Fonts: añade dos orígenes externos a la CSP y filtra la IP del operador a un tercero.

## Consecuencias

- (+) Un XSS no puede enviar datos a otro host ni cargar scripts externos; `innerHTML` sin política de Trusted Types falla en tiempo de ejecución.
- (+) El refresh por cookie `SameSite=Strict` funciona sin CORS.
- (−) `index.html` no se puede cachear y la CSP depende de `sub_filter` de Nginx; el servidor de pruebas e2e reproduce la sustitución leyendo el mismo archivo de cabeceras.
- (−) Librerías que escriben HTML con `innerHTML` (el tooltip de ECharts en E1.10) necesitarán `renderMode: 'richText'` o una política de Trusted Types propia registrada en la CSP; se decide en esa épica.
- (−) HSTS no se emite desde el contenedor `web` (HTTP en 8080); lo emite el reverse proxy con TLS (`docs/07-seguridad.md` §7).
