import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  input,
  output,
  viewChild,
} from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatSidenav, MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { UsuarioSesion } from '../../../core/auth/contrato-auth';
import { etiquetaRol } from '../../../core/auth/etiquetas-rol';

/** Entrada del menú lateral. */
export interface EntradaMenu {
  readonly ruta: string;
  readonly etiqueta: string;
  readonly icono: string;
}

/**
 * Shell presentacional del panel: topbar, sidebar colapsable (256/72 px) y contenido.
 * No inyecta servicios: el contenedor (LayoutPrincipal) le pasa el estado y escucha los eventos.
 */
@Component({
  selector: 'vm-shell',
  imports: [
    MatButtonModule,
    MatIconModule,
    MatMenuModule,
    MatSidenavModule,
    MatToolbarModule,
    MatTooltipModule,
    RouterLink,
    RouterLinkActive,
  ],
  templateUrl: './vm-shell.html',
  styleUrl: './vm-shell.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'vm-shell' },
})
export class VmShell {
  readonly navegacion = input.required<readonly EntradaMenu[]>();
  readonly usuario = input.required<UsuarioSesion>();
  readonly colapsado = input.required<boolean>();
  readonly movil = input<boolean>(false);
  readonly modoSimulado = input<boolean>(false);
  readonly temaOscuro = input<boolean>(false);

  readonly alternarColapso = output();
  readonly alternarTema = output();
  readonly cerrarSesion = output();

  private readonly sidenav = viewChild.required(MatSidenav);
  private readonly contenido = viewChild.required<ElementRef<HTMLElement>>('contenido');

  /** La sidebar solo se colapsa en escritorio; en móvil se abre completa sobre el contenido. */
  protected readonly colapsadaEfectiva = computed(() => this.colapsado() && !this.movil());
  protected readonly etiquetaExpandir = $localize`:@@shell.expandir_menu:Expandir menú lateral`;
  protected readonly etiquetaContraer = $localize`:@@shell.contraer_menu:Contraer menú lateral`;
  protected readonly rolesVisibles = computed(() =>
    this.usuario().roles.map(etiquetaRol).join(', '),
  );

  protected enfocarContenido(): void {
    this.contenido().nativeElement.focus();
  }

  protected alNavegar(): void {
    if (this.movil()) {
      void this.sidenav().close();
    }
  }

  protected abrirMenu(): void {
    void this.sidenav().toggle();
  }
}
