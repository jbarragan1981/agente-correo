import {
  HttpClient,
  HttpErrorResponse,
  HttpResponse,
  provideHttpClient,
  withInterceptors,
} from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';

import { RUTAS_AUTH, SesionOut } from '../auth/contrato-auth';
import {
  MARCA_SIMULADA,
  MAX_FALLOS_SEGUIDOS,
  apiSimuladaInterceptor,
  reiniciarApiSimulada,
} from './api-simulada.interceptor';
import { CONTRASENA_SIMULADA, USUARIOS_SIMULADOS } from './usuarios-simulados';

describe('apiSimuladaInterceptor', () => {
  let http: HttpClient;
  let controlador: HttpTestingController;

  beforeEach(() => {
    vi.useFakeTimers();
    reiniciarApiSimulada();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([apiSimuladaInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    controlador = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    vi.useRealTimers();
    controlador.verify();
  });

  async function resolver<T>(promesa: Promise<T>): Promise<T> {
    await vi.advanceTimersByTimeAsync(400);
    return promesa;
  }

  function login(
    email: string,
    password: string,
  ): Promise<HttpResponse<SesionOut> | HttpErrorResponse> {
    return resolver(
      firstValueFrom(
        http.post<SesionOut>(RUTAS_AUTH.login, { email, password }, { observe: 'response' }),
      ).catch((e: HttpErrorResponse) => e),
    );
  }

  it.each(USUARIOS_SIMULADOS.map((u) => [u.email, u.roles[0]]))(
    'login de %s → sesión con rol %s',
    async (email, rol) => {
      const respuesta = (await login(email, CONTRASENA_SIMULADA)) as HttpResponse<SesionOut>;
      expect(respuesta.body?.usuario.roles).toEqual([rol]);
    },
  );

  it('login correcto → token opaco simulado y marca X-Api-Simulada', async () => {
    const respuesta = (await login(
      'admin@viamatica.test',
      CONTRASENA_SIMULADA,
    )) as HttpResponse<SesionOut>;
    expect([
      respuesta.body?.access_token.startsWith('simulado.'),
      respuesta.headers.get(MARCA_SIMULADA),
    ]).toEqual([true, '1']);
  });

  it('contraseña errónea → 401 problem+json genérico', async () => {
    const error = (await login('admin@viamatica.test', 'otra')) as HttpErrorResponse;
    expect([
      error.status,
      (error.error as { type: string }).type,
      error.headers.get('Content-Type'),
    ]).toEqual([401, 'no_autenticado', 'application/problem+json']);
  });

  it('usuario inexistente → mismo 401 que contraseña errónea', async () => {
    const a = (await login('nadie@viamatica.test', 'x')) as HttpErrorResponse;
    const b = (await login('admin@viamatica.test', 'x')) as HttpErrorResponse;
    expect((a.error as { detail: string }).detail).toBe((b.error as { detail: string }).detail);
  });

  it('sexto intento tras cinco fallos → 429 con Retry-After', async () => {
    for (let i = 0; i < MAX_FALLOS_SEGUIDOS; i++) {
      await login('admin@viamatica.test', 'mal');
    }
    const error = (await login('admin@viamatica.test', CONTRASENA_SIMULADA)) as HttpErrorResponse;
    expect([error.status, error.headers.get('Retry-After')]).toEqual([429, '60']);
  });

  it('refresh → 401 (sin cookie real)', async () => {
    const error = await resolver(
      firstValueFrom(http.post(RUTAS_AUTH.refresh, null)).catch((e: HttpErrorResponse) => e),
    );
    expect((error as HttpErrorResponse).status).toBe(401);
  });

  it('logout → 204', async () => {
    const respuesta = await resolver(
      firstValueFrom(http.post(RUTAS_AUTH.logout, null, { observe: 'response' })),
    );
    expect(respuesta.status).toBe(204);
  });

  it('me con token emitido → usuario; sin token → 401', async () => {
    const sesion = (
      (await login('auditor@viamatica.test', CONTRASENA_SIMULADA)) as HttpResponse<SesionOut>
    ).body;
    const conToken = await resolver(
      firstValueFrom(
        http.get(RUTAS_AUTH.yo, {
          headers: { Authorization: `Bearer ${sesion?.access_token ?? ''}` },
        }),
      ),
    );
    const sinToken = await resolver(
      firstValueFrom(http.get(RUTAS_AUTH.yo)).catch((e: HttpErrorResponse) => e),
    );
    expect([(conToken as { email: string }).email, (sinToken as HttpErrorResponse).status]).toEqual(
      ['auditor@viamatica.test', 401],
    );
  });

  it('ruta que no es de auth → pasa al backend real', () => {
    void firstValueFrom(http.get('/api/v1/salud/listo'));
    controlador.expectOne('/api/v1/salud/listo').flush({ estado: 'listo', comprobaciones: {} });
  });
});
