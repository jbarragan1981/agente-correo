import { HttpErrorResponse, HttpHeaders } from '@angular/common/http';

import { Rol, SesionOut } from '../app/core/auth/contrato-auth';

/** Token opaco de prueba (nunca un JWT literal). */
export function tokenPrueba(): string {
  return `simulado.${crypto.randomUUID()}`;
}

/** Sesión de prueba con los roles indicados. */
export function crearSesionPrueba(roles: Rol[] = ['operador'], token = tokenPrueba()): SesionOut {
  return {
    access_token: token,
    token_type: 'bearer',
    expires_in: 900,
    usuario: {
      id: crypto.randomUUID(),
      email: 'persona@viamatica.test',
      nombre: 'Persona de Prueba',
      roles,
    },
  };
}

export const ID_PRUEBA = '3f2b8c1e-6d4a-4f7e-9a51-2b0c8d7e6f10';

/** Cuerpo problem+json (docs/04-api.md §12). */
export function cuerpoProblema(
  tipo: string,
  estado: number,
  extras: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    type: tipo,
    title: 'Título',
    status: estado,
    detail: 'Detalle del servidor.',
    instance: `urn:uuid:${ID_PRUEBA}`,
    ...extras,
  };
}

/** `HttpErrorResponse` con cuerpo problem+json. */
export function problema(
  tipo: string,
  estado: number,
  extras: Record<string, unknown> = {},
  cabeceras: Record<string, string> = {},
): HttpErrorResponse {
  return new HttpErrorResponse({
    status: estado,
    url: '/api/v1/prueba',
    headers: new HttpHeaders({ 'Content-Type': 'application/problem+json', ...cabeceras }),
    error: cuerpoProblema(tipo, estado, extras),
  });
}

/** `HttpErrorResponse` con un cuerpo que no es problem+json (p. ej. HTML de un proxy). */
export function respuestaNoProblema(
  estado = 502,
  cuerpo = '<html><body>Bad Gateway nginx</body></html>',
): HttpErrorResponse {
  return new HttpErrorResponse({
    status: estado,
    url: '/api/v1/prueba',
    headers: new HttpHeaders({ 'Content-Type': 'text/html' }),
    error: cuerpo,
  });
}
