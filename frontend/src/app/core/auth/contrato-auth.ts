/**
 * Contrato PROVISIONAL de autenticación (ADR-0013 §4). Se sustituye por los modelos generados
 * desde OpenAPI cuando E0.3 publique los endpoints; es la forma que se propone a E0.3
 * (alineada con docs/04-api.md §1).
 *
 * POST /api/v1/auth/login   → SesionOut + cookie refresh (httpOnly, Secure, SameSite=Strict, Path=/api/v1/auth)
 * POST /api/v1/auth/refresh → SesionOut (sin body; usa la cookie)
 * POST /api/v1/auth/logout  → 204
 * GET  /api/v1/auth/me      → UsuarioSesion
 */
export type Rol = 'admin' | 'operador' | 'auditor';

export const ROLES: readonly Rol[] = ['admin', 'operador', 'auditor'];

export interface LoginIn {
  email: string;
  password: string;
}

export interface UsuarioSesion {
  id: string;
  email: string;
  nombre: string;
  roles: Rol[];
}

export interface SesionOut {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
  usuario: UsuarioSesion;
}

export const RUTAS_AUTH = {
  login: '/api/v1/auth/login',
  refresh: '/api/v1/auth/refresh',
  logout: '/api/v1/auth/logout',
  yo: '/api/v1/auth/me',
} as const;
