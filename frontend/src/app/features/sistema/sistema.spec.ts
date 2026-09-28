import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { EnConstruccionPage } from './en-construccion.page';
import { NoEncontradoPage } from './no-encontrado.page';
import { SinPermisoPage } from './sin-permiso.page';

describe('páginas de sistema', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
  });

  it('sin permiso → título y enlace a inicio', async () => {
    const fixture = TestBed.createComponent(SinPermisoPage);
    await fixture.whenStable();
    const raiz = fixture.nativeElement as HTMLElement;
    expect([
      raiz.querySelector('h1')?.textContent?.trim(),
      raiz.querySelector('a')?.getAttribute('href'),
    ]).toEqual(['Sin permiso', '/inicio']);
  });

  it('no encontrado → título de 404', async () => {
    const fixture = TestBed.createComponent(NoEncontradoPage);
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).querySelector('h1')?.textContent?.trim()).toBe(
      'Página no encontrada',
    );
  });

  it('en construcción → nombre de la sección y épica prevista', async () => {
    const fixture = TestBed.createComponent(EnConstruccionPage);
    fixture.componentRef.setInput('seccion', 'bandeja');
    await fixture.whenStable();
    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect([texto.includes('Bandeja'), texto.includes('E1.7')]).toEqual([true, true]);
  });
});
