import { computed, inject } from '@angular/core';
import { Router } from '@angular/router';
import { patchState, signalStore, withComputed, withMethods, withState } from '@ngrx/signals';

import { aErrorApp } from '../errores/error-app';
import { AuthApi } from './auth-api';
import { LoginIn, Rol, SesionOut, UsuarioSesion } from './contrato-auth';

export type EstadoSesion = 'anonima' | 'restaurando' | 'autenticada';

/**
 * Estado de la sesión. El access token vive SOLO aquí, en memoria (CA6): nunca en
 * Storage, cookies accesibles, URL ni consola. Los miembros con `_` son privados del store.
 */
interface EstadoSesionStore {
  estado: EstadoSesion;
  usuario: UsuarioSesion | null;
  _token: string | null;
  _expiraEn: number | null;
}

const INICIAL: EstadoSesionStore = {
  estado: 'anonima',
  usuario: null,
  _token: null,
  _expiraEn: null,
};

export const SesionStore = signalStore(
  { providedIn: 'root' },
  withState<EstadoSesionStore>(INICIAL),
  withComputed(({ estado, usuario }) => ({
    autenticada: computed(() => estado() === 'autenticada'),
    roles: computed<readonly Rol[]>(() => usuario()?.roles ?? []),
    nombreVisible: computed(() => usuario()?.nombre ?? ''),
  })),
  withMethods((store) => {
    const api = inject(AuthApi);
    const router = inject(Router);
    let refreshEnCurso: Promise<string> | null = null;
    let restauracionEnCurso: Promise<void> | null = null;

    const aplicar = (sesion: SesionOut): void => {
      patchState(store, {
        estado: 'autenticada',
        usuario: sesion.usuario,
        _token: sesion.access_token,
        _expiraEn: Date.now() + sesion.expires_in * 1000,
      });
    };

    const limpiarLocal = (): void => {
      patchState(store, INICIAL);
    };

    return {
      /** Token para `authInterceptor`; no se expone a plantillas. */
      tokenActual(): string | null {
        return store._token();
      },

      /** Inicia sesión; lanza `ErrorApp`. La contraseña no se guarda. */
      async iniciar(credenciales: LoginIn): Promise<void> {
        try {
          aplicar(await api.login(credenciales));
        } catch (error) {
          throw aErrorApp(error);
        }
      },

      /** Al arrancar: refresh silencioso (con límite de tiempo) → autenticada | anonima. */
      restaurar(): Promise<void> {
        patchState(store, { estado: 'restaurando' });
        restauracionEnCurso = api
          .refrescar()
          .then(aplicar, limpiarLocal)
          .finally(() => {
            restauracionEnCurso = null;
          });
        return restauracionEnCurso;
      },

      /** Resuelve cuando termina la restauración en curso (inmediato si no hay ninguna). */
      esperarRestauracion(): Promise<void> {
        return restauracionEnCurso ?? Promise.resolve();
      },

      /** Refresh reactivo single-flight: una sola llamada compartida por todas las peticiones. */
      refrescar(): Promise<string> {
        refreshEnCurso ??= api
          .refrescar()
          .then((sesion) => {
            aplicar(sesion);
            return sesion.access_token;
          })
          .finally(() => {
            refreshEnCurso = null;
          });
        return refreshEnCurso;
      },

      /** Cierra la sesión en el servidor (errores ignorados), limpia y navega a /login. */
      async cerrar(): Promise<void> {
        try {
          await api.cerrarSesion();
        } catch {
          // El cierre local se hace igualmente: la cookie caduca sola en el servidor.
        }
        limpiarLocal();
        await router.navigate(['/login']);
      },

      /** Limpia la sesión sin red (401 persistente). */
      limpiarLocal,

      tieneAlgunRol(...roles: Rol[]): boolean {
        const propios = store.usuario()?.roles ?? [];
        return roles.some((rol) => propios.includes(rol));
      },
    };
  }),
);

export type SesionStore = InstanceType<typeof SesionStore>;
