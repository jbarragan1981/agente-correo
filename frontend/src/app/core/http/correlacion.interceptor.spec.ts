import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { CABECERA_CORRELACION, correlacionInterceptor } from './correlacion.interceptor';

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe('correlacionInterceptor', () => {
  let http: HttpClient;
  let controlador: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([correlacionInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    controlador = TestBed.inject(HttpTestingController);
  });

  afterEach(() => controlador.verify());

  it('petición a /api/ → X-Request-ID UUID v4', () => {
    http.get('/api/v1/salud').subscribe();
    expect(
      controlador.expectOne('/api/v1/salud').request.headers.get(CABECERA_CORRELACION),
    ).toMatch(UUID_V4);
  });

  it('dos peticiones → identificadores distintos', () => {
    http.get('/api/v1/a').subscribe();
    http.get('/api/v1/b').subscribe();
    const a = controlador.expectOne('/api/v1/a').request.headers.get(CABECERA_CORRELACION);
    const b = controlador.expectOne('/api/v1/b').request.headers.get(CABECERA_CORRELACION);
    expect(a).not.toBe(b);
  });

  it('URL fuera de /api/ → sin cabecera', () => {
    http.get('/assets/x.json').subscribe();
    expect(controlador.expectOne('/assets/x.json').request.headers.has(CABECERA_CORRELACION)).toBe(
      false,
    );
  });
});
