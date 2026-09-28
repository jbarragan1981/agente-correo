import { HttpClient, HttpContext } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom, timeout } from 'rxjs';

import { SILENCIAR_ERRORES, SIN_TOKEN } from '../errores/contexto-http';
import { LoginIn, RUTAS_AUTH, SesionOut, UsuarioSesion } from './contrato-auth';

/** Tiempo máximo de espera de un refresh (evita bloquear el arranque). */
export const LIMITE_REFRESH_MS = 5000;

/** Cliente HTTP de los endpoints de autenticación (contrato provisional de E0.3). */
@Injectable({ providedIn: 'root' })
export class AuthApi {
  private readonly http = inject(HttpClient);

  /** Login: sin token y sin notificación global (la página muestra el error en línea). */
  login(credenciales: LoginIn): Promise<SesionOut> {
    const contexto = new HttpContext().set(SIN_TOKEN, true).set(SILENCIAR_ERRORES, true);
    return firstValueFrom(
      this.http.post<SesionOut>(RUTAS_AUTH.login, credenciales, { context: contexto }),
    );
  }

  refrescar(): Promise<SesionOut> {
    const contexto = new HttpContext().set(SIN_TOKEN, true).set(SILENCIAR_ERRORES, true);
    return firstValueFrom(
      this.http
        .post<SesionOut>(RUTAS_AUTH.refresh, null, { context: contexto })
        .pipe(timeout(LIMITE_REFRESH_MS)),
    );
  }

  cerrarSesion(): Promise<void> {
    const contexto = new HttpContext().set(SIN_TOKEN, true).set(SILENCIAR_ERRORES, true);
    return firstValueFrom(this.http.post<void>(RUTAS_AUTH.logout, null, { context: contexto }));
  }

  yo(): Promise<UsuarioSesion> {
    return firstValueFrom(this.http.get<UsuarioSesion>(RUTAS_AUTH.yo));
  }
}
