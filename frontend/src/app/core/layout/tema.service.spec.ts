import { DOCUMENT } from '@angular/core';
import { TestBed } from '@angular/core/testing';

import { AlmacenMemoria } from '../../../testing/almacen-memoria';
import { ALMACEN_PREFERENCIAS, CLAVE_TEMA } from './preferencias-ui';
import { TemaService } from './tema.service';

describe('TemaService', () => {
  let almacen: AlmacenMemoria;

  beforeEach(() => {
    almacen = new AlmacenMemoria();
    TestBed.configureTestingModule({
      providers: [{ provide: ALMACEN_PREFERENCIAS, useValue: almacen }],
    });
  });

  afterEach(() => {
    delete TestBed.inject(DOCUMENT).documentElement.dataset['tema'];
    vi.unstubAllGlobals();
  });

  it('sin preferencia y sistema claro → tema claro aplicado a <html>', () => {
    const tema = TestBed.inject(TemaService);
    TestBed.tick();
    expect([tema.tema(), TestBed.inject(DOCUMENT).documentElement.dataset['tema']]).toEqual([
      'claro',
      'claro',
    ]);
  });

  it('sistema oscuro → tema oscuro', () => {
    vi.stubGlobal('matchMedia', (consulta: string) => ({ matches: consulta.includes('dark') }));
    expect(TestBed.inject(TemaService).tema()).toBe('oscuro');
  });

  it('preferencia guardada → prevalece sobre el sistema', () => {
    almacen.setItem(CLAVE_TEMA, 'oscuro');
    expect(TestBed.inject(TemaService).tema()).toBe('oscuro');
  });

  it('alternar → cambia el tema, lo persiste y actualiza data-tema', () => {
    const tema = TestBed.inject(TemaService);
    tema.alternar();
    TestBed.tick();
    expect([
      tema.tema(),
      almacen.getItem(CLAVE_TEMA),
      TestBed.inject(DOCUMENT).documentElement.dataset['tema'],
    ]).toEqual(['oscuro', 'oscuro', 'oscuro']);
  });

  it('alternar dos veces → vuelve a claro', () => {
    const tema = TestBed.inject(TemaService);
    tema.alternar();
    tema.alternar();
    expect(tema.tema()).toBe('claro');
  });
});
