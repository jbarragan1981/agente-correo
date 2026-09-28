// Umbral de cobertura por directorio (CA4): el builder de Angular solo admite umbrales globales,
// así que este script lee coverage/panel/coverage-summary.json y exige ≥ 80 % de líneas y ramas
// en src/app/core/** y src/app/shared/** (ya excluidos core/api/generado y core/mocks).
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const UMBRAL = 80;
const DIRECTORIOS = ['src/app/core/', 'src/app/shared/'];
const METRICAS = ['lines', 'branches'];

const ruta = fileURLToPath(new URL('../coverage/panel/coverage-summary.json', import.meta.url));
const resumen = JSON.parse(readFileSync(ruta, 'utf8'));

const errores = [];
for (const directorio of DIRECTORIOS) {
  const archivos = Object.entries(resumen).filter(([archivo]) =>
    archivo.includes(`/${directorio}`),
  );
  for (const metrica of METRICAS) {
    const total = archivos.reduce((s, [, m]) => s + m[metrica].total, 0);
    const cubiertas = archivos.reduce((s, [, m]) => s + m[metrica].covered, 0);
    const porcentaje = total === 0 ? 100 : (cubiertas / total) * 100;
    const linea = `${directorio} ${metrica}: ${porcentaje.toFixed(2)} % (${cubiertas}/${total})`;
    process.stdout.write(`verificar-cobertura: ${linea}\n`);
    if (porcentaje < UMBRAL) errores.push(linea);
  }
}
if (errores.length > 0) {
  process.stderr.write(
    `verificar-cobertura: por debajo del ${UMBRAL} %:\n- ${errores.join('\n- ')}\n`,
  );
  process.exit(1);
}
