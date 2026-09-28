// Verifica la CSP del panel (CA16, ADR-0012):
//  - infra/nginx-cabeceras-panel.conf contiene exactamente la política de ADR-0012, sin orígenes externos;
//  - infra/nginx.conf incluye las cabeceras en las location del panel (no en /api/) y sustituye el nonce;
//  - src/index.html declara ngCspNonce="__CSP_NONCE__" y lang="es";
//  - angular.json desactiva el CSS crítico en línea en production y e2e.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const leer = (ruta) => readFileSync(fileURLToPath(new URL(ruta, import.meta.url)), 'utf8');

export const POLITICA_ESPERADA =
  "default-src 'self'; script-src 'self'; style-src 'self' 'nonce-$request_id'; font-src 'self'; " +
  "img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; worker-src 'self'; " +
  "manifest-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; " +
  "require-trusted-types-for 'script'; trusted-types angular angular#bundler";

const PROHIBIDOS = ['https:', 'http:', 'wss:', 'ws:', "'unsafe-inline'", "'unsafe-eval'", '*'];

/** Extrae las cabeceras `add_header Nombre "valor"` de un archivo de Nginx. */
export function leerCabeceras(conf) {
  const cabeceras = new Map();
  for (const m of conf.matchAll(/^\s*add_header\s+([\w-]+)\s+"([^"]*)"\s+always;/gm)) {
    cabeceras.set(m[1], m[2]);
  }
  return cabeceras;
}

/** Devuelve los errores de la política respecto a ADR-0012. */
export function revisarPolitica(politica) {
  const errores = [];
  if (politica !== POLITICA_ESPERADA) errores.push('la CSP no coincide exactamente con ADR-0012');
  const tokens = (politica ?? '').split(/[\s;]+/).filter(Boolean);
  for (const prohibido of PROHIBIDOS) {
    if (tokens.some((t) => t === prohibido || (prohibido !== '*' && t.startsWith(prohibido)))) {
      errores.push(`la CSP contiene ${prohibido}`);
    }
  }
  const connect = /connect-src ([^;]*)/.exec(politica ?? '');
  if (connect?.[1]?.trim() !== "'self'") errores.push("connect-src debe ser exactamente 'self'");
  return errores;
}

function bloqueLocation(conf, patron) {
  const inicio = conf.indexOf(`location ${patron}`);
  if (inicio < 0) return null;
  const fin = conf.indexOf('\n    }', inicio);
  return conf.slice(inicio, fin);
}

function revisarNginx(conf) {
  const errores = [];
  const api = bloqueLocation(conf, '/api/ {');
  const recursos = bloqueLocation(conf, '~*');
  const spa = bloqueLocation(conf, '/ {');
  if (!api || !recursos || !spa) return ['nginx.conf debe tener location /api/, de recursos y /'];
  if (api.includes('cabeceras-panel.conf'))
    errores.push('/api/ no debe incluir las cabeceras del panel');
  if (/add_header/.test(conf.split('location')[0] ?? '')) {
    errores.push(
      'nginx.conf no debe declarar add_header a nivel server (se perderían en las location)',
    );
  }
  for (const [nombre, bloque] of [
    ['recursos', recursos],
    ['/', spa],
  ]) {
    if (!bloque.includes('include /etc/nginx/cabeceras-panel.conf;')) {
      errores.push(`la location ${nombre} debe incluir cabeceras-panel.conf`);
    }
  }
  if (!spa.includes("sub_filter '__CSP_NONCE__' $request_id;"))
    errores.push('falta sub_filter del nonce');
  if (!spa.includes('Cache-Control "no-store"'))
    errores.push('index.html debe servirse con no-store');
  return errores;
}

function revisarAngular(angularJson, indexHtml) {
  const errores = [];
  if (!indexHtml.includes('<app-root ngCspNonce="__CSP_NONCE__">')) {
    errores.push('src/index.html debe declarar <app-root ngCspNonce="__CSP_NONCE__">');
  }
  if (!/<html lang="es">/.test(indexHtml)) errores.push('src/index.html debe declarar lang="es"');
  const configuraciones = JSON.parse(angularJson).projects.panel.architect.build.configurations;
  for (const nombre of ['production', 'e2e']) {
    if (configuraciones[nombre]?.optimization?.styles?.inlineCritical !== false) {
      errores.push(`angular.json: ${nombre} debe tener optimization.styles.inlineCritical = false`);
    }
  }
  return errores;
}

function main() {
  const cabeceras = leerCabeceras(leer('../../infra/nginx-cabeceras-panel.conf'));
  const errores = [
    ...revisarPolitica(cabeceras.get('Content-Security-Policy')),
    ...revisarNginx(leer('../../infra/nginx.conf')),
    ...revisarAngular(leer('../angular.json'), leer('../src/index.html')),
  ];
  for (const requerida of [
    'X-Content-Type-Options',
    'Referrer-Policy',
    'X-Frame-Options',
    'Permissions-Policy',
  ]) {
    if (!cabeceras.has(requerida)) errores.push(`falta la cabecera ${requerida}`);
  }
  if (errores.length > 0) {
    process.stderr.write(`verificar-csp: ${errores.length} error(es)\n- ${errores.join('\n- ')}\n`);
    process.exit(1);
  }
  process.stdout.write('verificar-csp: política de ADR-0012 correcta\n');
}

if (process.argv[1] === fileURLToPath(import.meta.url)) main();
