import { InjectionToken } from '@angular/core';

/** `true` solo en los builds `mocks` y `e2e` (ADR-0013); el shell muestra el aviso "Modo simulado". */
export const MODO_SIMULADO = new InjectionToken<boolean>('MODO_SIMULADO', {
  providedIn: 'root',
  factory: () => false,
});
