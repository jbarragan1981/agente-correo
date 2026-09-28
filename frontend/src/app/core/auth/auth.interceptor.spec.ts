import { HttpClient, HttpContext, provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  HttpTestingController,
  TestRequest,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import type { MockInstance } from 'vitest';

import { crearSesionPrueba, cuerpoProblema } from '../../../testing/ayudas-http';
import { SIN_TOKEN } from '../errores/contexto-http';
import { erroresInterceptor } from '../errores/errores.interceptor';
import { NotificadorErrores } from '../errores/notificador-errores';
import { CABECERA_CORRELACION, correlacionInterceptor } from '../http/correlacion.interceptor';
import { authInterceptor } from './auth.interceptor';
import { RUTAS_AUTH } from './contrato-auth';
import { SesionStore } from './sesion.store';

const PROBLEMA = { 'Content-Type': 'application/problem+json' };

describe('authInterceptor', () => {
  let http: HttpClient;
  let controlador: HttpTestingController;
  let sesion: SesionStore;
  let navegar: MockInstance<Router['navigate']>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(
          withInterceptors([correlacionInterceptor, authInterceptor, erroresInterceptor]),
        ),
        provideHttpClientTesting(),
        { provide: NotificadorErrores, useValue: { mostrar: vi.fn() } },
      ],
    });
    http = TestBed.inject(HttpClient);
    controlador = TestBed.inject(HttpTestingController);
    sesion = TestBed.inject(SesionStore);
    navegar = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
  });

  afterEach(() => controlador.verify());

  async function iniciarSesion(token = 'simulado.inicial'): Promise<void> {
    const promesa = sesion.iniciar({
      email: 'persona@viamatica.test',
      password: 'prueba-panel-local',
    });
    controlador.expectOne(RUTAS_AUTH.login).flush(crearSesionPrueba(['operador'], token));
    await promesa;
  }

  function responder401(peticion: TestRequest): void {
    peticion.flush(cuerpoProblema('no_autenticado', 401), {
      status: 401,
      statusText: 'x',
      headers: PROBLEMA,
    });
  }

  function pedir(url: string, contexto?: HttpContext): Promise<unknown> {
    return firstValueFrom(http.get(url, { context: contexto })).catch((e: unknown) => e);
  }

  describe('adjuntar el token', () => {
    beforeEach(async () => {
      await iniciarSesion();
    });

    it('ruta relativa /api/ → Authorization Bearer', () => {
      void pedir('/api/v1/cuentas');
      expect(controlador.expectOne('/api/v1/cuentas').request.headers.get('Authorization')).toBe(
        'Bearer simulado.inicial',
      );
    });

    it.each([
      'https://evil.test/api/v1/cuentas',
      '//evil.test/api/v1/cuentas',
      '/otra/api/v1',
      RUTAS_AUTH.login,
      RUTAS_AUTH.refresh,
      `${RUTAS_AUTH.refresh}?x=1`,
    ])('URL %s → sin Authorization', (url) => {
      void pedir(url);
      expect(controlador.expectOne(url).request.headers.has('Authorization')).toBe(false);
    });

    it('contexto SIN_TOKEN → sin Authorization', () => {
      void pedir('/api/v1/cuentas', new HttpContext().set(SIN_TOKEN, true));
      expect(controlador.expectOne('/api/v1/cuentas').request.headers.has('Authorization')).toBe(
        false,
      );
    });
  });

  it('sin sesión → sin Authorization', () => {
    void pedir('/api/v1/cuentas');
    expect(controlador.expectOne('/api/v1/cuentas').request.headers.has('Authorization')).toBe(
      false,
    );
  });

  describe('401', () => {
    beforeEach(async () => {
      await iniciarSesion();
    });

    it('tres 401 concurrentes → una sola llamada a /auth/refresh', async () => {
      const urls = ['/api/v1/a', '/api/v1/b', '/api/v1/c'];
      const promesas = urls.map((url) => pedir(url));
      urls.forEach((url) => responder401(controlador.expectOne(url)));
      await Promise.resolve();
      const refrescos = controlador.match(RUTAS_AUTH.refresh);
      refrescos.forEach((r) => r.flush(crearSesionPrueba(['operador'], 'simulado.nuevo')));
      await new Promise((r) => setTimeout(r));
      urls.forEach((url) => controlador.expectOne(url).flush({ ok: true }));
      await Promise.all(promesas);
      expect(refrescos.length).toBe(1);
    });

    it('refresh correcto → reintenta una vez con el token nuevo y un X-Request-ID distinto', async () => {
      const promesa = pedir('/api/v1/a');
      const original = controlador.expectOne('/api/v1/a');
      const idOriginal = original.request.headers.get(CABECERA_CORRELACION);
      responder401(original);
      await Promise.resolve();
      controlador
        .expectOne(RUTAS_AUTH.refresh)
        .flush(crearSesionPrueba(['operador'], 'simulado.nuevo'));
      await new Promise((r) => setTimeout(r));
      const reintento = controlador.expectOne('/api/v1/a');
      reintento.flush({ ok: true });
      expect(await promesa).toEqual({ ok: true });
      expect([
        reintento.request.headers.get('Authorization'),
        reintento.request.headers.get(CABECERA_CORRELACION) !== idOriginal,
      ]).toEqual(['Bearer simulado.nuevo', true]);
    });

    it('reintento con 401 → cierra la sesión local y navega a /login con volver', async () => {
      const promesa = pedir('/api/v1/a');
      responder401(controlador.expectOne('/api/v1/a'));
      await Promise.resolve();
      controlador
        .expectOne(RUTAS_AUTH.refresh)
        .flush(crearSesionPrueba(['operador'], 'simulado.nuevo'));
      await new Promise((r) => setTimeout(r));
      responder401(controlador.expectOne('/api/v1/a'));
      await promesa;
      expect([sesion.autenticada(), navegar.mock.calls[0]]).toEqual([
        false,
        [['/login'], { queryParams: { volver: '/' } }],
      ]);
    });

    it('refresh fallido → cierra la sesión local, navega a /login y no reintenta', async () => {
      const promesa = pedir('/api/v1/a');
      responder401(controlador.expectOne('/api/v1/a'));
      await Promise.resolve();
      responder401(controlador.expectOne(RUTAS_AUTH.refresh));
      const error = (await promesa) as { estado: number };
      controlador.expectNone('/api/v1/a');
      expect([sesion.autenticada(), navegar.mock.calls.length, error.estado]).toEqual([
        false,
        1,
        401,
      ]);
    });

    it('error distinto de 401 → no refresca', async () => {
      const promesa = pedir('/api/v1/a');
      controlador
        .expectOne('/api/v1/a')
        .flush(cuerpoProblema('conflicto', 409), {
          status: 409,
          statusText: 'x',
          headers: PROBLEMA,
        });
      await promesa;
      controlador.expectNone(RUTAS_AUTH.refresh);
      expect(sesion.autenticada()).toBe(true);
    });

    it('401 de /auth/me → no refresca', async () => {
      const promesa = pedir(RUTAS_AUTH.yo);
      responder401(controlador.expectOne(RUTAS_AUTH.yo));
      await promesa;
      controlador.expectNone(RUTAS_AUTH.refresh);
      expect(sesion.autenticada()).toBe(true);
    });
  });

  it('401 sin sesión en una ruta sin token → no refresca', async () => {
    const promesa = pedir('/api/v1/a', new HttpContext().set(SIN_TOKEN, true));
    responder401(controlador.expectOne('/api/v1/a'));
    await promesa;
    controlador.expectNone(RUTAS_AUTH.refresh);
    expect(navegar).not.toHaveBeenCalled();
  });
});
