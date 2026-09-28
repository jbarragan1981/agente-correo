import { Injectable, inject } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { RouterStateSnapshot, TitleStrategy } from '@angular/router';

export const NOMBRE_APLICACION = $localize`:@@app.nombre:Agente Correo`;

/** Título del documento: "<título de la ruta> · Agente Correo". */
@Injectable({ providedIn: 'root' })
export class TituloStrategy extends TitleStrategy {
  private readonly titulo = inject(Title);

  override updateTitle(snapshot: RouterStateSnapshot): void {
    const deRuta = this.buildTitle(snapshot);
    this.titulo.setTitle(deRuta ? `${deRuta} · ${NOMBRE_APLICACION}` : NOMBRE_APLICACION);
  }
}
