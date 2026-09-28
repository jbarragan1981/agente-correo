import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { crearSesionPrueba } from '../../../testing/ayudas-http';
import { LIMITE_REFRESH_MS } from './auth-api';
import { RUTAS_AUTH } from './contrato-auth';
import { SesionStore } from './sesion.store';

/** Límite de tiempo real del refresh de arranque (plan §4.4: 5 s), con el cliente HTTP verdadero. */
describe('SesionStore.restaurar · límite de tiempo (QA)', () => {
  let controlador: HttpTestingController;
  let store: SesionStore;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    controlador = TestBed.inject(HttpTestingController);
    store = TestBed.inject(SesionStore);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('el límite es de 5 segundos', () => {
    expect(LIMITE_REFRESH_MS).toBe(5000);
  });

  it('el servidor no responde → a los 5 s la sesión queda anonima y el arranque continúa', async () => {
    const promesa = store.restaurar();
    controlador.expectOne(RUTAS_AUTH.refresh);
    expect(store.estado()).toBe('restaurando');
    await vi.advanceTimersByTimeAsync(LIMITE_REFRESH_MS - 1);
    expect(store.estado()).toBe('restaurando');
    await vi.advanceTimersByTimeAsync(1);
    await promesa;
    expect([store.estado(), store.tokenActual()]).toEqual(['anonima', null]);
  });

  it('responde justo antes del límite → autenticada', async () => {
    const promesa = store.restaurar();
    const peticion = controlador.expectOne(RUTAS_AUTH.refresh);
    await vi.advanceTimersByTimeAsync(LIMITE_REFRESH_MS - 1);
    peticion.flush(crearSesionPrueba(['admin']));
    await promesa;
    expect(store.estado()).toBe('autenticada');
  });
});
