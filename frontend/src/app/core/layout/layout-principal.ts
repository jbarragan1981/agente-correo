import { BreakpointObserver } from '@angular/cdk/layout';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterOutlet } from '@angular/router';
import { map } from 'rxjs';

import { VmShell } from '../../shared/ui/shell/vm-shell';
import { SesionStore } from '../auth/sesion.store';
import { MODO_SIMULADO } from '../mocks/modo-simulado';
import { seccionesPara } from './navegacion';
import { PreferenciasUi } from './preferencias-ui';
import { TemaService } from './tema.service';

/** Por debajo de este ancho el menú lateral pasa a modo `over` (CA12). */
export const CONSULTA_MOVIL = '(max-width: 1023.98px)';

/** Contenedor del shell: conecta sesión, preferencias, tema y responsive con `vm-shell`. */
@Component({
  selector: 'app-layout-principal',
  imports: [VmShell, RouterOutlet],
  templateUrl: './layout-principal.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LayoutPrincipal {
  protected readonly sesion = inject(SesionStore);
  private readonly preferencias = inject(PreferenciasUi);
  private readonly temaService = inject(TemaService);
  protected readonly modoSimulado = inject(MODO_SIMULADO);

  protected readonly colapsado = signal(this.preferencias.sidebarColapsada());
  protected readonly movil = toSignal(
    inject(BreakpointObserver)
      .observe(CONSULTA_MOVIL)
      .pipe(map((estado) => estado.matches)),
    { initialValue: false },
  );
  protected readonly navegacion = computed(() => seccionesPara(this.sesion.roles()));
  protected readonly temaOscuro = computed(() => this.temaService.tema() === 'oscuro');

  protected alternarColapso(): void {
    const siguiente = !this.colapsado();
    this.colapsado.set(siguiente);
    this.preferencias.guardarSidebarColapsada(siguiente);
  }

  protected alternarTema(): void {
    this.temaService.alternar();
  }

  protected cerrarSesion(): void {
    void this.sesion.cerrar();
  }
}
