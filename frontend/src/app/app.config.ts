import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import {
  ApplicationConfig,
  DEFAULT_CURRENCY_CODE,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
  provideZonelessChangeDetection,
} from '@angular/core';
import {
  TitleStrategy,
  provideRouter,
  withComponentInputBinding,
  withViewTransitions,
} from '@angular/router';

import { provideApiConfiguration } from './core/api/generado/api-configuration';
import { authInterceptor } from './core/auth/auth.interceptor';
import { SesionStore } from './core/auth/sesion.store';
import { erroresInterceptor } from './core/errores/errores.interceptor';
import { correlacionInterceptor } from './core/http/correlacion.interceptor';
import { TituloStrategy } from './core/layout/titulo.strategy';
import { interceptoresEntorno, proveedoresEntorno } from '../environments/proveedores-entorno';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZonelessChangeDetection(),
    provideRouter(routes, withComponentInputBinding(), withViewTransitions()),
    provideHttpClient(
      withFetch(),
      // Orden: correlación → auth → errores → (API simulada, la más interna, solo en mocks/e2e).
      withInterceptors([
        correlacionInterceptor,
        authInterceptor,
        erroresInterceptor,
        ...interceptoresEntorno,
      ]),
    ),
    provideApiConfiguration(''),
    { provide: TitleStrategy, useClass: TituloStrategy },
    { provide: DEFAULT_CURRENCY_CODE, useValue: 'USD' },
    provideAppInitializer(() => inject(SesionStore).restaurar()),
    ...proveedoresEntorno,
  ],
};
