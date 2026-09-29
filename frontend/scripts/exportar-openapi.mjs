// Exporta el esquema OpenAPI del backend a openapi/openapi.json (ADR-0013).
// Por defecto ejecuta la fábrica del backend con uv (sin servidor, sin BD, sin leer .env):
//   node scripts/exportar-openapi.mjs
// Alternativa: descargarlo de un backend local en marcha:
//   node scripts/exportar-openapi.mjs --desde-url http://localhost:8000/api/v1/openapi.json
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const raiz = fileURLToPath(new URL('..', import.meta.url));
const destino = join(raiz, 'openapi', 'openapi.json');
const backend = join(raiz, '..', 'backend');

const CODIGO_PYTHON = [
  'import json, sys',
  'from app.core.config import Settings',
  'from app.main import crear_app',
  'esquema = crear_app(Settings(_env_file=None, env="test")).openapi()',
  'open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(esquema, ensure_ascii=False, indent=2, sort_keys=True) + "\\n")',
].join('\n');

/** Ordena recursivamente las claves de un objeto JSON (mismo formato que sort_keys=True). */
function ordenar(valor) {
  if (Array.isArray(valor)) return valor.map(ordenar);
  if (valor && typeof valor === 'object') {
    return Object.fromEntries(
      Object.keys(valor)
        .sort()
        .map((clave) => [clave, ordenar(valor[clave])]),
    );
  }
  return valor;
}

async function desdeUrl(url) {
  const { hostname } = new URL(url);
  if (!['localhost', '127.0.0.1', '::1'].includes(hostname)) {
    throw new Error(`Solo se admite un backend local (recibido: ${hostname}).`);
  }
  const respuesta = await fetch(url);
  if (!respuesta.ok) throw new Error(`GET ${url} → ${respuesta.status}`);
  const esquema = ordenar(await respuesta.json());
  writeFileSync(destino, `${JSON.stringify(esquema, null, 2)}\n`, 'utf8');
}

function desdeFabrica() {
  execFileSync(
    'uv',
    ['run', '--directory', backend, '--frozen', 'python', '-c', CODIGO_PYTHON, destino],
    {
      stdio: ['ignore', 'inherit', 'inherit'],
      env: { ...process.env, ENV: 'test' },
    },
  );
}

mkdirSync(dirname(destino), { recursive: true });
const indice = process.argv.indexOf('--desde-url');
if (indice >= 0) {
  const url = process.argv[indice + 1];
  if (!url) throw new Error('Falta la URL tras --desde-url.');
  await desdeUrl(url);
} else {
  desdeFabrica();
}
process.stdout.write(`OpenAPI exportado en ${destino}\n`);
