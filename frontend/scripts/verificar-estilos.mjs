// Verifica las reglas de estilo y plantillas del panel (CA18, CA20):
//  - ningún color hexadecimal fuera de src/styles/tokens.css y del generado src/styles/_paleta-m3.scss;
//  - sin atributos style= ni enlaces [style] en plantillas;
//  - `!important` solo con el comentario `// override-material:` en la misma línea o la anterior;
//  - sin [innerHTML]/[outerHTML]/[srcdoc] (ni bind-…) en plantillas ni en plantillas en línea.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const raiz = fileURLToPath(new URL('..', import.meta.url));
const src = join(raiz, 'src');
const permitidosHex = new Set(['src/styles/tokens.css', 'src/styles/_paleta-m3.scss']);
const excluidos = ['src/app/core/api/generado/'];
const extensiones = /\.(ts|html|scss|css)$/;

const HEX = /(?<![\w&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![\w-])/g;
const ESTILO_EN_PLANTILLA = /\s(style|\[style(\.[\w-]+)?\]|\[ngStyle\])\s*=/;
// BUG-06: incluye la forma bind-innerHTML, [srcdoc] y las plantillas en línea de los .ts.
const HTML_CRUDO = /(\[|bind-)(attr\.)?(innerHTML|outerHTML|srcdoc)\]?/i;
const MARCA_OVERRIDE = '// override-material:';

function recorrer(dir) {
  return readdirSync(dir).flatMap((nombre) => {
    const ruta = join(dir, nombre);
    return statSync(ruta).isDirectory() ? recorrer(ruta) : [ruta];
  });
}

function rutaRelativa(ruta) {
  return relative(raiz, ruta).split(sep).join('/');
}

/** Devuelve los hallazgos de un archivo como cadenas "ruta:línea: motivo". */
export function revisarArchivo(rutaRel, contenido) {
  const hallazgos = [];
  const lineas = contenido.split('\n');
  const esPlantilla = rutaRel.endsWith('.html');
  const esCodigo = rutaRel.endsWith('.ts') && !rutaRel.endsWith('.spec.ts');
  lineas.forEach((linea, i) => {
    const donde = `${rutaRel}:${i + 1}`;
    if (!permitidosHex.has(rutaRel) && !rutaRel.endsWith('.spec.ts')) {
      const hex = linea.match(HEX);
      if (hex) hallazgos.push(`${donde}: color hexadecimal ${hex.join(', ')} fuera de tokens.css`);
    }
    if (esPlantilla && ESTILO_EN_PLANTILLA.test(linea)) {
      hallazgos.push(`${donde}: estilo en línea en plantilla`);
    }
    if ((esPlantilla || esCodigo) && HTML_CRUDO.test(linea)) {
      hallazgos.push(`${donde}: enlace a innerHTML/outerHTML/srcdoc prohibido`);
    }
    if (/!important/.test(linea)) {
      const anterior = lineas[i - 1] ?? '';
      if (!linea.includes(MARCA_OVERRIDE) && !anterior.includes(MARCA_OVERRIDE)) {
        hallazgos.push(`${donde}: !important sin comentario "${MARCA_OVERRIDE}"`);
      }
    }
  });
  return hallazgos;
}

function main() {
  const archivos = recorrer(src)
    .map((ruta) => ({ ruta, rel: rutaRelativa(ruta) }))
    .filter(({ rel }) => extensiones.test(rel) && !excluidos.some((e) => rel.startsWith(e)));
  const hallazgos = archivos.flatMap(({ ruta, rel }) =>
    revisarArchivo(rel, readFileSync(ruta, 'utf8')),
  );
  if (hallazgos.length > 0) {
    process.stderr.write(
      `verificar-estilos: ${hallazgos.length} hallazgo(s)\n${hallazgos.join('\n')}\n`,
    );
    process.exit(1);
  }
  process.stdout.write(`verificar-estilos: ${archivos.length} archivos sin hallazgos\n`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) main();
