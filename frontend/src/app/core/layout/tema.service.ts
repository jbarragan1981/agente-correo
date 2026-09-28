import { DOCUMENT, Injectable, effect, inject, signal } from '@angular/core';

import { PreferenciasUi, Tema } from './preferencias-ui';

/** Tema claro/oscuro: preferencia guardada o, si no hay, `prefers-color-scheme`. */
@Injectable({ providedIn: 'root' })
export class TemaService {
  private readonly documento = inject(DOCUMENT);
  private readonly preferencias = inject(PreferenciasUi);
  private readonly _tema = signal<Tema>(this.preferencias.tema() ?? this.temaDelSistema());

  readonly tema = this._tema.asReadonly();

  constructor() {
    effect(() => {
      this.documento.documentElement.dataset['tema'] = this._tema();
    });
  }

  alternar(): void {
    const siguiente: Tema = this._tema() === 'oscuro' ? 'claro' : 'oscuro';
    this._tema.set(siguiente);
    this.preferencias.guardarTema(siguiente);
  }

  private temaDelSistema(): Tema {
    const vista = this.documento.defaultView;
    return vista?.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'oscuro' : 'claro';
  }
}
