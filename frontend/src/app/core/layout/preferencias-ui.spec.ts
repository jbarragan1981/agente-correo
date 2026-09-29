import { TestBed } from '@angular/core/testing';

import { AlmacenMemoria } from '../../../testing/almacen-memoria';
import { ALMACEN_PREFERENCIAS, CLAVE_SIDEBAR, CLAVE_TEMA, PreferenciasUi } from './preferencias-ui';

describe('PreferenciasUi', () => {
  function crear(almacen: Storage | null): PreferenciasUi {
    TestBed.configureTestingModule({
      providers: [{ provide: ALMACEN_PREFERENCIAS, useValue: almacen }],
    });
    return TestBed.inject(PreferenciasUi);
  }

  it('sin valor guardado → sidebar expandida y sin tema', () => {
    const prefs = crear(new AlmacenMemoria());
    expect([prefs.sidebarColapsada(), prefs.tema()]).toEqual([false, null]);
  });

  it('guardar sidebar colapsada → se persiste en vm.sidebar.colapsado', () => {
    const almacen = new AlmacenMemoria();
    crear(almacen).guardarSidebarColapsada(true);
    expect(almacen.getItem(CLAVE_SIDEBAR)).toBe('true');
  });

  it('guardar tema → se lee de vuelta', () => {
    const prefs = crear(new AlmacenMemoria());
    prefs.guardarTema('oscuro');
    expect(prefs.tema()).toBe('oscuro');
  });

  it('tema con valor inválido → null', () => {
    const almacen = new AlmacenMemoria();
    almacen.setItem(CLAVE_TEMA, 'fucsia');
    expect(crear(almacen).tema()).toBeNull();
  });

  it('almacenamiento que lanza → no rompe', () => {
    const almacen = new AlmacenMemoria();
    vi.spyOn(almacen, 'getItem').mockImplementation(() => {
      throw new Error('bloqueado');
    });
    vi.spyOn(almacen, 'setItem').mockImplementation(() => {
      throw new Error('cuota');
    });
    const prefs = crear(almacen);
    prefs.guardarSidebarColapsada(true);
    expect(prefs.sidebarColapsada()).toBe(false);
  });

  it('sin almacenamiento → valores por defecto', () => {
    const prefs = crear(null);
    prefs.guardarTema('claro');
    expect(prefs.tema()).toBeNull();
  });

  it('proveedor por defecto → usa localStorage del navegador', () => {
    expect(TestBed.inject(ALMACEN_PREFERENCIAS)).toBe(globalThis.localStorage);
  });
});
