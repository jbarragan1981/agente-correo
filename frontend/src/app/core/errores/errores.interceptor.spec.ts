import { HttpClient, HttpContext, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';

import { cuerpoProblema } from '../../../testing/ayudas-http';
import { SILENCIAR_ERRORES } from './contexto-http';
import { ErrorApp, esErrorApp } from './error-app';
import { erroresInterceptor } from './errores.interceptor';
import { NotificadorErrores } from './notificador-errores';

const CABECERAS = { 'Content-Type': 'application/problem+json' };

describe('erroresInterceptor', () => {
  let http: HttpClient;
  let controlador: HttpTestingController;
  const mostrar = vi.fn<(e: ErrorApp) => Promise<void>>();

  beforeEach(() => {
    mostrar.mockReset().mockResolvedValue(undefined);
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([erroresInterceptor])),
        provideHttpClientTesting(),
        { provide: NotificadorErrores, useValue: { mostrar } },
      ],
    });
    http = TestBed.inject(HttpClient);
    controlador = TestBed.inject(HttpTestingController);
  });

  afterEach(() => controlador.verify());

  function fallar(estado: number, tipo: string, contexto?: HttpContext): Promise<unknown> {
    const promesa = firstValueFrom(http.get('/api/v1/x', { context: contexto })).catch(
      (e: unknown) => e,
    );
    controlador
      .expectOne('/api/v1/x')
      .flush(cuerpoProblema(tipo, estado), { status: estado, statusText: 'x', headers: CABECERAS });
    return promesa;
  }

  it('409 → rechaza con ErrorApp', async () => {
    expect(esErrorApp(await fallar(409, 'conflicto'))).toBe(true);
  });

  it('500 → notifica el ErrorApp', async () => {
    await fallar(500, 'error_interno');
    expect(mostrar).toHaveBeenCalledWith(expect.objectContaining({ tipo: 'error_interno' }));
  });

  it('SILENCIAR_ERRORES → no notifica', async () => {
    await fallar(500, 'error_interno', new HttpContext().set(SILENCIAR_ERRORES, true));
    expect(mostrar).not.toHaveBeenCalled();
  });

  it('401 → no notifica (lo gestiona authInterceptor)', async () => {
    await fallar(401, 'no_autenticado');
    expect(mostrar).not.toHaveBeenCalled();
  });

  it('respuesta correcta → pasa sin cambios', async () => {
    const promesa = firstValueFrom(http.get<{ ok: boolean }>('/api/v1/x'));
    controlador.expectOne('/api/v1/x').flush({ ok: true });
    expect(await promesa).toEqual({ ok: true });
  });
});
