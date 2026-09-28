import {
  HttpHeaders,
  HttpInterceptorFn,
  HttpRequest,
  HttpResponse,
  HttpErrorResponse,
} from '@angular/common/http';
import { Observable, delay, dematerialize, materialize, of, throwError } from 'rxjs';

import { LoginIn, RUTAS_AUTH, SesionOut, UsuarioSesion } from '../auth/contrato-auth';
import { CONTRASENA_SIMULADA, USUARIOS_SIMULADOS } from './usuarios-simulados';

/**
 * API simulada de autenticación (ADR-0013). Solo se incluye en los builds `mocks` y `e2e` por
 * `fileReplacements`; `production` y `development` no la empaquetan (CA15).
 * Atiende POST login/refresh/logout y GET me; el resto pasa al backend real.
 */
export const MARCA_SIMULADA = 'X-Api-Simulada';
export const LATENCIA_SIMULADA_MS = 300;
export const MAX_FALLOS_SEGUIDOS = 5;
export const RETRY_AFTER_S = 60;

interface EstadoSimulado {
  fallosSeguidos: number;
  tokens: Map<string, UsuarioSesion>;
}

const estado: EstadoSimulado = { fallosSeguidos: 0, tokens: new Map() };

/** Reinicia el estado (solo pruebas). */
export function reiniciarApiSimulada(): void {
  estado.fallosSeguidos = 0;
  estado.tokens.clear();
}

function cabeceras(extra: Record<string, string> = {}): HttpHeaders {
  return new HttpHeaders({ [MARCA_SIMULADA]: '1', ...extra });
}

function problema(
  req: HttpRequest<unknown>,
  status: number,
  tipo: string,
  titulo: string,
  detalle: string,
  extra: Record<string, string> = {},
): Observable<never> {
  const id = req.headers.get('X-Request-ID') ?? crypto.randomUUID();
  const error = new HttpErrorResponse({
    status,
    url: req.url,
    headers: cabeceras({ 'Content-Type': 'application/problem+json', ...extra }),
    error: { type: tipo, title: titulo, status, detail: detalle, instance: `urn:uuid:${id}` },
  });
  return throwError(() => error);
}

function ok<T>(req: HttpRequest<unknown>, cuerpo: T, status = 200): Observable<HttpResponse<T>> {
  return of(new HttpResponse<T>({ status, url: req.url, body: cuerpo, headers: cabeceras() }));
}

function sesionPara(usuario: UsuarioSesion): SesionOut {
  const token = `simulado.${crypto.randomUUID()}`;
  estado.tokens.set(token, usuario);
  return { access_token: token, token_type: 'bearer', expires_in: 900, usuario };
}

function login(req: HttpRequest<unknown>): Observable<HttpResponse<unknown>> {
  if (estado.fallosSeguidos >= MAX_FALLOS_SEGUIDOS) {
    return problema(req, 429, 'limite_excedido', 'Demasiadas peticiones', 'Demasiados intentos.', {
      'Retry-After': String(RETRY_AFTER_S),
    });
  }
  const cuerpo = (req.body ?? {}) as Partial<LoginIn>;
  const usuario = USUARIOS_SIMULADOS.find((u) => u.email === cuerpo.email?.trim().toLowerCase());
  if (!usuario || cuerpo.password !== CONTRASENA_SIMULADA) {
    estado.fallosSeguidos++;
    return problema(req, 401, 'no_autenticado', 'No autenticado', 'Credenciales no válidas.');
  }
  estado.fallosSeguidos = 0;
  return ok(req, sesionPara(usuario));
}

function yo(req: HttpRequest<unknown>): Observable<HttpResponse<unknown>> {
  const token = (req.headers.get('Authorization') ?? '').replace(/^Bearer /, '');
  const usuario = estado.tokens.get(token);
  return usuario
    ? ok(req, usuario)
    : problema(req, 401, 'no_autenticado', 'No autenticado', 'Sesión no válida.');
}

function responder(req: HttpRequest<unknown>): Observable<HttpResponse<unknown>> | null {
  const ruta = req.url.split('?', 1)[0];
  if (req.method === 'POST' && ruta === RUTAS_AUTH.login) return login(req);
  // Sin cookie real de refresh: recargar la página devuelve a /login (CA6).
  if (req.method === 'POST' && ruta === RUTAS_AUTH.refresh) {
    return problema(req, 401, 'no_autenticado', 'No autenticado', 'No hay sesión que renovar.');
  }
  if (req.method === 'POST' && ruta === RUTAS_AUTH.logout) return ok(req, null, 204);
  if (req.method === 'GET' && ruta === RUTAS_AUTH.yo) return yo(req);
  return null;
}

export const apiSimuladaInterceptor: HttpInterceptorFn = (req, next) => {
  const respuesta = responder(req);
  if (respuesta === null) {
    return next(req);
  }
  // materialize/dematerialize: la latencia se aplica también a los errores.
  return respuesta.pipe(materialize(), delay(LATENCIA_SIMULADA_MS), dematerialize());
};
