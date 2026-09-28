import {
  HttpContext,
  HttpErrorResponse,
  HttpInterceptorFn,
  HttpRequest,
} from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, from, switchMap, throwError } from 'rxjs';

import { REINTENTADA, SIN_TOKEN } from '../errores/contexto-http';
import { esErrorApp } from '../errores/error-app';
import { CABECERA_CORRELACION, esRutaApi } from '../http/correlacion.interceptor';
import { RUTAS_AUTH } from './contrato-auth';
import { SesionStore } from './sesion.store';

const RUTAS_SIN_TOKEN: readonly string[] = [
  RUTAS_AUTH.login,
  RUTAS_AUTH.refresh,
  RUTAS_AUTH.logout,
];

function ruta(url: string): string {
  return url.split(/[?#]/, 1)[0] ?? url;
}

function esRutaAuth(url: string): boolean {
  return ruta(url).startsWith('/api/v1/auth/');
}

/** ¿Se adjunta `Authorization` a esta petición? Solo rutas relativas `/api/` (CA7). */
export function llevaToken(req: HttpRequest<unknown>): boolean {
  return (
    esRutaApi(req.url) && !req.context.get(SIN_TOKEN) && !RUTAS_SIN_TOKEN.includes(ruta(req.url))
  );
}

function esNoAutenticado(error: unknown): boolean {
  return (
    (esErrorApp(error) && error.estado === 401) ||
    (error instanceof HttpErrorResponse && error.status === 401)
  );
}

function conToken(req: HttpRequest<unknown>, token: string | null): HttpRequest<unknown> {
  return token !== null && llevaToken(req)
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;
}

function comoReintento(req: HttpRequest<unknown>): HttpRequest<unknown> {
  const contexto = new HttpContext();
  for (const clave of req.context.keys()) {
    contexto.set(clave, req.context.get(clave));
  }
  contexto.set(REINTENTADA, true);
  const cabeceras: Record<string, string> = req.headers.has(CABECERA_CORRELACION)
    ? { [CABECERA_CORRELACION]: crypto.randomUUID() }
    : {};
  return req.clone({ context: contexto, setHeaders: cabeceras });
}

/**
 * Adjunta el access token y gestiona el 401: un refresh compartido y un único reintento.
 * Si el refresh falla o el reintento vuelve a dar 401, cierra la sesión local y navega a
 * `/login?volver=<ruta actual>`.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const sesion = inject(SesionStore);
  const router = inject(Router);

  const cerrarLocal = (): void => {
    const actual = router.url;
    sesion.limpiarLocal();
    if (!actual.startsWith('/login')) {
      void router.navigate(['/login'], { queryParams: { volver: actual } });
    }
  };

  const reintentable = llevaToken(req) && !esRutaAuth(req.url) && !req.context.get(REINTENTADA);

  return next(conToken(req, sesion.tokenActual())).pipe(
    catchError((error: unknown) => {
      if (!esNoAutenticado(error) || !llevaToken(req) || esRutaAuth(req.url)) {
        return throwError(() => error);
      }
      if (!reintentable) {
        cerrarLocal();
        return throwError(() => error);
      }
      return from(sesion.refrescar()).pipe(
        catchError(() => {
          cerrarLocal();
          return throwError(() => error);
        }),
        switchMap((token) =>
          next(conToken(comoReintento(req), token)).pipe(
            catchError((errorReintento: unknown) => {
              if (esNoAutenticado(errorReintento)) {
                cerrarLocal();
              }
              return throwError(() => errorReintento);
            }),
          ),
        ),
      );
    }),
  );
};
