import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter, withComponentInputBinding } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';

import { crearSesionPrueba } from '../../../testing/ayudas-http';
import { routes } from '../../app.routes';
import { SECCIONES, seccionesPara } from '../layout/navegacion';
import { AuthApi } from './auth-api';
import { Rol, SesionOut } from './contrato-auth';
import { SesionStore } from './sesion.store';

/**
 * Matriz rol x ruta escrita a mano desde docs/planes/e0-4-esqueleto-frontend.md §4.8. La prueba de guards
 * genera su matriz desde `navegacion.ts` y no detectaría un error de datos en ese archivo: esta sí.
 */
const MATRIZ_PLAN: Record<string, readonly Rol[]> = {
  inicio: ['admin', 'operador', 'auditor'],
  dashboard: ['admin', 'operador', 'auditor'],
  bandeja: ['admin', 'operador', 'auditor'],
  aprobaciones: ['admin', 'operador'],
  agentes: ['admin', 'operador', 'auditor'],
  cuentas: ['admin', 'operador', 'auditor'],
  taxonomia: ['admin'],
  webchat: ['admin', 'operador'],
  proveedores: ['admin', 'auditor'],
  usuarios: ['admin'],
  auditoria: ['admin', 'auditor'],
};

describe('matriz de roles del plan §4.8 (QA)', () => {
  const api = {
    login: vi.fn<() => Promise<SesionOut>>(),
    refrescar: vi.fn<() => Promise<SesionOut>>(),
    cerrarSesion: vi.fn<() => Promise<void>>(),
  };

  beforeEach(() => {
    harness = undefined;
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

  async function conRoles(roles: Rol[]): Promise<void> {
    api.login.mockResolvedValue(crearSesionPrueba(roles));
    await TestBed.inject(SesionStore).iniciar({ email: 'a@viamatica.test', password: 'x' });
  }

  let harness: RouterTestingHarness | undefined;

  async function ir(url: string): Promise<string> {
    harness ??= await RouterTestingHarness.create();
    await harness.navigateByUrl(url);
    return TestBed.inject(Router).url;
  }

  it('navegacion.ts contiene exactamente las 11 secciones y roles del plan', () => {
    const actual = Object.fromEntries(SECCIONES.map((s) => [s.ruta, [...s.roles].sort()]));
    const esperado = Object.fromEntries(
      Object.entries(MATRIZ_PLAN).map(([ruta, roles]) => [ruta, [...roles].sort()]),
    );
    expect(actual).toEqual(esperado);
  });

  it.each(
    (['admin', 'operador', 'auditor'] as const).flatMap((rol) =>
      Object.entries(MATRIZ_PLAN).map(([ruta, roles]) => [rol, ruta, roles.includes(rol)] as const),
    ),
  )('rol %s en /%s (permitido: %s) → según la tabla del plan', async (rol, ruta, permitido) => {
    await conRoles([rol]);
    expect(await ir(`/${ruta}`)).toBe(permitido ? `/${ruta}` : '/sin-permiso');
  });

  it('usuario con roles vacíos → /sin-permiso en una sección protegida y el menú no lista nada', async () => {
    await conRoles([]);
    expect([await ir('/bandeja'), seccionesPara([]).length]).toEqual(['/sin-permiso', 0]);
  });

  it('usuario con rol desconocido → /sin-permiso', async () => {
    await conRoles(['superadmin' as Rol]);
    expect(await ir('/inicio')).toBe('/sin-permiso');
  });

  it('roles combinados operador + auditor → acceso a la unión de ambos', async () => {
    await conRoles(['operador', 'auditor']);
    const destinos = [await ir('/aprobaciones'), await ir('/auditoria'), await ir('/usuarios')];
    expect(destinos).toEqual(['/aprobaciones', '/auditoria', '/sin-permiso']);
  });

  it('sin sesión, cada sección protegida → /login con volver a esa ruta', async () => {
    for (const ruta of Object.keys(MATRIZ_PLAN)) {
      expect(await ir(`/${ruta}`)).toBe(`/login?volver=%2F${ruta}`);
    }
  });

  it('sin sesión, /sin-permiso → /login (no se muestra a anónimos)', async () => {
    expect(await ir('/sin-permiso')).toBe('/login?volver=%2Fsin-permiso');
  });
});
