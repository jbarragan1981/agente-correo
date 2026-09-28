import { expect, test } from '@playwright/test';

import { USUARIOS, enviarLogin, iniciarSesion, simularSaludListo } from './ayudas';

const MENU_ESPERADO = {
  admin: 11,
  operador: 7,
  auditor: 7,
} as const;

test.describe('login con API simulada (CA6, CA11)', () => {
  test.beforeEach(async ({ page }) => {
    await simularSaludListo(page);
  });

  for (const rol of Object.keys(USUARIOS) as (keyof typeof USUARIOS)[]) {
    test(`login de ${rol} → menú con sus secciones`, async ({ page }) => {
      await iniciarSesion(page, rol);
      await expect(page).toHaveURL('/inicio');
      await expect(
        page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('link'),
      ).toHaveCount(MENU_ESPERADO[rol]);
    });
  }

  test('credenciales erróneas → mensaje genérico y contraseña vacía', async ({ page }) => {
    await page.goto('/login');
    await enviarLogin(page, 'admin', 'contraseña-incorrecta');
    await expect(page.getByRole('alert')).toHaveText('Correo o contraseña incorrectos.');
    await expect(page.getByLabel('Contraseña', { exact: true })).toHaveValue('');
  });

  test('cinco fallos seguidos → 429 con los segundos de espera', async ({ page }) => {
    await page.goto('/login');
    for (let i = 0; i < 5; i++) {
      await enviarLogin(page, 'operador', `mal-${i}`);
      // La contraseña se vacía al recibir la respuesta: así cada intento espera al anterior.
      await expect(page.getByLabel('Contraseña', { exact: true })).toHaveValue('');
      await expect(page.getByRole('alert')).toHaveText('Correo o contraseña incorrectos.');
    }
    await enviarLogin(page, 'operador');
    await expect(page.getByRole('alert')).toHaveText(
      'Demasiados intentos. Inténtalo de nuevo en 60 s.',
    );
  });

  test('validación en español bajo cada campo', async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('button', { name: 'Entrar' }).click();
    await expect(page.getByText('Escribe tu correo electrónico.')).toBeVisible();
    await expect(page.getByText('Escribe tu contraseña.')).toBeVisible();
  });

  test('el token no está en localStorage, sessionStorage, cookies ni la URL', async ({ page }) => {
    // La API simulada emite tokens opacos con prefijo "simulado." (no viajan por la red).
    await iniciarSesion(page, 'admin');
    const almacenado = await page.evaluate(() =>
      JSON.stringify([{ ...localStorage }, { ...sessionStorage }, document.cookie, location.href]),
    );
    const cookies = JSON.stringify(await page.context().cookies());
    expect(`${almacenado}${cookies}`).not.toContain('simulado.');
  });

  test('recargar con sesión → vuelve a /login (sin refresh real)', async ({ page }) => {
    await iniciarSesion(page, 'admin');
    await page.reload();
    await expect(page).toHaveURL(/\/login/);
  });

  test('cerrar sesión → /login', async ({ page }) => {
    await iniciarSesion(page, 'operador');
    await page.getByRole('button', { name: 'Menú de usuario' }).click();
    await page.getByRole('menuitem', { name: 'Cerrar sesión' }).click();
    await expect(page).toHaveURL('/login');
  });
});
