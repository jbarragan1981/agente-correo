import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { crearSesionPrueba } from '../../../../testing/ayudas-http';
import { EntradaMenu, VmShell } from './vm-shell';

@Component({ template: '' })
class Vacia {}

const MENU: EntradaMenu[] = [
  { ruta: 'inicio', etiqueta: 'Inicio', icono: 'home' },
  { ruta: 'bandeja', etiqueta: 'Bandeja', icono: 'inbox' },
];

describe('VmShell', () => {
  let fixture: ComponentFixture<VmShell>;
  let raiz: HTMLElement;

  async function crear(
    entradas: Partial<Record<'colapsado' | 'movil' | 'modoSimulado' | 'temaOscuro', boolean>> = {},
  ) {
    TestBed.configureTestingModule({
      imports: [VmShell],
      providers: [provideRouter([{ path: '**', component: Vacia }])],
    });
    fixture = TestBed.createComponent(VmShell);
    fixture.componentRef.setInput('navegacion', MENU);
    fixture.componentRef.setInput('usuario', crearSesionPrueba(['admin', 'auditor']).usuario);
    fixture.componentRef.setInput('colapsado', entradas.colapsado ?? false);
    for (const clave of ['movil', 'modoSimulado', 'temaOscuro'] as const) {
      if (entradas[clave] !== undefined) fixture.componentRef.setInput(clave, entradas[clave]);
    }
    await fixture.whenStable();
    raiz = fixture.nativeElement as HTMLElement;
  }

  function boton(etiqueta: string): HTMLButtonElement {
    const encontrado = [...raiz.querySelectorAll('button')].find(
      (b) => b.getAttribute('aria-label') === etiqueta || b.textContent?.trim() === etiqueta,
    );
    if (!encontrado) throw new Error(`No hay botón "${etiqueta}"`);
    return encontrado;
  }

  it('lista una entrada del menú por sección', async () => {
    await crear();
    expect([...raiz.querySelectorAll('.vm-nav-enlace')].map((a) => a.textContent?.trim())).toEqual([
      'homeInicio',
      'inboxBandeja',
    ]);
  });

  it('enlaces → apuntan a la ruta de la sección', async () => {
    await crear();
    expect(raiz.querySelector('.vm-nav-enlace')?.getAttribute('href')).toBe('/inicio');
  });

  it('colapsada → etiquetas solo para lectores de pantalla y clase de ancho reducido', async () => {
    await crear({ colapsado: true });
    const etiqueta = raiz.querySelector('.vm-nav-enlace span');
    expect([
      etiqueta?.classList.contains('vm-solo-lectores'),
      !!raiz.querySelector('.vm-sidebar-colapsada'),
    ]).toEqual([true, true]);
  });

  it('botón de colapso → emite alternarColapso', async () => {
    await crear();
    const emitido = vi.fn();
    fixture.componentInstance.alternarColapso.subscribe(emitido);
    boton('Contraer menú lateral').click();
    expect(emitido).toHaveBeenCalledOnce();
  });

  it('colapsada → el botón ofrece expandir con aria-expanded=false', async () => {
    await crear({ colapsado: true });
    expect(boton('Expandir menú lateral').getAttribute('aria-expanded')).toBe('false');
  });

  it('modo simulado → muestra el aviso', async () => {
    await crear({ modoSimulado: true });
    expect(raiz.querySelector('.vm-aviso-simulado')?.textContent).toContain('Modo simulado');
  });

  it('sin modo simulado → no muestra el aviso', async () => {
    await crear();
    expect(raiz.querySelector('.vm-aviso-simulado')).toBeNull();
  });

  it('móvil → botón de menú en el topbar y sin botón de colapso', async () => {
    await crear({ movil: true });
    expect([!!boton('Abrir menú de navegación'), raiz.querySelector('.vm-colapsar')]).toEqual([
      true,
      null,
    ]);
  });

  it('móvil → el botón de menú abre la sidebar', async () => {
    await crear({ movil: true });
    boton('Abrir menú de navegación').click();
    await fixture.whenStable();
    expect(boton('Abrir menú de navegación').getAttribute('aria-expanded')).toBe('true');
  });

  it('móvil → navegar cierra la sidebar', async () => {
    await crear({ movil: true });
    boton('Abrir menú de navegación').click();
    await fixture.whenStable();
    raiz.querySelector<HTMLAnchorElement>('.vm-nav-enlace')?.click();
    await fixture.whenStable();
    expect(boton('Abrir menú de navegación').getAttribute('aria-expanded')).toBe('false');
  });

  it('conmutador de tema → aria-pressed refleja el tema y emite alternarTema', async () => {
    await crear({ temaOscuro: true });
    const emitido = vi.fn();
    fixture.componentInstance.alternarTema.subscribe(emitido);
    const conmutador = boton('Tema oscuro');
    conmutador.click();
    expect([conmutador.getAttribute('aria-pressed'), emitido.mock.calls.length]).toEqual([
      'true',
      1,
    ]);
  });

  it('menú de usuario → muestra nombre y roles y emite cerrarSesion', async () => {
    await crear();
    const emitido = vi.fn();
    fixture.componentInstance.cerrarSesion.subscribe(emitido);
    boton('Menú de usuario').click();
    await fixture.whenStable();
    const panel = document.querySelector('.mat-mdc-menu-panel');
    const texto = panel?.textContent ?? '';
    [...(panel?.querySelectorAll('button') ?? [])]
      .find((b) => b.textContent?.includes('Cerrar sesión'))
      ?.click();
    expect([
      texto.includes('Persona de Prueba'),
      texto.includes('Administración, Auditoría'),
      emitido.mock.calls.length,
    ]).toEqual([true, true, 1]);
  });

  it('saltar al contenido → enfoca el main', async () => {
    await crear();
    boton('Saltar al contenido').click();
    expect(document.activeElement?.id).toBe('contenido-principal');
  });
});
