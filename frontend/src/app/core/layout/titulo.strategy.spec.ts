import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Title } from '@angular/platform-browser';
import { TitleStrategy, provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';

import { TituloStrategy } from './titulo.strategy';

@Component({ template: '' })
class Vacia {}

describe('TituloStrategy', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([
          { path: 'con', title: 'Bandeja', component: Vacia },
          { path: 'sin', component: Vacia },
        ]),
        { provide: TitleStrategy, useClass: TituloStrategy },
      ],
    });
  });

  it('ruta con título → "<título> · Agente Correo"', async () => {
    await (await RouterTestingHarness.create()).navigateByUrl('/con');
    expect(TestBed.inject(Title).getTitle()).toBe('Bandeja · Agente Correo');
  });

  it('ruta sin título → "Agente Correo"', async () => {
    await (await RouterTestingHarness.create()).navigateByUrl('/sin');
    expect(TestBed.inject(Title).getTitle()).toBe('Agente Correo');
  });
});
