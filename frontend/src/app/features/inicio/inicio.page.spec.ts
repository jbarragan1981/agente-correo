import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { crearSesionPrueba, cuerpoProblema } from '../../../testing/ayudas-http';
import { provideApiConfiguration } from '../../core/api/generado/api-configuration';
import { AuthApi } from '../../core/auth/auth-api';
import { Rol, SesionOut } from '../../core/auth/contrato-auth';
import { SesionStore } from '../../core/auth/sesion.store';
import { erroresInterceptor } from '../../core/errores/errores.interceptor';
import { NotificadorErrores } from '../../core/errores/notificador-errores';
import { InicioPage, etiquetaComprobacion } from './inicio.page';

const URL = '/api/v1/salud/listo';

describe('InicioPage', () => {
  let fixture: ComponentFixture<InicioPage>;
  let controlador: HttpTestingController;
  let raiz: HTMLElement;
  const mostrar = vi.fn();

  async function crear(roles: Rol[] = ['operador']): Promise<void> {
    mostrar.mockReset();
    const api = {
      login: vi.fn<() => Promise<SesionOut>>().mockResolvedValue(crearSesionPrueba(roles)),
    };
    TestBed.configureTestingModule({
      imports: [InicioPage],
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([erroresInterceptor])),
        provideHttpClientTesting(),
        provideApiConfiguration(''),
        { provide: AuthApi, useValue: api },
        { provide: NotificadorErrores, useValue: { mostrar } },
      ],
    });
    await TestBed.inject(SesionStore).iniciar({ email: 'a@viamatica.test', password: 'x' });
    controlador = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(InicioPage);
    raiz = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
  }

  /** La petición la lanza resource() tras un ciclo; se espera a que exista. */
  function peticion() {
    return vi.waitFor(() => controlador.expectOne(URL));
  }

  async function responder(cuerpo: Record<string, unknown>, estado = 200): Promise<void> {
    const cabeceras: Record<string, string> =
      estado === 200 ? {} : { 'Content-Type': 'application/problem+json' };
    (await peticion()).flush(cuerpo, { status: estado, statusText: 'x', headers: cabeceras });
    await fixture.whenStable();
  }

  function texto(): string {
    return raiz.textContent?.replace(/\s+/g, ' ') ?? '';
  }

  afterEach(() => controlador.verify());

  it('saluda con el nombre del usuario', async () => {
    await crear();
    await responder({ estado: 'listo', comprobaciones: { base_datos: 'ok' } });
    expect(raiz.querySelector('h1')?.textContent?.trim()).toBe('Hola, Persona de Prueba');
  });

  it('cargando → indicador de progreso', async () => {
    await crear();
    const pendiente = await peticion();
    fixture.detectChanges();
    const cargando = !!raiz.querySelector('mat-progress-bar');
    pendiente.flush({ estado: 'listo', comprobaciones: {} });
    await fixture.whenStable();
    expect(cargando).toBe(true);
  });

  it('listo → estado listo con cada comprobación', async () => {
    await crear();
    await responder({ estado: 'listo', comprobaciones: { base_datos: 'ok', migraciones: 'ok' } });
    expect([
      texto().includes('El sistema está listo.'),
      texto().includes('Base de datos'),
      texto().includes('Migraciones'),
    ]).toEqual([true, true, true]);
  });

  it('503 no_listo → cada comprobación en falla, sin detalles técnicos ni notificación', async () => {
    await crear();
    await responder(
      cuerpoProblema('no_listo', 503, {
        comprobaciones: { base_datos: 'falla', migraciones: 'ok' },
      }),
      503,
    );
    const filas = [...raiz.querySelectorAll('.vm-comprobaciones li')].map((li) =>
      li.textContent?.trim(),
    );
    expect([
      texto().includes('El sistema no está listo.'),
      filas.includes('Base de datosFalla'),
      texto().includes('Detalle del servidor'),
      mostrar.mock.calls.length,
    ]).toEqual([true, true, false, 0]);
  });

  it('error de red → mensaje y Reintentar vuelve a consultar', async () => {
    await crear();
    (await peticion()).error(new ProgressEvent('error'), { status: 0 });
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(raiz.querySelector('[role="alert"]')).not.toBeNull();
    });
    const mensaje = raiz.querySelector('[role="alert"] span')?.textContent?.trim();
    [...raiz.querySelectorAll('button')]
      .find((b) => b.textContent?.includes('Reintentar'))
      ?.click();
    fixture.detectChanges();
    await responder({ estado: 'listo', comprobaciones: {} });
    expect([mensaje, texto().includes('El sistema está listo.')]).toEqual([
      'No se pudo contactar con el servidor.',
      true,
    ]);
  });

  it('accesos → solo secciones permitidas al rol, sin inicio', async () => {
    await crear(['auditor']);
    await responder({ estado: 'listo', comprobaciones: {} });
    const accesos = [...raiz.querySelectorAll('.vm-acceso')].map((a) => a.getAttribute('href'));
    expect([
      accesos.includes('/auditoria'),
      accesos.includes('/usuarios'),
      accesos.includes('/inicio'),
    ]).toEqual([true, false, false]);
  });
});

describe('etiquetaComprobacion', () => {
  it.each([
    ['base_datos', 'Base de datos'],
    ['migraciones', 'Migraciones'],
    ['proveedores', 'Proveedores de IA'],
    ['cola_trabajos', 'cola trabajos'],
  ])('%s → %s', (nombre, etiqueta) => {
    expect(etiquetaComprobacion(nombre)).toBe(etiqueta);
  });
});
