import { expect, test } from '@playwright/test';

import { enviarLogin, iniciarSesion, simularSaludListo } from './ayudas';

test.describe('shell (CA12)', () => {
  test.beforeEach(async ({ page }) => {
    await simularSaludListo(page);
  });

  test('colapsar la sidebar → 72 px y preferencia persistida', async ({ page }) => {
    await iniciarSesion(page, 'admin');
    const sidebar = page.locator('mat-sidenav');
    await expect(sidebar).toHaveCSS('width', '256px');
    await page.getByRole('button', { name: 'Contraer menú lateral' }).click();
    await expect(sidebar).toHaveCSS('width', '72px');
    expect(await page.evaluate(() => localStorage.getItem('vm.sidebar.colapsado'))).toBe('true');
  });

  test('aviso "Modo simulado" visible en el build e2e', async ({ page }) => {
    await iniciarSesion(page, 'auditor');
    await expect(page.getByRole('status').filter({ hasText: 'Modo simulado' })).toBeVisible();
  });

  test('ancho < 1024 px → menú en modo over con botón en el topbar', async ({ page }) => {
    await page.setViewportSize({ width: 800, height: 900 });
    // En móvil la navegación está dentro del drawer cerrado: se espera a la URL y al botón de menú.
    await page.goto('/login');
    await enviarLogin(page, 'admin');
    await expect(page).toHaveURL('/inicio');
    const boton = page.getByRole('button', { name: 'Abrir menú de navegación' });
    await expect(boton).toHaveAttribute('aria-expanded', 'false');
    await boton.click();
    await expect(boton).toHaveAttribute('aria-expanded', 'true');
    await page.getByRole('navigation').getByRole('link', { name: 'Bandeja' }).click();
    await expect(page).toHaveURL('/bandeja');
    await expect(boton).toHaveAttribute('aria-expanded', 'false');
  });

  test('saltar al contenido es el primer elemento enfocable', async ({ page }) => {
    await iniciarSesion(page, 'operador');
    await page.keyboard.press('Tab');
    await expect(page.getByRole('button', { name: 'Saltar al contenido' })).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.locator('#contenido-principal')).toBeFocused();
  });
});
