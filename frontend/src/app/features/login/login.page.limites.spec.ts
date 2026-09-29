import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { crearSesionPrueba } from '../../../testing/ayudas-http';
import { AuthApi } from '../../core/auth/auth-api';
import { SesionOut } from '../../core/auth/contrato-auth';
import { LoginPage, MAX_LONGITUD_PASSWORD } from './login.page';

/** Casos límite de QA sobre el formulario de login (CA11): doble envío, caracteres raros y longitudes. */
describe('LoginPage · casos límite (QA)', () => {
  const api = {
    login: vi.fn<() => Promise<SesionOut>>(),
    refrescar: vi.fn<() => Promise<SesionOut>>(),
    cerrarSesion: vi.fn<() => Promise<void>>(),
  };
  let fixture: ComponentFixture<LoginPage>;
  let raiz: HTMLElement;

  async function crear(): Promise<void> {
    Object.values(api).forEach((f) => f.mockReset());
    TestBed.configureTestingModule({
      imports: [LoginPage],
      providers: [provideRouter([]), { provide: AuthApi, useValue: api }],
    });
    vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    fixture = TestBed.createComponent(LoginPage);
    await fixture.whenStable();
    raiz = fixture.nativeElement as HTMLElement;
  }

  function escribir(id: string, valor: string): void {
    const input = raiz.querySelector<HTMLInputElement>(`#${id}`)!;
    input.value = valor;
    input.dispatchEvent(new Event('input'));
    input.dispatchEvent(new Event('blur'));
  }

  function enviarFormulario(): void {
    raiz.querySelector('form')?.dispatchEvent(new Event('submit', { cancelable: true }));
  }

  async function vaciarCola(): Promise<void> {
    await new Promise((r) => setTimeout(r));
    await fixture.whenStable();
  }

  it('doble envío síncrono con la petición en curso → una sola llamada de login', async () => {
    await crear();
    api.login.mockReturnValue(new Promise(() => undefined));
    escribir('login-email', 'admin@viamatica.test');
    escribir('login-password', 'prueba-panel-local');
    enviarFormulario();
    enviarFormulario();
    enviarFormulario();
    await vaciarCola();
    expect(api.login).toHaveBeenCalledTimes(1);
  });

  it('envío repetido tras terminar el primero → dos llamadas (no se bloquea para siempre)', async () => {
    await crear();
    api.login.mockRejectedValue(new Error('x'));
    escribir('login-email', 'admin@viamatica.test');
    escribir('login-password', 'uno');
    enviarFormulario();
    await vaciarCola();
    escribir('login-password', 'dos');
    enviarFormulario();
    await vaciarCola();
    expect(api.login).toHaveBeenCalledTimes(2);
  });

  it('contraseña con espacios, acentos y emoji → se envía tal cual, sin recortar', async () => {
    await crear();
    api.login.mockResolvedValue(crearSesionPrueba());
    const password = '  pässwörd ñ 🔑 ';
    escribir('login-email', 'admin@viamatica.test');
    escribir('login-password', password);
    enviarFormulario();
    await vaciarCola();
    expect(api.login).toHaveBeenCalledWith({ email: 'admin@viamatica.test', password });
  });

  it('correo de 300 caracteres → lo rechaza el validador de formato y no se envía', async () => {
    await crear();
    escribir('login-email', `${'a'.repeat(290)}@viamatica.test`);
    escribir('login-password', 'x');
    enviarFormulario();
    await vaciarCola();
    expect(api.login).not.toHaveBeenCalled();
  });

  it('correo con etiqueta + y subdominios → válido y se envía', async () => {
    await crear();
    api.login.mockResolvedValue(crearSesionPrueba());
    escribir('login-email', 'ana.perez+panel@correo.viamatica.test');
    escribir('login-password', 'x');
    enviarFormulario();
    await vaciarCola();
    expect(api.login).toHaveBeenCalledTimes(1);
  });

  it.each([
    '"><img src=x onerror=alert(1)>@x.test',
    "admin@viamatica.test'; DROP TABLE usuarios;--",
    'sin-arroba',
    'a@',
    '@b.test',
    'a b@viamatica.test',
    '\u0000@x.test',
  ])('correo inválido %j → no se envía y el HTML no se interpreta', async (correo) => {
    await crear();
    escribir('login-email', correo);
    escribir('login-password', 'x');
    enviarFormulario();
    await vaciarCola();
    expect([api.login.mock.calls.length, raiz.querySelectorAll('img, script').length]).toEqual([
      0, 0,
    ]);
  });

  it('error del servidor con HTML en el mensaje → se muestra como texto, sin nodos nuevos', async () => {
    await crear();
    api.login.mockRejectedValue(new Error('<img src=x onerror=alert(1)>'));
    escribir('login-email', 'admin@viamatica.test');
    escribir('login-password', 'x');
    enviarFormulario();
    await vaciarCola();
    expect(raiz.querySelectorAll('img').length).toBe(0);
  });

  it('contraseña de 100 000 caracteres → la página no se rompe y muestra el error de longitud', async () => {
    await crear();
    escribir('login-email', 'admin@viamatica.test');
    escribir('login-password', 'a'.repeat(100_000));
    enviarFormulario();
    await vaciarCola();
    expect(raiz.querySelector('#login-password-error')?.textContent?.trim()).toBe(
      'La contraseña no puede superar 1024 caracteres.',
    );
  });

  // BUG-03 (corregido): regla maxLength en el esquema y maxlength en el control.
  it('BUG-03: contraseña de 100 000 caracteres → no se envía', async () => {
    await crear();
    api.login.mockResolvedValue(crearSesionPrueba());
    escribir('login-email', 'admin@viamatica.test');
    escribir('login-password', 'a'.repeat(100_000));
    enviarFormulario();
    await vaciarCola();
    expect(api.login).not.toHaveBeenCalled();
  });

  it(`contraseña de ${MAX_LONGITUD_PASSWORD + 1} caracteres → error enlazado con aria-describedby y aria-invalid`, async () => {
    await crear();
    escribir('login-email', 'admin@viamatica.test');
    escribir('login-password', 'a'.repeat(MAX_LONGITUD_PASSWORD + 1));
    enviarFormulario();
    await vaciarCola();
    const input = raiz.querySelector<HTMLInputElement>('#login-password');
    expect([input?.getAttribute('aria-describedby'), input?.getAttribute('aria-invalid')]).toEqual([
      'login-password-error',
      'true',
    ]);
  });

  it(`contraseña de exactamente ${MAX_LONGITUD_PASSWORD} caracteres → se envía`, async () => {
    await crear();
    api.login.mockResolvedValue(crearSesionPrueba());
    escribir('login-email', 'admin@viamatica.test');
    escribir('login-password', 'a'.repeat(MAX_LONGITUD_PASSWORD));
    enviarFormulario();
    await vaciarCola();
    expect(api.login).toHaveBeenCalledTimes(1);
  });

  it('el campo de contraseña declara maxlength 1024', async () => {
    await crear();
    expect(raiz.querySelector('#login-password')?.getAttribute('maxlength')).toBe('1024');
  });
});
