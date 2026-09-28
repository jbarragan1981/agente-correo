// Servidor del panel para e2e: reproduce infra/nginx.conf (ADR-0012) sin Docker.
//  - Lee las cabeceras de infra/nginx-cabeceras-panel.conf y sustituye $request_id por un nonce
//    aleatorio por petición, igual que Nginx con sub_filter sobre __CSP_NONCE__ en index.html.
//  - index.html y rutas SPA con Cache-Control: no-store; recursos con hash inmutables.
//  - /api/ sin cabeceras del panel: proxy a API_DESTINO si está definida; si no, 502 problem+json.
// Uso: DIST=dist/e2e/browser PUERTO=4300 [API_DESTINO=http://127.0.0.1:8000] node e2e/servidor-panel.mjs
import { randomBytes, randomUUID } from 'node:crypto';
import { readFileSync, statSync } from 'node:fs';
import { createServer, request as peticionHttp } from 'node:http';
import { extname, join, normalize, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

import { leerCabeceras } from '../scripts/verificar-csp.mjs';

const raiz = fileURLToPath(new URL('..', import.meta.url));
const dist = resolve(raiz, process.env.DIST ?? 'dist/panel/browser');
const puerto = Number(process.env.PUERTO ?? 4300);
const apiDestino = process.env.API_DESTINO ? new URL(process.env.API_DESTINO) : null;
const cabecerasPanel = leerCabeceras(
  readFileSync(join(raiz, '..', 'infra', 'nginx-cabeceras-panel.conf'), 'utf8'),
);
const indice = readFileSync(join(dist, 'index.html'), 'utf8');

const TIPOS = {
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.woff2': 'font/woff2',
  '.woff': 'font/woff',
  '.ico': 'image/x-icon',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.webp': 'image/webp',
  '.html': 'text/html; charset=utf-8',
};
const RECURSO = /\.(?:js|css|woff2?|ico|svg|png|webp)$/i;

function aplicarCabecerasPanel(respuesta, nonce) {
  for (const [nombre, valor] of cabecerasPanel) {
    respuesta.setHeader(nombre, valor.replaceAll('$request_id', nonce));
  }
}

function archivoSeguro(rutaUrl) {
  const relativa = normalize(decodeURIComponent(rutaUrl)).replace(/^([/\\])+/, '');
  const absoluta = resolve(dist, relativa);
  if (absoluta !== dist && !absoluta.startsWith(dist + sep)) return null;
  try {
    return statSync(absoluta).isFile() ? absoluta : null;
  } catch {
    return null;
  }
}

function servirApi(req, res) {
  if (!apiDestino) {
    res.writeHead(502, { 'Content-Type': 'application/problem+json' });
    res.end(
      JSON.stringify({
        type: 'proveedor_no_disponible',
        title: 'Backend no disponible',
        status: 502,
        detail: 'El servidor e2e no tiene API_DESTINO.',
        instance: `urn:uuid:${randomUUID()}`,
      }),
    );
    return;
  }
  const destino = peticionHttp(
    {
      hostname: apiDestino.hostname,
      port: apiDestino.port,
      path: req.url,
      method: req.method,
      headers: { ...req.headers, host: apiDestino.host },
    },
    (respuesta) => {
      res.writeHead(respuesta.statusCode ?? 502, respuesta.headers);
      respuesta.pipe(res);
    },
  );
  destino.on('error', () => {
    res.writeHead(502, { 'Content-Type': 'application/problem+json' });
    res.end(
      JSON.stringify({
        type: 'proveedor_no_disponible',
        title: 'Bad Gateway',
        status: 502,
        instance: `urn:uuid:${randomUUID()}`,
      }),
    );
  });
  req.pipe(destino);
}

const servidor = createServer((req, res) => {
  const ruta = (req.url ?? '/').split('?', 1)[0] ?? '/';
  if (ruta.startsWith('/api/')) {
    servirApi(req, res);
    return;
  }
  const nonce = randomBytes(16).toString('hex');
  aplicarCabecerasPanel(res, nonce);
  if (RECURSO.test(ruta)) {
    const archivo = archivoSeguro(ruta);
    if (!archivo) {
      res.writeHead(404);
      res.end();
      return;
    }
    res.writeHead(200, {
      'Content-Type': TIPOS[extname(archivo).toLowerCase()] ?? 'application/octet-stream',
      'Cache-Control': 'public, max-age=31536000, immutable',
    });
    res.end(readFileSync(archivo));
    return;
  }
  res.writeHead(200, { 'Content-Type': TIPOS['.html'], 'Cache-Control': 'no-store' });
  res.end(indice.replaceAll('__CSP_NONCE__', nonce));
});

servidor.listen(puerto, '127.0.0.1', () => {
  process.stdout.write(
    `servidor-panel: http://127.0.0.1:${puerto} (dist: ${dist}; api: ${apiDestino ?? 'sin destino'})\n`,
  );
});
