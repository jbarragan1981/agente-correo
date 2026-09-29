import { HttpErrorResponse } from '@angular/common/http';

import type { Problema } from '../api/generado/models/problema';

/** Tipos de error de docs/04-api.md §12 más los propios del cliente (`red`, `desconocido`). */
export type TipoError =
  | 'validacion'
  | 'no_autenticado'
  | 'sin_permiso'
  | 'no_encontrado'
  | 'metodo_no_permitido'
  | 'conflicto'
  | 'proveedor_rechazo'
  | 'limite_excedido'
  | 'proveedor_no_disponible'
  | 'error_interno'
  | 'no_listo'
  | 'error_http'
  | 'red'
  | 'desconocido';

export interface ErrorCampo {
  campo: string;
  mensaje: string;
}

/** Error uniforme de la aplicación: lo único que ven componentes y stores. */
export interface ErrorApp {
  readonly tipo: TipoError;
  readonly estado: number;
  /** Mensaje en español del catálogo i18n; nunca el cuerpo crudo de la respuesta. */
  readonly mensaje: string;
  /** `detail` del servidor, solo si la respuesta es problem+json válida. */
  readonly detalle: string | null;
  /** UUID de `instance` (urn:uuid:…) o de la cabecera X-Request-ID. */
  readonly idCorrelacion: string | null;
  /** Errores por campo (solo 400 `validacion`). */
  readonly errores: readonly ErrorCampo[];
  /** Estado de cada dependencia (solo 503 `no_listo`). */
  readonly comprobaciones: Readonly<Record<string, string>> | null;
  /** Segundos de `Retry-After` (solo 429). */
  readonly reintentarEnS: number | null;
}

const TIPOS_SERVIDOR: ReadonlySet<string> = new Set<TipoError>([
  'validacion',
  'no_autenticado',
  'sin_permiso',
  'no_encontrado',
  'metodo_no_permitido',
  'conflicto',
  'proveedor_rechazo',
  'limite_excedido',
  'proveedor_no_disponible',
  'error_interno',
  'no_listo',
  'error_http',
]);

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const creados = new WeakSet<object>();

/** Mensaje en español para cada tipo de error (catálogo i18n). */
export function mensajeDeError(tipo: TipoError, reintentarEnS: number | null = null): string {
  switch (tipo) {
    case 'validacion':
      return $localize`:@@error.validacion:Revisa los datos marcados.`;
    case 'no_autenticado':
      return $localize`:@@error.no_autenticado:Tu sesión no es válida o ha caducado. Inicia sesión de nuevo.`;
    case 'sin_permiso':
      return $localize`:@@error.sin_permiso:No tienes permiso para realizar esta acción.`;
    case 'no_encontrado':
      return $localize`:@@error.no_encontrado:El recurso solicitado no existe.`;
    case 'metodo_no_permitido':
      return $localize`:@@error.metodo_no_permitido:La operación no está permitida.`;
    case 'conflicto':
      return $localize`:@@error.conflicto:La operación entra en conflicto con el estado actual. Recarga e inténtalo de nuevo.`;
    case 'proveedor_rechazo':
      return $localize`:@@error.proveedor_rechazo:El proveedor de IA rechazó la solicitud.`;
    case 'limite_excedido':
      return reintentarEnS === null
        ? $localize`:@@error.limite_excedido:Demasiados intentos. Espera un momento e inténtalo de nuevo.`
        : $localize`:@@error.limite_excedido.espera:Demasiados intentos. Inténtalo de nuevo en ${reintentarEnS}:segundos: s.`;
    case 'proveedor_no_disponible':
      return $localize`:@@error.proveedor_no_disponible:El proveedor no está disponible en este momento.`;
    case 'error_interno':
      return $localize`:@@error.error_interno:Se produjo un error interno.`;
    case 'no_listo':
      return $localize`:@@error.no_listo:El sistema todavía no está listo.`;
    case 'error_http':
      return $localize`:@@error.error_http:La solicitud no se pudo completar.`;
    case 'red':
      return $localize`:@@error.red:No se pudo contactar con el servidor.`;
    case 'desconocido':
      return $localize`:@@error.desconocido:Se produjo un error inesperado.`;
  }
}

/** Guarda de tipo: el cuerpo tiene la forma mínima de `Problema` (docs/04-api.md §12). */
export function esProblema(cuerpo: unknown): cuerpo is Problema {
  if (typeof cuerpo !== 'object' || cuerpo === null || Array.isArray(cuerpo)) {
    return false;
  }
  const p = cuerpo as Record<string, unknown>;
  return (
    typeof p['type'] === 'string' &&
    typeof p['title'] === 'string' &&
    typeof p['status'] === 'number' &&
    typeof p['instance'] === 'string'
  );
}

