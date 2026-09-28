import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { BreakpointObserver, BreakpointState } from '@angular/cdk/layout';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { BehaviorSubject } from 'rxjs';

import { AlmacenMemoria } from '../../../testing/almacen-memoria';
import { crearSesionPrueba } from '../../../testing/ayudas-http';
import { AuthApi } from '../auth/auth-api';
import { Rol, SesionOut } from '../auth/contrato-auth';
import { SesionStore } from '../auth/sesion.store';
import { MODO_SIMULADO } from '../mocks/modo-simulado';
import { LayoutPrincipal } from './layout-principal';
import { ALMACEN_PREFERENCIAS, CLAVE_SIDEBAR } from './preferencias-ui';

describe('LayoutPrincipal', () => {
  const api = {
    login: vi.fn<() => Promise<SesionOut>>(),
    refrescar: vi.fn<() => Promise<SesionOut>>(),
    cerrarSesion: vi.fn<() => Promise<void>>(),
  };
  let almacen: AlmacenMemoria;
  let pantalla: BehaviorSubject<BreakpointState>;

  async function crear(roles: Rol[], modoSimulado = false) {
    almacen = new AlmacenMemoria();
    pantalla = new BehaviorSubject<BreakpointState>({ matches: false, breakpoints: {} });
    TestBed.configureTestingModule({
      imports: [LayoutPrincipal],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AuthApi, useValue: api },
        { provide: ALMACEN_PREFERENCIAS, useValue: almacen },
        { provide: MODO_SIMULADO, useValue: modoSimulado },
        { provide: BreakpointObserver, useValue: { observe: () => pantalla } },
      ],
    });
    api.login.mockResolvedValue(crearSesionPrueba(roles));
    api.cerrarSesion.mockResolvedValue(undefined);
    await TestBed.inject(SesionStore).iniciar({ email: 'a@viamatica.test', password: 'x' });
    const fixture = TestBed.createComponent(LayoutPrincipal);
    await fixture.whenStable();
    return { fixture, raiz: fixture.nativeElement as HTMLElement };
  }

  function etiquetas(raiz: HTMLElement): string[] {
    return [...raiz.querySelectorAll('.vm-nav-enlace span')].map(
      (s) => s.textContent?.trim() ?? '',
    );
  }

  it('operador → menú sin secciones de admin', async () => {
    const { raiz } = await crear(['operador']);
    expect(etiquetas(raiz)).not.toContain('Usuarios');
  });

  it('admin → menú con todas las secciones', async () => {
    const { raiz } = await crear(['admin']);
    expect(etiquetas(raiz).length).toBe(11);
  });

  it('colapsar → persiste vm.sidebar.colapsado sin datos de sesión', async () => {
    const { fixture, raiz } = await crear(['auditor']);
    raiz.querySelector<HTMLButtonElement>('.vm-colapsar')?.click();
    await fixture.whenStable();
    expect([almacen.getItem(CLAVE_SIDEBAR), almacen.length]).toEqual(['true', 1]);
  });

  it('pantalla estrecha → modo móvil con botón de menú', async () => {
    const { fixture, raiz } = await crear(['auditor']);
    pantalla.next({ matches: true, breakpoints: {} });
    await fixture.whenStable();
    expect(
      raiz.querySelector('[aria-controls="vm-menu-lateral"]')?.getAttribute('aria-label'),
    ).toBe('Abrir menú de navegación');
  });

  it('MODO_SIMULADO → aviso visible', async () => {
    const { raiz } = await crear(['auditor'], true);
    expect(raiz.querySelector('.vm-aviso-simulado')).not.toBeNull();
  });

  it('alternar tema → cambia data-tema del documento', async () => {
    const { fixture, raiz } = await crear(['auditor']);
    const antes = document.documentElement.dataset['tema'];
    raiz.querySelector<HTMLButtonElement>('[aria-pressed]')?.click();
    await fixture.whenStable();
    expect(document.documentElement.dataset['tema']).not.toBe(antes);
  });

  it('cerrar sesión → llama a logout y navega a /login', async () => {
    const { fixture } = await crear(['auditor']);
    const navegar = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    fixture.debugElement.query((d) => d.name === 'vm-shell').triggerEventHandler('cerrarSesion');
    await vi.waitFor(() => expect(navegar).toHaveBeenCalledWith(['/login']));
  });
});
