import { ChangeDetectionStrategy, Component } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { RouterLink } from '@angular/router';

/** 403 de interfaz: el rol no tiene acceso a la sección solicitada. */
@Component({
  selector: 'app-sin-permiso-page',
  imports: [MatButtonModule, RouterLink],
  templateUrl: './sin-permiso.page.html',
  styleUrl: './sistema.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SinPermisoPage {}
