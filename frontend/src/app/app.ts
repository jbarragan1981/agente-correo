import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { TemaService } from './core/layout/tema.service';

/**
 * Raíz del panel: aloja el enrutador; el shell vive en LayoutPrincipal. Instancia `TemaService` aquí para
 * que el tema (preferencia guardada o del sistema) se aplique también en /login (BUG-05).
 */
@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  template: '<router-outlet />',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App {
  private readonly tema = inject(TemaService);

  /** Tema activo, expuesto para las pruebas. */
  readonly temaActivo = this.tema.tema;
}
