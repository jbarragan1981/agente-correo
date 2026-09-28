import { Injectable, InjectionToken, inject } from '@angular/core';

export type Tema = 'claro' | 'oscuro';

/** Claves de preferencias de interfaz. Nunca contienen datos de sesión. */
export const CLAVE_SIDEBAR = 'vm.sidebar.colapsado';
export const CLAVE_TEMA = 'vm.tema';

/** Almacenamiento de preferencias; en pruebas se sustituye por uno en memoria. */
export const ALMACEN_PREFERENCIAS = new InjectionToken<Storage | null>('ALMACEN_PREFERENCIAS', {
  providedIn: 'root',
  factory: () => {
    try {
      return globalThis.localStorage ?? null;
    } catch {
      return null;
    }
  },
});

/** Lee y escribe preferencias de UI; tolera almacenamiento no disponible (modo privado, cuotas). */
@Injectable({ providedIn: 'root' })
export class PreferenciasUi {
  private readonly almacen = inject(ALMACEN_PREFERENCIAS);

  sidebarColapsada(): boolean {
    return this.leer(CLAVE_SIDEBAR) === 'true';
  }

  guardarSidebarColapsada(colapsada: boolean): void {
    this.escribir(CLAVE_SIDEBAR, String(colapsada));
  }

  tema(): Tema | null {
    const valor = this.leer(CLAVE_TEMA);
    return valor === 'claro' || valor === 'oscuro' ? valor : null;
  }

  guardarTema(tema: Tema): void {
    this.escribir(CLAVE_TEMA, tema);
  }

  private leer(clave: string): string | null {
    try {
      return this.almacen?.getItem(clave) ?? null;
    } catch {
      return null;
    }
  }

  private escribir(clave: string, valor: string): void {
    try {
      this.almacen?.setItem(clave, valor);
    } catch {
      // Sin almacenamiento disponible: la preferencia dura lo que la pestaña.
    }
  }
}
