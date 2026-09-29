import { HttpInterceptorFn } from '@angular/common/http';

/** Cabecera de correlación con los logs del backend (E0.1). */
export const CABECERA_CORRELACION = 'X-Request-ID';

/** ¿La URL es una ruta relativa de la API del mismo origen? */
export function esRutaApi(url: string): boolean {
  return url.startsWith('/api/');
}

/** Añade `X-Request-ID` (UUID v4 distinto) a cada petición a `/api/`. */
export const correlacionInterceptor: HttpInterceptorFn = (req, next) => {
  if (!esRutaApi(req.url)) {
    return next(req);
  }
  return next(req.clone({ setHeaders: { [CABECERA_CORRELACION]: crypto.randomUUID() } }));
};
