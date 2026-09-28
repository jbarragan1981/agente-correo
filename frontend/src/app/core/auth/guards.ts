import { inject } from '@angular/core';
import { CanMatchFn, Router, UrlSegment, UrlTree } from '@angular/router';

import { Rol } from './contrato-auth';
import { SesionStore } from './sesion.store';

/**
 * Guards de EXPERIENCIA DE USUARIO: ocultan pantallas que el rol no puede usar. La autorización
 * real la aplica el backend en cada endpoint (E0.3).
 */

function urlSolicitada(router: Router, segmentos: UrlSegment[]): string {
  const navegacion = router.currentNavigation();
  if (navegacion) {
    return router.serializeUrl(navegacion.extractedUrl);
  }
  return `/${segmentos.map((s) => s.path).join('/')}`;
}

/** Sin sesión → `/login?volver=<url>`. Espera a que termine la restauración de la sesión. */
export const autenticadoGuard: CanMatchFn = async (
  _ruta,
  segmentos,
): Promise<boolean | UrlTree> => {
  const sesion = inject(SesionStore);
  const router = inject(Router);
  const volver = urlSolicitada(router, segmentos);
  await sesion.esperarRestauracion();
  return sesion.autenticada()
    ? true
    : router.createUrlTree(['/login'], { queryParams: { volver } });
};

/** Con sesión → `/inicio`. */
export const invitadoGuard: CanMatchFn = async (): Promise<boolean | UrlTree> => {
  const sesion = inject(SesionStore);
  const router = inject(Router);
  await sesion.esperarRestauracion();
  return sesion.autenticada() ? router.createUrlTree(['/inicio']) : true;
};

/** El usuario necesita alguno de los roles; si no, `/sin-permiso`. */
export function rolGuard(...roles: readonly Rol[]): CanMatchFn {
  return () => {
    const sesion = inject(SesionStore);
    return sesion.tieneAlgunRol(...roles) ? true : inject(Router).createUrlTree(['/sin-permiso']);
  };
}
