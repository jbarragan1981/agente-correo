import { expect, test } from '@playwright/test';

import { iniciarSesion } from './ayudas';

/**
 * Contra el backend real (CA13). Sin base de datos, /salud/listo responde 503 `no_listo` y la
 * tarjeta muestra cada comprobación en falla sin detalles técnicos.
 */
test.describe('salud contra el backend real @backend', () => {
  test('/api/v1/salud llega al backend con sus propias cabeceras', async ({ request }) => {
    const respuesta = await request.get('/api/v1/salud');
    expect(respuesta.status()).toBe(200);
    expect(await respuesta.json()).toEqual({ estado: 'vivo' });
    expect(respuesta.headers()['content-security-policy']).not.toContain('nonce-');
  });

  test('inicio muestra el estado de /salud/listo', async ({ page }) => {
    await iniciarSesion(page, 'admin');
    const tarjeta = page.locator('mat-card');
    await expect(tarjeta.getByText(/El sistema (está|no está) listo\./)).toBeVisible();
    await expect(tarjeta.getByText('Base de datos')).toBeVisible();
    await expect(tarjeta).not.toContainText(/Traceback|Exception|psycopg|asyncpg|connection/i);
  });
});
