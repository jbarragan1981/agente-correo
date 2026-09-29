import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import type { MockInstance } from 'vitest';

import { crearSesionPrueba } from '../../../testing/ayudas-http';
import { AuthApi } from '../../core/auth/auth-api';
import { SesionOut } from '../../core/auth/contrato-auth';
import { crearErrorApp } from '../../core/errores/error-app';
import { MODO_SIMULADO } from '../../core/mocks/modo-simulado';
import { LoginPage, mensajeLogin } from './login.page';

describe('LoginPage', () => {
  const api = {
    login: vi.fn<() => Promise<SesionOut>>(),
    refrescar: vi.fn<() => Promise<SesionOut>>(),
    cerrarSesion: vi.fn<() => Promise<void>>(),
  };
  let fixture: ComponentFixture<LoginPage>;
  let raiz: HTMLElement;
  let navegar: MockInstance<Router['navigateByUrl']>;

  async function crear(volver?: string, modoSimulado = false): Promise<void> {
    Object.values(api).forEach((f) => f.mockReset());
    TestBed.configureTestingModule({
      imports: [LoginPage],
      providers: [
        provideRouter([]),
        { provide: AuthApi, useValue: api },
        { provide: MODO_SIMULADO, useValue: modoSimulado },
      ],
    });
    navegar = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    fixture = TestBed.createComponent(LoginPage);
    if (volver !== undefined) fixture.componentRef.setInput('volver', volver);
    await fixture.whenStable();
    raiz = fixture.nativeElement as HTMLElement;
  }

  function campo(id: string): HTMLInputElement {
    const input = raiz.querySelector<HTMLInputElement>(`#${id}`);
    if (!input) throw new Error(`No existe el campo ${id}`);
    return input;
  }

  function escribir(id: string, valor: string): void {
    const input = campo(id);
    input.value = valor;
    input.dispatchEvent(new Event('input'));
    input.dispatchEvent(new Event('blur'));
  }

  async function enviar(
    email = 'admin@viamatica.test',
    password = 'prueba-panel-local',
  ): Promise<void> {
    escribir('login-email', email);
    escribir('login-password', password);
    raiz.querySelector('form')?.dispatchEvent(new Event('submit', { cancelable: true }));
    // El envío es asíncrono (submit de Signal Forms + store): se vacía la cola de microtareas.
    await new Promise((r) => setTimeout(r));
    await fixture.whenStable();
  }

  function textoError(): string {
    return raiz.querySelector('[role="alert"]')?.textContent?.trim() ?? '';
  }

  it('campos con autocomplete username y current-password', async () => {
    await crear();
    expect([campo('login-email').autocomplete, campo('login-password').autocomplete]).toEqual([
      'username',
      'current-password',
    ]);
  });

  it('enviar vacío → errores en español enlazados con aria-describedby', async () => {
    await crear();
    await enviar('', '');
    expect([
      raiz.querySelector('#login-email-error')?.textContent?.trim(),
      campo('login-email').getAttribute('aria-describedby'),
      raiz.querySelector('#login-password-error')?.textContent?.trim(),
      api.login.mock.calls.length,
    ]).toEqual([
      'Escribe tu correo electrónico.',
      'login-email-error',
      'Escribe tu contraseña.',
      0,
    ]);
  });

  it('correo con formato inválido → mensaje de formato', async () => {
    await crear();
    await enviar('no-es-correo', 'x');
    expect(raiz.querySelector('#login-email-error')?.textContent?.trim()).toBe(
      'Escribe un correo electrónico válido.',
    );
  });

  it('mientras envía → botón deshabilitado', async () => {
    await crear();
    api.login.mockReturnValue(new Promise(() => undefined));
    await enviar();
    expect(raiz.querySelector<HTMLButtonElement>('button[type="submit"]')?.disabled).toBe(true);
  });

  it('401 → mensaje genérico y contraseña vaciada', async () => {
    await crear();
    api.login.mockRejectedValue(crearErrorApp('no_autenticado', 401));
    await enviar();
    expect([textoError(), campo('login-password').value]).toEqual([
      'Correo o contraseña incorrectos.',
      '',
    ]);
  });

  it('429 con Retry-After → mensaje con los segundos', async () => {
    await crear();
    api.login.mockRejectedValue(crearErrorApp('limite_excedido', 429, { reintentarEnS: 60 }));
    await enviar();
    expect(textoError()).toBe('Demasiados intentos. Inténtalo de nuevo en 60 s.');
  });

  it('error de red → mensaje de conexión', async () => {
    await crear();
    api.login.mockRejectedValue(crearErrorApp('red', 0));
    await enviar();
    expect(textoError()).toBe('No se pudo contactar con el servidor.');
  });

  it('éxito con volver interno → navega a esa ruta', async () => {
    await crear('/bandeja?filtro=hoy');
    api.login.mockResolvedValue(crearSesionPrueba());
    await enviar();
    expect(navegar).toHaveBeenCalledWith('/bandeja?filtro=hoy');
  });

  it('éxito con volver externo → navega a /inicio', async () => {
    await crear('https://evil.test');
    api.login.mockResolvedValue(crearSesionPrueba());
    await enviar();
    expect(navegar).toHaveBeenCalledWith('/inicio');
  });

  it('éxito → el correo se envía sin espacios y la contraseña no queda en el formulario', async () => {
    await crear();
    api.login.mockResolvedValue(crearSesionPrueba());
    await enviar('  admin@viamatica.test ', 'prueba-panel-local');
    expect([api.login.mock.calls[0], campo('login-password').value]).toEqual([
      [{ email: 'admin@viamatica.test', password: 'prueba-panel-local' }],
      '',
    ]);
  });

  it('mostrar contraseña → cambia el tipo y aria-pressed', async () => {
    await crear();
    const conmutador = raiz.querySelector<HTMLButtonElement>('[aria-pressed]');
    conmutador?.click();
    await fixture.whenStable();
    expect([campo('login-password').type, conmutador?.getAttribute('aria-pressed')]).toEqual([
      'text',
      'true',
    ]);
  });

  it('modo simulado → nota visible', async () => {
    await crear(undefined, true);
    expect(raiz.querySelector('[role="note"]')).not.toBeNull();
  });

  it('login completo → el token no llega a Storage, cookies ni consola (CA6)', async () => {
    await crear();
    const sesion = crearSesionPrueba();
    api.login.mockResolvedValue(sesion);
    const setItem = vi.spyOn(Storage.prototype, 'setItem');
    const consola = (['log', 'info', 'warn', 'error', 'debug'] as const).map((m) =>
      vi.spyOn(console, m),
    );
    await enviar();
    const llamadas = JSON.stringify([
      ...setItem.mock.calls,
      ...consola.flatMap((c) => c.mock.calls),
    ]);
    expect([
      llamadas.includes(sesion.access_token),
      document.cookie.includes(sesion.access_token),
    ]).toEqual([false, false]);
  });
});

describe('mensajeLogin', () => {
  it('429 sin Retry-After → mensaje genérico de espera', () => {
    expect(mensajeLogin(crearErrorApp('limite_excedido', 429))).toContain('Espera un momento');
  });

  it('otro error → mensaje del catálogo', () => {
    expect(mensajeLogin(crearErrorApp('error_interno', 500))).toBe('Se produjo un error interno.');
  });
});
