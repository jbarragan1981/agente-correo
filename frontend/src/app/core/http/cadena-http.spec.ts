import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  HttpTestingController,
  TestRequest,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import type { MockInstance } from 'vitest';

import { crearSesionPrueba, cuerpoProblema, tokenPrueba } from '../../../testing/ayudas-http';
import { authInterceptor } from '../auth/auth.interceptor';
import { RUTAS_AUTH } from '../auth/contrato-auth';
import { SesionStore } from '../auth/sesion.store';
import { ErrorApp, esErrorApp } from '../errores/error-app';
import { erroresInterceptor } from '../errores/errores.interceptor';
import { NotificadorErrores } from '../errores/notificador-errores';
import { CABECERA_CORRELACION, correlacionInterceptor } from './correlacion.interceptor';

/**
 * Cadena real de interceptores (correlación → auth → errores) con casos adversariales de QA:
 * bucles de refresh, cuerpos sin problem+json, URLs absolutas y fuga del token (CA6 a CA9).
 */
const PROBLEMA = { 'Content-Type': 'application/problem+json' };
const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe('cadena de interceptores HTTP (QA)', () => {
  let http: HttpClient;
  let controlador: HttpTestingController;
  let sesion: SesionStore;
  let navegar: MockInstance<Router['navigate']>;
  const mostrar = vi.fn<(e: ErrorApp) => Promise<void>>();
  const vistas: TestRequest[] = [];

  beforeEach(() => {
    mostrar.mockReset().mockResolvedValue(undefined);
    vistas.length = 0;
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(
          withInterceptors([correlacionInterceptor, authInterceptor, erroresInterceptor]),
        ),
        provideHttpClientTesting(),
        { provide: NotificadorErrores, useValue: { mostrar, texto: (e: ErrorApp) => e.mensaje } },
      ],
    });
    http = TestBed.inject(HttpClient);
    controlador = TestBed.inject(HttpTestingController);
    sesion = TestBed.inject(SesionStore);
    navegar = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
  });

  afterEach(() => controlador.verify());

  function tomar(url: string): TestRequest {
    const peticion = controlador.expectOne(url);
    vistas.push(peticion);
    return peticion;
  }

  async function iniciarSesion(token = tokenPrueba()): Promise<string> {
    const promesa = sesion.iniciar({ email: 'a@viamatica.test', password: 'prueba-panel-local' });
    tomar(RUTAS_AUTH.login).flush(crearSesionPrueba(['operador'], token));
    await promesa;
    return token;
  }

  function pedir(url: string): Promise<unknown> {
    return firstValueFrom(http.get(url)).catch((e: unknown) => e);
  }

  function responder(
    peticion: TestRequest,
    estado: number,
    cuerpo: object | string | null,
    cabeceras: Record<string, string> = {},
  ): void {
    peticion.flush(cuerpo, { status: estado, statusText: 'x', headers: cabeceras });
  }

  /** Espera (sondeo de condición, sin pausas fijas) a que exista una petición a `url`. */
  async function esperar(url: string): Promise<TestRequest> {
    let encontrada: TestRequest | undefined;
    await vi.waitFor(() => {
      encontrada = controlador.match(url)[0];
      if (!encontrada) throw new Error(`Aún no hay petición a ${url}`);
    });
    vistas.push(encontrada!);
    return encontrada!;
  }

  const NO_AUTENTICADO = cuerpoProblema('no_autenticado', 401);

  describe('401 persistente (sin bucles)', () => {
    it('refresh que también da 401 → sin reintento, sin más peticiones y sesión cerrada', async () => {
      await iniciarSesion();
      const resultado = pedir('/api/v1/datos');
      responder(tomar('/api/v1/datos'), 401, NO_AUTENTICADO, PROBLEMA);
      responder(await esperar(RUTAS_AUTH.refresh), 401, NO_AUTENTICADO, PROBLEMA);
      const error = await resultado;
      expect([
        esErrorApp(error),
        controlador.match(() => true).length,
        sesion.autenticada(),
        navegar.mock.calls.length,
      ]).toEqual([true, 0, false, 1]);
    });

    it('reintento con 401 → 3 peticiones en total, un solo refresh y navegación única', async () => {
      await iniciarSesion();
      const resultado = pedir('/api/v1/datos');
      responder(tomar('/api/v1/datos'), 401, NO_AUTENTICADO, PROBLEMA);
      responder(await esperar(RUTAS_AUTH.refresh), 200, crearSesionPrueba(['operador']));
      const reintento = await esperar('/api/v1/datos');
      responder(reintento, 401, NO_AUTENTICADO, PROBLEMA);
      await resultado;
      expect([
        controlador.match(() => true).length,
        vistas.filter((v) => v.request.url === RUTAS_AUTH.refresh).length,
        sesion.autenticada(),
        navegar.mock.calls.length,
      ]).toEqual([0, 1, false, 1]);
    });

    it('navegación tras 401 persistente → /login con volver = ruta actual', async () => {
      await iniciarSesion();
      const resultado = pedir('/api/v1/datos');
      responder(tomar('/api/v1/datos'), 401, NO_AUTENTICADO, PROBLEMA);
      responder(await esperar(RUTAS_AUTH.refresh), 401, NO_AUTENTICADO, PROBLEMA);
      await resultado;
      expect(navegar).toHaveBeenCalledWith(['/login'], { queryParams: { volver: '/' } });
    });
  });

  describe('URLs absolutas o ambiguas (CA7)', () => {
    it.each([
      'https://evil.test/api/v1/datos',
      '//evil.test/api/v1/datos',
      'http://127.0.0.1:9/api/v1/datos',
      '/apiario/datos',
      'api/v1/datos',
      '/API/v1/datos',
    ])('%s → sin Authorization', async (url) => {
      await iniciarSesion();
      const promesa = pedir(url);
      const peticion = tomar(url);
      expect(peticion.request.headers.has('Authorization')).toBe(false);
      peticion.flush({});
      await promesa;
    });

    it.each(['https://evil.test/api/v1/datos', '//evil.test/api/v1/datos', 'api/v1/datos'])(
      '%s → sin X-Request-ID (no se filtra correlación a terceros)',
      async (url) => {
        const promesa = pedir(url);
        const peticion = tomar(url);
        expect(peticion.request.headers.has(CABECERA_CORRELACION)).toBe(false);
        peticion.flush({});
        await promesa;
      },
    );

    it('401 de una URL externa → no dispara refresh ni cierra la sesión', async () => {
      await iniciarSesion();
      const promesa = pedir('https://evil.test/api/v1/datos');
      responder(tomar('https://evil.test/api/v1/datos'), 401, 'no', {});
      await promesa;
      expect([controlador.match(RUTAS_AUTH.refresh).length, sesion.autenticada()]).toEqual([
        0,
        true,
      ]);
    });

    it.each([`${RUTAS_AUTH.login}?x=1`, `${RUTAS_AUTH.refresh}?y=2`, RUTAS_AUTH.logout])(
      '%s → nunca lleva Authorization',
      async (url) => {
        await iniciarSesion();
        const promesa = firstValueFrom(http.post(url, null)).catch((e: unknown) => e);
        const peticion = tomar(url);
        expect(peticion.request.headers.has('Authorization')).toBe(false);
        peticion.flush({});
        await promesa;
      },
    );

    // BUG-02 (baja): RUTAS_SIN_TOKEN compara igualdad exacta y `/api/v1/auth/login/` (barra final)
    // sí lleva Authorization. La aplicación nunca usa esa forma. Al corregirlo en
    // core/auth/auth.interceptor.ts (comparar con la barra final normalizada), quitar `.fails`.
    it.fails('BUG-02: ruta de login con barra final → sin Authorization', async () => {
      await iniciarSesion();
      const promesa = firstValueFrom(http.post(`${RUTAS_AUTH.login}/`, null)).catch(() => 0);
      const peticion = tomar(`${RUTAS_AUTH.login}/`);
      const lleva = peticion.request.headers.has('Authorization');
      peticion.flush({});
      await promesa;
      expect(lleva).toBe(false);
    });
  });

  describe('token fuera de URL y de cuerpos', () => {
    it('el token solo viaja en la cabecera Authorization', async () => {
      const token = await iniciarSesion();
      const promesa = pedir('/api/v1/datos?x=1');
      const peticion = tomar('/api/v1/datos?x=1');
      peticion.flush({});
      await promesa;
      expect([
        peticion.request.urlWithParams.includes(token),
        JSON.stringify(peticion.request.body ?? null).includes(token),
        peticion.request.headers.get('Authorization'),
      ]).toEqual([false, false, `Bearer ${token}`]);
    });
  });

  describe('X-Request-ID (CA8)', () => {
    it('petición, refresh y reintento → tres UUID v4 distintos', async () => {
      await iniciarSesion();
      const resultado = pedir('/api/v1/datos');
      const primera = tomar('/api/v1/datos');
      responder(primera, 401, NO_AUTENTICADO, PROBLEMA);
      const refresh = await esperar(RUTAS_AUTH.refresh);
      responder(refresh, 200, crearSesionPrueba(['operador']));
      const reintento = await esperar('/api/v1/datos');
      reintento.flush({});
      await resultado;
      const ids = [primera, refresh, reintento].map((p) =>
        p.request.headers.get(CABECERA_CORRELACION),
      );
      expect([ids.every((id) => UUID_V4.test(id ?? '')), new Set(ids).size]).toEqual([true, 3]);
    });
  });

  describe('errores sin problem+json (CA9)', () => {
    it.each([
      [500, '<html><body>nginx/1.27 Bad Gateway</body></html>', 'text/html'],
      [502, 'upstream connect error or disconnect/reset before headers', 'text/plain'],
      [503, '{"detail":"traceback: File \\"/app/main.py\\""}', 'application/json'],
      [500, '', 'text/plain'],
    ])(
      'estado %d con cuerpo ajeno (%s) → mensaje fijo sin el cuerpo',
      async (estado, cuerpo, tipo) => {
        const promesa = pedir('/api/v1/datos');
        responder(tomar('/api/v1/datos'), estado, cuerpo, { 'Content-Type': tipo });
        const error = (await promesa) as ErrorApp;
        const visible = JSON.stringify([error.mensaje, error.detalle, mostrar.mock.calls]);
        expect([
          esErrorApp(error),
          error.estado,
          cuerpo === '' || !visible.includes(cuerpo),
        ]).toEqual([true, estado, true]);
      },
    );

    it('cuerpo null con 500 y sin cabeceras → ErrorApp desconocido', async () => {
      const promesa = pedir('/api/v1/datos');
      responder(tomar('/api/v1/datos'), 500, null);
      expect(((await promesa) as ErrorApp).tipo).toBe('desconocido');
    });

    it('429 con problem+json y Retry-After → reintentarEnS y notificación', async () => {
      const promesa = pedir('/api/v1/datos');
      responder(tomar('/api/v1/datos'), 429, cuerpoProblema('limite_excedido', 429), {
        ...PROBLEMA,
        'Retry-After': '42',
      });
      const error = (await promesa) as ErrorApp;
      expect([error.tipo, error.reintentarEnS, mostrar.mock.calls.length]).toEqual([
        'limite_excedido',
        42,
        1,
      ]);
    });

    it('red caída (estado 0) → tipo red y notificación', async () => {
      const promesa = pedir('/api/v1/datos');
      tomar('/api/v1/datos').error(new ProgressEvent('error'), { status: 0, statusText: '' });
      const error = (await promesa) as ErrorApp;
      expect([error.tipo, error.estado, mostrar.mock.calls.length]).toEqual(['red', 0, 1]);
    });
  });
});
