import { Rol } from './contrato-auth';

/** Nombre visible de cada rol. */
export function etiquetaRol(rol: Rol): string {
  switch (rol) {
    case 'admin':
      return $localize`:@@rol.admin:Administración`;
    case 'operador':
      return $localize`:@@rol.operador:Operación`;
    case 'auditor':
      return $localize`:@@rol.auditor:Auditoría`;
  }
}
