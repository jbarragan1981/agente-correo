import { Injectable, Injector, inject } from '@angular/core';

import { ErrorApp } from './error-app';

/**
 * Muestra errores al usuario con un snackbar; los 5xx incluyen el código de referencia.
 * `MatSnackBar` se carga bajo demanda para no inflar el bundle inicial (CA5).
 */
@Injectable({ providedIn: 'root' })
export class NotificadorErrores {
  private readonly injector = inject(Injector);

  async mostrar(error: ErrorApp): Promise<void> {
    const { MatSnackBar } = await import('@angular/material/snack-bar');
    this.injector
      .get(MatSnackBar)
      .open(this.texto(error), $localize`:@@notificador.cerrar:Cerrar`, {
        duration: 8000,
        politeness: 'assertive',
      });
  }

  /** Texto visible: mensaje del catálogo y, en 5xx, el identificador de correlación. */
  texto(error: ErrorApp): string {
    if (error.estado >= 500 && error.idCorrelacion !== null) {
      return $localize`:@@notificador.con_referencia:${error.mensaje}:mensaje: Código de referencia: ${error.idCorrelacion}:referencia:`;
    }
    return error.mensaje;
  }
}
