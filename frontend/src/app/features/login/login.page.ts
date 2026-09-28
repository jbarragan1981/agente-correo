import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { Router } from '@angular/router';

import { LoginIn } from '../../core/auth/contrato-auth';
import { rutaInternaSegura } from '../../core/auth/ruta-segura';
import { SesionStore } from '../../core/auth/sesion.store';
import { ErrorApp, aErrorApp } from '../../core/errores/error-app';
import { MODO_SIMULADO } from '../../core/mocks/modo-simulado';
import {
  FormField,
  correo,
  form,
  primerError,
  requerido,
  submit,
} from '../../shared/forms/validadores';

/** Mensaje del error general del login; nunca distingue si falló el correo o la contraseña. */
export function mensajeLogin(error: ErrorApp): string {
  switch (error.tipo) {
    case 'no_autenticado':
      return $localize`:@@login.error_credenciales:Correo o contraseña incorrectos.`;
    case 'limite_excedido':
      return error.reintentarEnS === null
        ? $localize`:@@login.error_limite:Demasiados intentos. Espera un momento e inténtalo de nuevo.`
        : $localize`:@@login.error_limite_espera:Demasiados intentos. Inténtalo de nuevo en ${error.reintentarEnS}:segundos: s.`;
    case 'red':
      return $localize`:@@login.error_red:No se pudo contactar con el servidor.`;
    default:
      return error.mensaje;
  }
}

/** Pantalla de inicio de sesión (CA11). */
@Component({
  selector: 'app-login-page',
  imports: [
    FormField,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressBarModule,
  ],
  templateUrl: './login.page.html',
  styleUrl: './login.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoginPage {
  private readonly sesion = inject(SesionStore);
  private readonly router = inject(Router);
  protected readonly modoSimulado = inject(MODO_SIMULADO);

  /** Query param `volver` (withComponentInputBinding). */
  readonly volver = input<string | undefined>();

  private readonly modelo = signal<LoginIn>({ email: '', password: '' });
  protected readonly formulario = form(this.modelo, (campos) => {
    requerido(campos.email, $localize`:@@login.email_requerido:Escribe tu correo electrónico.`);
    correo(campos.email, $localize`:@@login.email_invalido:Escribe un correo electrónico válido.`);
    requerido(campos.password, $localize`:@@login.password_requerida:Escribe tu contraseña.`);
  });

  protected readonly enviando = signal(false);
  protected readonly errorGeneral = signal<string | null>(null);
  protected readonly mostrarPassword = signal(false);

  protected readonly errorEmail = computed(() => this.errorVisible(this.formulario.email));
  protected readonly errorPassword = computed(() => this.errorVisible(this.formulario.password));

  protected alternarPassword(): void {
    this.mostrarPassword.update((v) => !v);
  }

  protected async enviar(evento: Event): Promise<void> {
    evento.preventDefault();
    if (this.enviando()) {
      return;
    }
    await submit(this.formulario, async () => {
      await this.iniciarSesion();
      return undefined;
    });
  }

  private async iniciarSesion(): Promise<void> {
    this.enviando.set(true);
    this.errorGeneral.set(null);
    try {
      await this.sesion.iniciar({ ...this.modelo(), email: this.modelo().email.trim() });
      this.vaciarPassword();
      await this.router.navigateByUrl(rutaInternaSegura(this.volver()));
    } catch (error) {
      this.errorGeneral.set(mensajeLogin(aErrorApp(error)));
      this.vaciarPassword();
    } finally {
      this.enviando.set(false);
    }
  }

  /** La contraseña no permanece en el formulario tras un intento, con éxito o sin él. */
  private vaciarPassword(): void {
    this.modelo.update((m) => ({ ...m, password: '' }));
    this.formulario.password().reset('');
  }

  private errorVisible(campo: typeof this.formulario.email): string | null {
    const estado = campo();
    return estado.touched() ? primerError(estado.errors()) : null;
  }
}
