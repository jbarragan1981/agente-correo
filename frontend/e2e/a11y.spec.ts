import AxeBuilder from '@axe-core/playwright';
import { Page, expect, test } from '@playwright/test';

import { enviarLogin, iniciarSesion, simularSaludListo } from './ayudas';

async function sinViolacionesGraves(page: Page): Promise<void> {
  const resultado = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  const graves = resultado.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`);
  expect(graves).toEqual([]);
}

for (const tema of ['claro', 'oscuro'] as const) {
  test.describe(`accesibilidad en tema ${tema} (CA19)`, () => {
    test.beforeEach(async ({ page }) => {
      await simularSaludListo(page);
      await page.addInitScript((t) => localStorage.setItem('vm.tema', t), tema);
    });

    test('/login sin violaciones serias ni críticas', async ({ page }) => {
      await page.goto('/login');
      await expect(page.getByRole('heading', { name: 'Iniciar sesión' })).toBeVisible();
      await sinViolacionesGraves(page);
    });

    test('/inicio sin violaciones serias ni críticas', async ({ page }) => {
      await iniciarSesion(page, 'admin');
      await expect(page.getByText('El sistema está listo.')).toBeVisible();
      await sinViolacionesGraves(page);
    });

    test('/sin-permiso sin violaciones serias ni críticas', async ({ page }) => {
      await page.goto('/usuarios');
      await enviarLogin(page, 'auditor');
      await expect(page.getByRole('heading', { name: 'Sin permiso' })).toBeVisible();
      await sinViolacionesGraves(page);
    });
  });
}

test('teclado: Tab recorre el shell con foco visible y Escape cierra el menú de usuario', async ({
  page,
}) => {
  await simularSaludListo(page);
  await iniciarSesion(page, 'admin');
  const enfocados: string[] = [];
  for (let i = 0; i < 6; i++) {
    await page.keyboard.press('Tab');
    const info = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      const estilo = el ? getComputedStyle(el) : null;
      return `${el?.getAttribute('aria-label') ?? el?.textContent?.trim() ?? ''}|${estilo?.outlineStyle ?? ''}`;
    });
    enfocados.push(info);
  }
  expect(enfocados.filter((e) => e.endsWith('|none'))).toEqual([]);
  await page.getByRole('button', { name: 'Menú de usuario' }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('menu')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('menu')).toBeHidden();
  await expect(page.getByRole('button', { name: 'Menú de usuario' })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(page.getByRole('button', { name: 'Tema oscuro' })).toBeFocused();
});
