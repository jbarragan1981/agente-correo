import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter, withComponentInputBinding } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';

import { crearSesionPrueba } from '../../../testing/ayudas-http';
import { routes } from '../../app.routes';
import { SECCIONES } from '../layout/navegacion';
import { AuthApi } from './auth-api';
import { ROLES, Rol, SesionOut } from './contrato-auth';
import { SesionStore } from './sesion.store';

describe('guards de rutas', () => {
  const api = {
    login: vi.fn<() => Promise<SesionOut>>(),
    refrescar: vi.fn<() => Promise<SesionOut>>(),
    cerrarSesion: vi.fn<() => Promise<void>>(),
  };

  beforeEach(() => {
    Object.values(api).forEach((f) => f.mockReset());
    TestBed.configureTestingModule({
      providers: [
        provideRouter(routes, withComponentInputBinding()),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AuthApi, useValue: api },
      ],
    });
  });

  async function conSesion(roles: Rol[]): Promise<void> {
    api.login.mockResolvedValue(crearSesionPrueba(roles));
    await TestBed.inject(SesionStore).iniciar({ email: 'a@viamatica.test', password: 'x' });
  }

  async function navegar(url: string): Promise<string> {
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl(url);
    return TestBed.inject(Router).url;
  }

  const matriz = ROLES.flatMap((rol) =>
    SECCIONES.map((s) => [rol, s.ruta, s.roles.includes(rol)] as const),
  );

  it.each(matriz)(
    'rol %s en /%s (permitido: %s) → ruta o /sin-permiso',
    async (rol, ruta, permitido) => {
      await conSesion([rol]);
      expect(await navegar(`/${ruta}`)).toBe(permitido ? `/${ruta}` : '/sin-permiso');
    },
  );

  it('sin sesión y enlace profundo → /login con volver', async () => {
    expect(await navegar('/bandeja?filtro=hoy')).toBe('/login?volver=%2Fbandeja%3Ffiltro%3Dhoy');
  });

  it('con sesión en /login → /inicio', async () => {
    await conSesion(['auditor']);
    expect(await navegar('/login')).toBe('/inicio');
  });

  it('raíz → /inicio', async () => {
    await conSesion(['auditor']);
    expect(await navegar('/')).toBe('/inicio');
  });

  it('/sin-permiso con sesión → se muestra', async () => {
    await conSesion(['auditor']);
    expect(await navegar('/sin-permiso')).toBe('/sin-permiso');
  });

  it('ruta desconocida con sesión → página no encontrada sin redirigir', async () => {
    await conSesion(['operador']);
    expect(await navegar('/no-existe')).toBe('/no-existe');
  });

  it('ruta desconocida sin sesión → /login con volver (no revela qué rutas existen)', async () => {
    expect(await navegar('/no-existe')).toBe('/login?volver=%2Fno-existe');
  });

  it('restauración en curso → espera y deja pasar si termina autenticada', async () => {
    let resolver: (s: SesionOut) => void = () => undefined;
    api.refrescar.mockReturnValue(new Promise((r) => (resolver = r)));
    void TestBed.inject(SesionStore).restaurar();
    const destino = navegar('/inicio');
    resolver(crearSesionPrueba(['operador']));
    expect(await destino).toBe('/inicio');
  });
});
