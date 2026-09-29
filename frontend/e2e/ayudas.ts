import { Page, expect } from '@playwright/test';

/** Credenciales de la API simulada (build e2e); no existen en el backend real. */
export const CONTRASENA = 'prueba-panel-local';
export const USUARIOS = {
  admin: 'admin@viamatica.test',
  operador: 'operador@viamatica.test',
  auditor: 'auditor@viamatica.test',
} as const;

export type RolE2e = keyof typeof USUARIOS;

/** Responde /salud/listo como listo para que las pruebas sin backend no dependan de la API real. */
export async function simularSaludListo(page: Page): Promise<void> {
  await page.route('**/api/v1/salud/listo', (ruta) =>
    ruta.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '{"estado":"listo","comprobaciones":{"base_datos":"ok"}}',
    }),
  );
}

/** Rellena y envía el formulario de login de la página actual. */
export async function enviarLogin(page: Page, rol: RolE2e, contrasena = CONTRASENA): Promise<void> {
  await page.getByLabel('Correo electrónico').fill(USUARIOS[rol]);
  await page.getByLabel('Contraseña', { exact: true }).fill(contrasena);
  await page.getByRole('button', { name: 'Entrar' }).click();
}

/** Abre /login (o `destino`), inicia sesión y espera al shell. */
export async function iniciarSesion(page: Page, rol: RolE2e, destino = '/login'): Promise<void> {
  await page.goto(destino);
  await enviarLogin(page, rol);
  await expect(page.getByRole('navigation', { name: 'Navegación principal' })).toBeVisible();
}

/** Registra violaciones de CSP en la página (se leen con `violacionesCsp`). */
export async function vigilarCsp(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const registro: string[] = [];
    Object.defineProperty(window, '__violacionesCsp', { value: registro });
    document.addEventListener('securitypolicyviolation', (e) =>
      registro.push(`${e.violatedDirective} ${e.blockedURI}`),
    );
  });
}

export function violacionesCsp(page: Page): Promise<string[]> {
  return page.evaluate(
    () => (window as unknown as { __violacionesCsp: string[] }).__violacionesCsp,
  );
}