/** ¿El valor es un `ErrorApp` creado por este módulo? */
export function esErrorApp(valor: unknown): valor is ErrorApp {
  return typeof valor === 'object' && valor !== null && creados.has(valor);
}

/** Crea un `ErrorApp` con valores por defecto. */
export function crearErrorApp(
  tipo: TipoError,
  estado: number,
  extras: Partial<ErrorApp> = {},
): ErrorApp {
  const reintentarEnS = extras.reintentarEnS ?? null;
  const error: ErrorApp = Object.freeze({
    tipo,
    estado,
    mensaje: extras.mensaje ?? mensajeDeError(tipo, reintentarEnS),
    detalle: extras.detalle ?? null,
    idCorrelacion: extras.idCorrelacion ?? null,
    errores: Object.freeze([...(extras.errores ?? [])]),
    comprobaciones: extras.comprobaciones ?? null,
    reintentarEnS,
  });
  creados.add(error);
  return error;
}

function uuidDeInstance(instance: string): string | null {
  const valor = instance.startsWith('urn:uuid:') ? instance.slice('urn:uuid:'.length) : '';
  return UUID.test(valor) ? valor.toLowerCase() : null;
}

function uuidValido(valor: string | null): string | null {
  return valor !== null && UUID.test(valor) ? valor.toLowerCase() : null;
}

function leerErrores(valor: unknown): ErrorCampo[] {
  if (!Array.isArray(valor)) {
    return [];
  }
  return valor.flatMap((item: unknown) => {
    if (typeof item !== 'object' || item === null) {
      return [];
    }
    const { campo, mensaje } = item as Record<string, unknown>;
    return typeof campo === 'string' && typeof mensaje === 'string' ? [{ campo, mensaje }] : [];
  });
}

function leerComprobaciones(valor: unknown): Record<string, string> | null {
  if (typeof valor !== 'object' || valor === null || Array.isArray(valor)) {
    return null;
  }
  const entradas = Object.entries(valor as Record<string, unknown>).filter(
    (e): e is [string, string] => typeof e[1] === 'string',
  );
  return Object.freeze(Object.fromEntries(entradas));
}

function leerRetryAfter(valor: string | null): number | null {
  if (valor === null || !/^\d{1,6}$/.test(valor.trim())) {
    return null;
  }
  return Number(valor.trim());
}

function esProblemJson(respuesta: HttpErrorResponse): boolean {
  const tipo = respuesta.headers.get('Content-Type') ?? '';
  return tipo.trim().toLowerCase().startsWith('application/problem+json');
}

function desdeProblema(respuesta: HttpErrorResponse, problema: Problema): ErrorApp {
  const tipo: TipoError = TIPOS_SERVIDOR.has(problema.type)
    ? (problema.type as TipoError)
    : 'error_http';
  const extensiones = problema as Record<string, unknown>;
  return crearErrorApp(tipo, respuesta.status, {
    detalle: typeof problema.detail === 'string' ? problema.detail : null,
    idCorrelacion:
      uuidDeInstance(problema.instance) ?? uuidValido(respuesta.headers.get('X-Request-ID')),
    errores: respuesta.status === 400 ? leerErrores(extensiones['errores']) : [],
    comprobaciones:
      respuesta.status === 503 ? leerComprobaciones(extensiones['comprobaciones']) : null,
    reintentarEnS:
      respuesta.status === 429 ? leerRetryAfter(respuesta.headers.get('Retry-After')) : null,
  });
}

/**
 * Convierte cualquier error en un `ErrorApp` (función pura).
 * Solo interpreta el cuerpo si es `application/problem+json` válido; nunca expone otros cuerpos.
 */
export function aErrorApp(error: unknown): ErrorApp {
  if (esErrorApp(error)) {
    return error;
  }
  if (!(error instanceof HttpErrorResponse)) {
    return crearErrorApp('desconocido', 0);
  }
  if (error.status === 0) {
    return crearErrorApp('red', 0);
  }
  if (esProblemJson(error) && esProblema(error.error)) {
    return desdeProblema(error, error.error);
  }
  return crearErrorApp('desconocido', error.status, {
    idCorrelacion: uuidValido(error.headers.get('X-Request-ID')),
  });
}

/** Recupera el `ErrorApp` del error de un `resource()` (Angular envuelve los valores que no son `Error`). */
export function errorDeRecurso(error: unknown): ErrorApp {
  if (error instanceof Error && error.cause !== undefined) {
    return aErrorApp(error.cause);
  }
  return aErrorApp(error);
}
