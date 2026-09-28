import { expect, test } from '@playwright/test';

import { enviarLogin, simularSaludListo, violacionesCsp, vigilarCsp } from './ayudas';

test.describe('CSP del panel (ADR-0012, CA16)', () => {
  test.beforeEach(async ({ page }) => {
    await vigilarCsp(page);
    await simularSaludListo(page);
  });

  test('cabeceras de seguridad presentes y connect-src self', async ({ request }) => {
    const respuesta = await request.get('/login');
    const cabeceras = respuesta.headers();
    expect(cabeceras['content-security-policy']).toContain("connect-src 'self';");
    expect(cabeceras['content-security-policy']).toMatch(/style-src 'self' 'nonce-[0-9a-f]{32}'/);
    expect(cabeceras['x-frame-options']).toBe('DENY');
    expect(cabeceras['x-content-type-options']).toBe('nosniff');
    expect(cabeceras['cache-control']).toBe('no-store');
  });

  test('el nonce cambia entre dos cargas de index.html y coincide con ngCspNonce', async ({
    request,
  }) => {
    const nonce = async (): Promise<[string, string]> => {
      const r = await request.get('/inicio');
      const cabecera =
        /'nonce-([0-9a-f]+)'/.exec(r.headers()['content-security-policy'] ?? '')?.[1] ?? '';
      const html = /ngCspNonce="([0-9a-f]+)"/i.exec(await r.text())?.[1] ?? '';
      return [cabecera, html];
    };
    const [a, htmlA] = await nonce();
    const [b] = await nonce();
    expect(a).not.toBe(b);
    expect(htmlA).toBe(a);
  });

  test('recursos con hash → caché inmutable', async ({ request, page }) => {
    await page.goto('/login');
    const script = await page.locator('script[src^="main-"]').getAttribute('src');
    const respuesta = await request.get(`/${script ?? ''}`);
    expect(respuesta.headers()['cache-control']).toBe('public, max-age=31536000, immutable');
  });

  test('0 violaciones y 0 errores de consola en login, inicio, ruta perezosa, sin permiso y 404', async ({
    page,
  }) => {
    const errores: string[] = [];
    const violaciones: string[] = [];
    const acumular = async (): Promise<void> => {
      violaciones.push(...(await violacionesCsp(page)));
    };
    page.on('console', (m) => {
      if (m.type() === 'error') errores.push(m.text());
    });
    page.on('pageerror', (e) => errores.push(e.message));

    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Iniciar sesión' })).toBeVisible();
    await enviarLogin(page, 'auditor');
    await expect(page.getByText('El sistema está listo.')).toBeVisible();
    await page.getByRole('navigation').getByRole('link', { name: 'Bandeja' }).click();
    await expect(page.getByRole('heading', { name: 'Bandeja' })).toBeVisible();
    await page.getByRole('button', { name: 'Menú de usuario' }).click();
    await expect(page.getByRole('menu')).toBeVisible();
    await page.keyboard.press('Escape');
    await page.getByRole('button', { name: 'Contraer menú lateral' }).click();
    await page.getByRole('navigation').getByRole('link', { name: 'Inicio' }).hover();
    await expect(page.locator('.mat-mdc-tooltip')).toHaveText('Inicio');
    await acumular();

    await page.goto('/usuarios');
    await enviarLogin(page, 'auditor');
    await expect(page.getByRole('heading', { name: 'Sin permiso' })).toBeVisible();
    await acumular();

    await page.goto('/ruta-que-no-existe');
    await enviarLogin(page, 'auditor');
    await expect(page.getByRole('heading', { name: 'Página no encontrada' })).toBeVisible();
    await acumular();

    expect(violaciones).toEqual([]);
    expect(errores).toEqual([]);
  });
});
