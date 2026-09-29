import { EnvironmentProviders, Provider } from '@angular/core';
import { HttpInterceptorFn } from '@angular/common/http';

import { apiSimuladaInterceptor } from '../app/core/mocks/api-simulada.interceptor';
import { MODO_SIMULADO } from '../app/core/mocks/modo-simulado';

/** Proveedores de los builds `mocks` y `e2e`: API simulada de autenticación (ADR-0013). */
export const interceptoresEntorno: HttpInterceptorFn[] = [apiSimuladaInterceptor];
export const proveedoresEntorno: (Provider | EnvironmentProviders)[] = [
  { provide: MODO_SIMULADO, useValue: true },
];
