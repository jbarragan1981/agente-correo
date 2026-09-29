import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { crearSesionPrueba } from '../../../testing/ayudas-http';
import { crearErrorApp, esErrorApp } from '../errores/error-app';
import { AuthApi } from './auth-api';
import { SesionOut } from './contrato-auth';
import { SesionStore } from './sesion.store';

describe('SesionStore', () => {
  const api = {
    login: vi.fn<() => Promise<SesionOut>>(),
    refrescar: vi.fn<() => Promise<SesionOut>>(),
    cerrarSesion: vi.fn<() => Promise<void>>(),
  };
  let store: SesionStore;

  beforeEach(() => {
    Object.values(api).forEach((f) => f.mockReset());
    TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthApi, useValue: api }],
    });
    store = TestBed.inject(SesionStore);
    vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
  });

  it('estado inicial → anonima sin usuario', () => {
    expect([store.estado(), store.usuario(), store.tokenActual()]).toEqual(['anonima', null, null]);
  });

  it('iniciar correcto → autenticada con usuario, roles y token', async () => {
    const sesion = crearSesionPrueba(['admin', 'auditor']);
    api.login.mockResolvedValue(sesion);
    await store.iniciar({ email: 'a@viamatica.test', password: 'x' });
    expect([
      store.autenticada(),
      store.roles(),
      store.nombreVisible(),
      store.tokenActual(),
    ]).toEqual([true, ['admin', 'auditor'], 'Persona de Prueba', sesion.access_token]);
  });

  it('iniciar fallido → lanza ErrorApp y sigue anonima', async () => {
    api.login.mockRejectedValue(crearErrorApp('no_autenticado', 401));
    const error = await store
      .iniciar({ email: 'a@viamatica.test', password: 'x' })
      .catch((e: unknown) => e);
    expect([esErrorApp(error), store.estado()]).toEqual([true, 'anonima']);
  });

  it('restaurar con refresh correcto → autenticada', async () => {
    api.refrescar.mockResolvedValue(crearSesionPrueba());
    await store.restaurar();
    expect(store.estado()).toBe('autenticada');
  });

  it.each([
    ['401', crearErrorApp('no_autenticado', 401)],
    ['404', crearErrorApp('no_encontrado', 404)],
    ['timeout', new Error('Timeout has occurred')],
  ])('restaurar con %s → anonima', async (_caso, error) => {
    api.refrescar.mockRejectedValue(error);
    await store.restaurar();
    expect(store.estado()).toBe('anonima');
  });

  it('restaurar en curso → estado restaurando y esperarRestauracion resuelve al terminar', async () => {
    let resolver: (s: SesionOut) => void = () => undefined;
    api.refrescar.mockReturnValue(new Promise((r) => (resolver = r)));
    void store.restaurar();
    const durante = store.estado();
    const espera = store.esperarRestauracion();
    resolver(crearSesionPrueba());
    await espera;
    expect([durante, store.estado()]).toEqual(['restaurando', 'autenticada']);
  });

  it('esperarRestauracion sin restauración → resuelve inmediatamente', async () => {
    await expect(store.esperarRestauracion()).resolves.toBeUndefined();
  });

  it('refrescar concurrente → una sola llamada al API (single-flight)', async () => {
    api.refrescar.mockResolvedValue(crearSesionPrueba(['operador'], 'simulado.nuevo'));
    const tokens = await Promise.all([store.refrescar(), store.refrescar(), store.refrescar()]);
    expect([api.refrescar.mock.calls.length, tokens]).toEqual([
      1,
      ['simulado.nuevo', 'simulado.nuevo', 'simulado.nuevo'],
    ]);
  });

  it('refrescar tras terminar el anterior → nueva llamada', async () => {
    api.refrescar.mockResolvedValue(crearSesionPrueba());
    await store.refrescar();
    await store.refrescar();
    expect(api.refrescar).toHaveBeenCalledTimes(2);
  });

  it('cerrar con logout fallido → limpia igualmente y navega a /login', async () => {
    api.login.mockResolvedValue(crearSesionPrueba());
    api.cerrarSesion.mockRejectedValue(crearErrorApp('red', 0));
    await store.iniciar({ email: 'a@viamatica.test', password: 'x' });
    await store.cerrar();
    expect([
      store.estado(),
      store.tokenActual(),
      vi.mocked(TestBed.inject(Router).navigate).mock.calls[0],
    ]).toEqual(['anonima', null, [['/login']]]);
  });

  it('tieneAlgunRol → true si comparte algún rol', async () => {
    api.login.mockResolvedValue(crearSesionPrueba(['auditor']));
    await store.iniciar({ email: 'a@viamatica.test', password: 'x' });
    expect([store.tieneAlgunRol('admin', 'auditor'), store.tieneAlgunRol('admin')]).toEqual([
      true,
      false,
    ]);
  });

  it('login completo → ningún Storage.setItem, cookie ni consola recibe el token (CA6)', async () => {
    const sesion = crearSesionPrueba();
    const setItem = vi.spyOn(Storage.prototype, 'setItem');
    const consola = (['log', 'info', 'warn', 'error', 'debug'] as const).map((m) =>
      vi.spyOn(console, m),
    );
    api.login.mockResolvedValue(sesion);
    await store.iniciar({ email: 'a@viamatica.test', password: 'x' });
    const llamadas = JSON.stringify([
      ...setItem.mock.calls,
      ...consola.flatMap((c) => c.mock.calls),
    ]);
    expect([
      llamadas.includes(sesion.access_token),
      document.cookie.includes(sesion.access_token),
    ]).toEqual([false, false]);
  });
});
