import { UsuarioSesion } from '../auth/contrato-auth';

/**
 * Usuarios de la API simulada (dominio reservado .test). Solo existen en los builds `mocks` y
 * `e2e`; el backend real no los conoce. Contraseña común de ejemplo, documentada en el README.
 */
export const CONTRASENA_SIMULADA = 'prueba-panel-local';

export const USUARIOS_SIMULADOS: readonly UsuarioSesion[] = [
  {
    id: '0192f0a0-0000-7000-8000-000000000001',
    email: 'admin@viamatica.test',
    nombre: 'Ana Admin',
    roles: ['admin'],
  },
  {
    id: '0192f0a0-0000-7000-8000-000000000002',
    email: 'operador@viamatica.test',
    nombre: 'Óscar Operador',
    roles: ['operador'],
  },
  {
    id: '0192f0a0-0000-7000-8000-000000000003',
    email: 'auditor@viamatica.test',
    nombre: 'Aurora Auditora',
    roles: ['auditor'],
  },
];
