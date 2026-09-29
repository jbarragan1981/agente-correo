import { expect, test } from '@playwright/test';

import { enviarLogin, simularSaludListo } from './ayudas';

test.describe('guards y redirecciones (CA10)', () => {
  test.beforeEach(async ({ page }) => {
    await simularSaludListo(page);
  });

  test('enlace profundo sin sesión → login → vuelve a la ruta', async ({ page }) => {
    await page.goto('/agentes');
    await expect(page).toHaveURL('/login?volver=%2Fagentes');
    await enviarLogin(page, 'operador');
    await expect(page).toHaveURL('/agentes');
  });

  for (const volver of [
    '//evil.test',
    'https://evil.test',
    '/\\evil.test',
    'javascript:alert(1)',
    '%2F%2Fevil.test',
  ]) {
    test(`volver externo ${volver} → /inicio`, async ({ page }) => {
      await page.goto(`/login?volver=${encodeURIComponent(volver)}`);
      await enviarLogin(page, 'operador');
      await expect(page).toHaveURL('/inicio');
    });
  }

  test('rol sin permiso → /sin-permiso', async ({ page }) => {
    await page.goto('/taxonomia');
    await enviarLogin(page, 'operador');
    await expect(page).toHaveURL('/sin-permiso');
    await expect(page.getByRole('heading', { name: 'Sin permiso' })).toBeVisible();
  });
});
