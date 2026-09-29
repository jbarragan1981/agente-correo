import { ROLES, Rol } from '../auth/contrato-auth';

/** Sección del panel: única fuente de rutas, iconos, etiquetas y roles (menú y enrutador). */
export interface ItemNavegacion {
  readonly ruta: string;
  readonly etiqueta: string;
  readonly icono: string;
  readonly roles: readonly Rol[];
  /** Épica en la que se implementa la pantalla (se muestra en "En construcción"). */
  readonly epica: string;
}

const TODOS = ROLES;

/**
 * Roles provisionales alineados con docs/04-api.md; E0.3 los confirma. Los guards son solo de
 * experiencia de usuario: la autorización real la aplica el backend.
 */
export const SECCIONES: readonly ItemNavegacion[] = [
  {
    ruta: 'inicio',
    etiqueta: $localize`:@@nav.inicio:Inicio`,
    icono: 'home',
    roles: TODOS,
    epica: 'E0.4',
  },
  {
    ruta: 'dashboard',
    etiqueta: $localize`:@@nav.dashboard:Dashboard`,
    icono: 'insights',
    roles: TODOS,
    epica: 'E1.10',
  },
  {
    ruta: 'bandeja',
    etiqueta: $localize`:@@nav.bandeja:Bandeja`,
    icono: 'inbox',
    roles: TODOS,
    epica: 'E1.7',
  },
  {
    ruta: 'aprobaciones',
    etiqueta: $localize`:@@nav.aprobaciones:Aprobaciones`,
    icono: 'task_alt',
    roles: ['admin', 'operador'],
    epica: 'E1.7',
  },
  {
    ruta: 'agentes',
    etiqueta: $localize`:@@nav.agentes:Agentes`,
    icono: 'smart_toy',
    roles: TODOS,
    epica: 'E1.8',
  },
  {
    ruta: 'cuentas',
    etiqueta: $localize`:@@nav.cuentas:Cuentas de correo`,
    icono: 'alternate_email',
    roles: TODOS,
    epica: 'E1.9',
  },
  {
    ruta: 'taxonomia',
    etiqueta: $localize`:@@nav.taxonomia:Taxonomía`,
    icono: 'category',
    roles: ['admin'],
    epica: 'E1.9',
  },
  {
    ruta: 'webchat',
    etiqueta: $localize`:@@nav.webchat:Webchat`,
    icono: 'forum',
    roles: ['admin', 'operador'],
    epica: 'E1.11',
  },
  {
    ruta: 'proveedores',
    etiqueta: $localize`:@@nav.proveedores:Proveedores de IA`,
    icono: 'hub',
    roles: ['admin', 'auditor'],
    epica: 'E1.9',
  },
  {
    ruta: 'usuarios',
    etiqueta: $localize`:@@nav.usuarios:Usuarios`,
    icono: 'group',
    roles: ['admin'],
    epica: 'E1.9',
  },
  {
    ruta: 'auditoria',
    etiqueta: $localize`:@@nav.auditoria:Auditoría`,
    icono: 'policy',
    roles: ['admin', 'auditor'],
    epica: 'E1.10',
  },
];

/** Secciones visibles para un conjunto de roles. */
export function seccionesPara(roles: readonly Rol[]): ItemNavegacion[] {
  return SECCIONES.filter((s) => s.roles.some((rol) => roles.includes(rol)));
}

/** Busca una sección por su ruta. */
export function seccionPorRuta(ruta: string): ItemNavegacion | undefined {
  return SECCIONES.find((s) => s.ruta === ruta);
}
