import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { App } from './app';

describe('App', () => {
  it('se crea con el enrutador → contiene router-outlet', async () => {
    TestBed.configureTestingModule({ imports: [App], providers: [provideRouter([])] });
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const raiz = fixture.nativeElement as HTMLElement;
    expect(raiz.querySelector('router-outlet')).not.toBeNull();
  });

  it('BUG-05: crear la raíz aplica data-tema al documento (también sin shell, p. ej. /login)', async () => {
    delete document.documentElement.dataset['tema'];
    TestBed.configureTestingModule({ imports: [App], providers: [provideRouter([])] });
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    expect(['claro', 'oscuro']).toContain(document.documentElement.dataset['tema']);
  });
});
