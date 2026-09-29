import { HttpContext } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, resource } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';

import { Api } from '../../core/api/generado/api';
import { listoApiV1SaludListoGet } from '../../core/api/generado/fn/salud/listo-api-v-1-salud-listo-get';
import { SesionStore } from '../../core/auth/sesion.store';
import { SILENCIAR_ERRORES } from '../../core/errores/contexto-http';
import { errorDeRecurso } from '../../core/errores/error-app';
import { seccionesPara } from '../../core/layout/navegacion';

/** Fila de la lista de comprobaciones de salud. */
export interface FilaComprobacion {
  readonly nombre: string;
  readonly ok: boolean;
}

/** Nombre visible de una comprobación de `/salud/listo`. */
export function etiquetaComprobacion(nombre: string): string {
  switch (nombre) {
    case 'base_datos':
      return $localize`:@@salud.base_datos:Base de datos`;
    case 'migraciones':
      return $localize`:@@salud.migraciones:Migraciones`;
    case 'proveedores':
      return $localize`:@@salud.proveedores:Proveedores de IA`;
    default:
      return nombre.replaceAll('_', ' ');
  }
}

function filas(
  comprobaciones: Readonly<Record<string, string>> | null | undefined,
): FilaComprobacion[] {
  return Object.entries(comprobaciones ?? {}).map(([nombre, estado]) => ({
    nombre: etiquetaComprobacion(nombre),
    ok: estado === 'ok',
  }));
}

/** Pantalla de inicio: saludo, estado del sistema (`/salud/listo`) y accesos por rol. */
@Component({
  selector: 'app-inicio-page',
  imports: [MatButtonModule, MatCardModule, MatIconModule, MatProgressBarModule, RouterLink],
  templateUrl: './inicio.page.html',
  styleUrl: './inicio.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InicioPage {
  private readonly api = inject(Api);
  protected readonly sesion = inject(SesionStore);

  protected readonly salud = resource({
    loader: () =>
      this.api.invoke(
        listoApiV1SaludListoGet,
        undefined,
        new HttpContext().set(SILENCIAR_ERRORES, true),
      ),
  });

  protected readonly error = computed(() => {
    const error = this.salud.error();
    return error === undefined ? null : errorDeRecurso(error);
  });
  protected readonly comprobacionesListo = computed(() =>
    filas(this.salud.value()?.comprobaciones),
  );
  protected readonly comprobacionesFallidas = computed(() => filas(this.error()?.comprobaciones));
  protected readonly accesos = computed(() =>
    seccionesPara(this.sesion.roles()).filter((s) => s.ruta !== 'inicio'),
  );

  protected reintentar(): void {
    this.salud.reload();
  }
}
