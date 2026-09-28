import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';

import { SILENCIAR_ERRORES } from './contexto-http';
import { aErrorApp } from './error-app';
import { NotificadorErrores } from './notificador-errores';

/**
 * Convierte cada `HttpErrorResponse` en `ErrorApp` y lo notifica, salvo 401 (lo gestiona
 * `authInterceptor`) o peticiones marcadas con `SILENCIAR_ERRORES`.
 */
export const erroresInterceptor: HttpInterceptorFn = (req, next) => {
  const notificador = inject(NotificadorErrores);
  return next(req).pipe(
    catchError((error: unknown) => {
      if (!(error instanceof HttpErrorResponse)) {
        return throwError(() => error);
      }
      const errorApp = aErrorApp(error);
      if (!req.context.get(SILENCIAR_ERRORES) && errorApp.estado !== 401) {
        void notificador.mostrar(errorApp);
      }
      return throwError(() => errorApp);
    }),
  );
};
