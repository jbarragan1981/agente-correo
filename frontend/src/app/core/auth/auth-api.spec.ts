import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { crearSesionPrueba } from '../../../testing/ayudas-http';
import { SILENCIAR_ERRORES, SIN_TOKEN } from '../errores/contexto-http';
import { AuthApi } from './auth-api';
import { RUTAS_AUTH } from './contrato-auth';

describe('AuthApi', () => {
  let api: AuthApi;
  let controlador: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    api = TestBed.inject(AuthApi);
    controlador = TestBed.inject(HttpTestingController);
  });

  afterEach(() => controlador.verify());

  it('login → POST con SIN_TOKEN y SILENCIAR_ERRORES', async () => {
    const promesa = api.login({ email: 'a@viamatica.test', password: 'x' });
    const peticion = controlador.expectOne(RUTAS_AUTH.login);
    peticion.flush(crearSesionPrueba());
    await promesa;
    const { method, context } = peticion.request;
    expect([method, context.get(SIN_TOKEN), context.get(SILENCIAR_ERRORES)]).toEqual([
      'POST',
      true,
      true,
    ]);
  });

  it('refrescar → POST sin cuerpo y sin token', async () => {
    const promesa = api.refrescar();
    const peticion = controlador.expectOne(RUTAS_AUTH.refresh);
    peticion.flush(crearSesionPrueba());
    await promesa;
    expect([peticion.request.body, peticion.request.context.get(SIN_TOKEN)]).toEqual([null, true]);
  });

  it('cerrarSesion → POST a logout', async () => {
    const promesa = api.cerrarSesion();
    controlador
      .expectOne({ method: 'POST', url: RUTAS_AUTH.logout })
      .flush(null, { status: 204, statusText: 'x' });
    await expect(promesa).resolves.toBeNull();
  });

  it('yo → GET de /auth/me', async () => {
    const usuario = crearSesionPrueba().usuario;
    const promesa = api.yo();
    controlador.expectOne({ method: 'GET', url: RUTAS_AUTH.yo }).flush(usuario);
    await expect(promesa).resolves.toEqual(usuario);
  });
});
