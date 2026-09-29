import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

import { seccionPorRuta } from '../../core/layout/navegacion';

/** Marcador de las secciones de negocio que llegan en épicas posteriores. */
@Component({
  selector: 'app-en-construccion-page',
  imports: [MatIconModule],
  templateUrl: './en-construccion.page.html',
  styleUrl: './sistema.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EnConstruccionPage {
  /** Ruta de la sección (dato de la ruta, enlazado con withComponentInputBinding). */
  readonly seccion = input.required<string>();

  protected readonly item = computed(() => seccionPorRuta(this.seccion()));
}
