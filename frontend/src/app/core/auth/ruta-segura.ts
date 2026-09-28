import { DefaultUrlSerializer } from '@angular/router';

/** Ruta a la que se vuelve cuando `volver` no es una ruta interna segura. */
export const RUTA_POR_DEFECTO = '/inicio';

const ESQUEMA = /^[a-z][a-z0-9+.-]*:/i;
const serializador = new DefaultUrlSerializer();

function decodificar(valor: string): string | null {
  try {
    return decodeURIComponent(valor);
  } catch {
    return null;
  }
}

function tieneControl(valor: string): boolean {
  return [...valor].some((c) => {
    const codigo = c.charCodeAt(0);
    return codigo < 0x20 || codigo === 0x7f;
  });
}

function formaSegura(valor: string): boolean {
  return (
    valor.startsWith('/') &&
    !valor.startsWith('//') &&
    !valor.includes('\\') &&
    !tieneControl(valor) &&
    !ESQUEMA.test(valor.replace(/^\/+/, ''))
  );
}

/**
 * Devuelve `valor` solo si es una ruta interna del panel (evita redirecciones abiertas, CA10):
 * empieza por `/`, no por `//` ni `/\`, sin `\`, esquemas ni caracteres de control tras
 * decodificar (hasta tres niveles), y el enrutador puede interpretarla. En otro caso, `/inicio`.
 */
export function rutaInternaSegura(valor: string | null | undefined): string {
  if (typeof valor !== 'string' || valor.length === 0 || valor.length > 2048) {
    return RUTA_POR_DEFECTO;
  }
  let actual: string | null = valor;
  for (let nivel = 0; nivel < 3 && actual !== null; nivel++) {
    if (!formaSegura(actual)) {
      return RUTA_POR_DEFECTO;
    }
    const siguiente = decodificar(actual);
    if (siguiente === actual) {
      break;
    }
    actual = siguiente;
  }
  if (actual === null || !formaSegura(actual)) {
    return RUTA_POR_DEFECTO;
  }
  try {
    serializador.parse(valor);
  } catch {
    return RUTA_POR_DEFECTO;
  }
  return valor;
}
