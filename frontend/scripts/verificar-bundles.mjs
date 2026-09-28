#!/usr/bin/env node
/**
 * CA15 (plan E0.4): la API simulada solo existe en los builds `e2e` y `mocks`.
 * Compila `production` y `development` (y `e2e` como control positivo) en un directorio temporal y busca
 * los marcadores de la API simulada en todos los archivos generados.
 */
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readdirSync, readFileSync, rmSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const MARCADORES = [
  'X-Api-Simulada',
  'prueba-panel-local',
  '@viamatica.test',
  'apiSimuladaInterceptor',
  'api-simulada.interceptor',
  'usuarios-simulados',
];
const CONFIGURACIONES = [
  { nombre: 'production', debeContener: false },
  { nombre: 'development', debeContener: false },
  { nombre: 'e2e', debeContener: true },
];

function archivos(dir) {
  return readdirSync(dir).flatMap((n) => {
    const ruta = join(dir, n);
    return statSync(ruta).isDirectory() ? archivos(ruta) : [ruta];
  });
}

const temporal = mkdtempSync(join(tmpdir(), 'bundles-'));
let fallos = 0;
try {
  for (const { nombre, debeContener } of CONFIGURACIONES) {
    const salida = join(temporal, nombre);
    execFileSync('npx', ['ng', 'build', '--configuration', nombre, '--output-path', salida], {
      stdio: 'ignore',
    });
    const encontrados = new Set();
    for (const archivo of archivos(salida).filter((a) => /\.(js|mjs|html|css|map)$/.test(a))) {
      const texto = readFileSync(archivo, 'utf8');
      MARCADORES.filter((m) => texto.includes(m)).forEach((m) => encontrados.add(m));
    }
    const correcto = debeContener ? encontrados.has('X-Api-Simulada') : encontrados.size === 0;
    console.log(
      `verificar-bundles: ${nombre} -> ${[...encontrados].join(', ') || 'sin marcadores'} ${correcto ? 'OK' : 'FALLA'}`,
    );
    if (!correcto) fallos++;
  }
} finally {
  rmSync(temporal, { recursive: true, force: true });
}
process.exit(fallos === 0 ? 0 : 1);
