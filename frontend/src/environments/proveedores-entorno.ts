import { EnvironmentProviders, Provider } from '@angular/core';
import { HttpInterceptorFn } from '@angular/common/http';

/**
 * Proveedores de los builds `production` y `development`: sin API simulada.
 * Los builds `mocks` y `e2e` sustituyen este archivo por proveedores-entorno.mocks.ts (ADR-0013).
 */
export const interceptoresEntorno: HttpInterceptorFn[] = [];
export const proveedoresEntorno: (Provider | EnvironmentProviders)[] = [];
