import { ChangeDetectionStrategy, Component } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { RouterLink } from '@angular/router';

/** 404 de interfaz. */
@Component({
  selector: 'app-no-encontrado-page',
  imports: [MatButtonModule, RouterLink],
  templateUrl: './no-encontrado.page.html',
  styleUrl: './sistema.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NoEncontradoPage {}
