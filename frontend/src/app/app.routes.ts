import { Routes } from '@angular/router';

import { autenticadoGuard, invitadoGuard, rolGuard } from './core/auth/guards';
import { SECCIONES } from './core/layout/navegacion';

const seccionesEnConstruccion: Routes = SECCIONES.filter((s) => s.ruta !== 'inicio').map((s) => ({
  path: s.ruta,
  title: s.etiqueta,
  canMatch: [rolGuard(...s.roles)],
  data: { seccion: s.ruta },
  loadComponent: () =>
    import('./features/sistema/en-construccion.page').then((m) => m.EnConstruccionPage),
}));

const inicio = SECCIONES.find((s) => s.ruta === 'inicio');

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'inicio' },
  {
    path: 'login',
    title: $localize`:@@titulo.login:Iniciar sesión`,
    canMatch: [invitadoGuard],
    loadComponent: () => import('./features/login/login.page').then((m) => m.LoginPage),
  },
  {
    path: '',
    canMatch: [autenticadoGuard],
    loadComponent: () => import('./core/layout/layout-principal').then((m) => m.LayoutPrincipal),
    children: [
      {
        path: 'inicio',
        title: inicio?.etiqueta ?? '',
        canMatch: [rolGuard(...(inicio?.roles ?? []))],
        loadComponent: () => import('./features/inicio/inicio.page').then((m) => m.InicioPage),
      },
      {
        path: 'sin-permiso',
        title: $localize`:@@titulo.sin_permiso:Sin permiso`,
        loadComponent: () =>
          import('./features/sistema/sin-permiso.page').then((m) => m.SinPermisoPage),
      },
      ...seccionesEnConstruccion,
    ],
  },
  {
    path: '**',
    title: $localize`:@@titulo.no_encontrado:Página no encontrada`,
    loadComponent: () =>
      import('./features/sistema/no-encontrado.page').then((m) => m.NoEncontradoPage),
  },
];
