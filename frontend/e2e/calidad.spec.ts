import { expect, test } from '@playwright/test';

import { enviarLogin, iniciarSesion, simularSaludListo, USUARIOS } from './ayudas';

/** Verificaciones de QA de E0.4: viewport móvil, tema, trazabilidad, consola, errores de salud y sesión. */
const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

async function desbordeHorizontal(page: import('@playwright/test').Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
}

test.describe('viewport móvil de 360 px (BUG-04)', () => {
  test.use({ viewport: { width: 360, height: 740 } });

  test('/login sin scroll horizontal', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Iniciar sesión' })).toBeVisible();
    expect(await desbordeHorizontal(page)).toBeLessThanOrEqual(0);
  });

  for (const rol of ['admin', 'auditor'] as const) {
    test(`/inicio de ${rol} sin scroll horizontal y con el menú de usuario visible`, async ({
      page,
    }) => {
      await simularSaludListo(page);
      await page.goto('/login');
      await enviarLogin(page, rol);
      await expect(page.getByText('El sistema está listo.')).toBeVisible();
      const caja = await page.getByRole('button', { name: 'Menú de usuario' }).boundingBox();
      expect([await desbordeHorizontal(page), (caja?.x ?? 0) + (caja?.width ?? 0) <= 360]).toEqual([
        0,
        true,
      ]);
    });
  }

  test('/sin-permiso sin scroll horizontal', async ({ page }) => {
    await simularSaludListo(page);
    await page.goto('/usuarios');
    await enviarLogin(page, 'auditor');
    await expect(page.getByRole('heading', { name: 'Sin permiso' })).toBeVisible();
    expect(await desbordeHorizontal(page)).toBeLessThanOrEqual(0);
  });

  test('menú lateral en móvil: se abre, Escape lo cierra y el foco vuelve al botón', async ({
    page,
  }) => {
    await simularSaludListo(page);
    await page.goto('/login');
    await enviarLogin(page, 'admin');
    const boton = page.getByRole('button', { name: 'Abrir menú de navegación' });
    await boton.click();
    await expect(boton).toHaveAttribute('aria-expanded', 'true');
    // Escape solo actúa con el foco dentro del panel: se espera a que Material lo mueva allí.
    await expect(page.locator('mat-sidenav').getByRole('link').first()).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(boton).toHaveAttribute('aria-expanded', 'false');
    await expect(boton).toBeFocused();
  });
});

test.describe('tema claro y oscuro persistido', () => {
  test.beforeEach(async ({ page }) => {
    await simularSaludListo(page);
  });

  test('conmutar → data-tema, localStorage vm.tema y se conserva tras recargar (también en /login)', async ({
    page,
  }) => {
    await iniciarSesion(page, 'operador');
    await page.getByRole('button', { name: 'Tema oscuro' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-tema', 'oscuro');
    const antes = await page.evaluate(() => [
      document.documentElement.dataset['tema'],
      localStorage.getItem('vm.tema'),
    ]);
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Iniciar sesión' })).toBeVisible();
    const despues = await page.evaluate(() => document.documentElement.dataset['tema']);
    expect([antes, despues]).toEqual([['oscuro', 'oscuro'], 'oscuro']);
  });

  test('sin preferencia y prefers-color-scheme oscuro → tema oscuro', async ({ browser }) => {
    const contexto = await browser.newContext({ colorScheme: 'dark' });
    const page = await contexto.newPage();
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Iniciar sesión' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.dataset['tema'])).toBe('oscuro');
    await contexto.close();
  });

  test('preferencia guardada gana a prefers-color-scheme', async ({ browser }) => {
    const contexto = await browser.newContext({ colorScheme: 'dark' });
    await contexto.addInitScript(() => localStorage.setItem('vm.tema', 'claro'));
    const page = await contexto.newPage();
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Iniciar sesión' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.dataset['tema'])).toBe('claro');
    await contexto.close();
  });

  test('valor corrupto en vm.tema → tema del sistema y sin errores', async ({ browser }) => {
    const contexto = await browser.newContext({ colorScheme: 'light' });
    await contexto.addInitScript(() => localStorage.setItem('vm.tema', '"><script>x</script>'));
    const page = await contexto.newPage();
    const errores: string[] = [];
    page.on('pageerror', (e) => errores.push(e.message));
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Iniciar sesión' })).toBeVisible();
    expect([await page.evaluate(() => document.documentElement.dataset['tema']), errores]).toEqual([
      'claro',
      [],
    ]);
    await contexto.close();
  });
});

test.describe('trazabilidad, almacenamiento y consola', () => {
  test('cada petición a /api/ lleva un X-Request-ID UUID v4 distinto', async ({ page }) => {
    // El login simulado no sale a la red; se observan las peticiones reales de la tarjeta de salud.
    await page.route('**/api/v1/salud/listo', (ruta) =>
      ruta.fulfill({
        status: 503,
        contentType: 'application/problem+json',
        body: JSON.stringify({
          type: 'no_listo',
          title: 'No listo',
          status: 503,
          instance: 'urn:uuid:3f2b8c1e-6d4a-4f7e-9a51-2b0c8d7e6f10',
          comprobaciones: { base_datos: 'falla' },
        }),
      }),
    );
    const ids: (string | undefined)[] = [];
    page.on('request', (r) => {
      if (new URL(r.url()).pathname.startsWith('/api/')) ids.push(r.headers()['x-request-id']);
    });
    await iniciarSesion(page, 'admin');
    for (let i = 0; i < 2; i++) {
      await expect(page.getByRole('button', { name: 'Reintentar' })).toBeVisible();
      await page.getByRole('button', { name: 'Reintentar' }).click();
      await expect.poll(() => ids.length).toBe(i + 2);
    }
    expect([ids.every((id) => UUID_V4.test(id ?? '')), new Set(ids).size]).toEqual([true, 3]);
  });

  test('ninguna petición lleva el token en la URL y el almacenamiento solo tiene claves vm.*', async ({
    page,
  }) => {
    await simularSaludListo(page);
    const urls: string[] = [];
    page.on('request', (r) => urls.push(r.url()));
    await iniciarSesion(page, 'admin');
    await page.getByRole('navigation').getByRole('link', { name: 'Bandeja' }).click();
    await expect(page).toHaveURL('/bandeja');
    const almacenes = await page.evaluate(() => ({
      local: Object.keys(localStorage),
      sesion: Object.keys(sessionStorage),
      cookie: document.cookie,
      databases: 'databases' in indexedDB ? indexedDB.databases().then((d) => d.length) : 0,
    }));
    expect([
      urls.filter((u) => u.includes('simulado')),
      almacenes.local.filter((k) => !k.startsWith('vm.')),
      almacenes.sesion,
      almacenes.cookie,
    ]).toEqual([[], [], [], '']);
  });

  test('flujo completo de login y logout → 0 mensajes de consola', async ({ page }) => {
    await simularSaludListo(page);
    const consola: string[] = [];
    page.on('console', (m) => consola.push(`${m.type()}: ${m.text()}`));
    page.on('pageerror', (e) => consola.push(`pageerror: ${e.message}`));
    await iniciarSesion(page, 'admin');
    await page.getByRole('button', { name: 'Menú de usuario' }).click();
    await page.getByRole('menuitem', { name: 'Cerrar sesión' }).click();
    await expect(page).toHaveURL('/login');
    expect(consola).toEqual([]);
  });

  test('cerrar sesión y volver atrás → no se muestra el shell ni datos', async ({ page }) => {
    await simularSaludListo(page);
    await iniciarSesion(page, 'admin');
    await page.getByRole('button', { name: 'Menú de usuario' }).click();
    await page.getByRole('menuitem', { name: 'Cerrar sesión' }).click();
    await expect(page).toHaveURL('/login');
    await page.goBack();
    await expect(page.getByRole('heading', { name: 'Iniciar sesión' })).toBeVisible();
    await expect(page.getByRole('navigation', { name: 'Navegación principal' })).toHaveCount(0);
  });
});

test.describe('login con entradas hostiles', () => {
  test('correo con HTML y comillas → validación en línea y sin ejecución de script', async ({
    page,
  }) => {
    await page.goto('/login');
    await page.getByLabel('Correo electrónico').fill('"><img src=x onerror=window.__xss=1>@x.test');
    await page.getByLabel('Contraseña', { exact: true }).fill("' OR '1'='1");
    await page.getByRole('button', { name: 'Entrar' }).click();
    await expect(page.getByText('Escribe un correo electrónico válido.')).toBeVisible();
    expect(await page.evaluate(() => (window as unknown as { __xss?: number }).__xss)).toBe(
      undefined,
    );
  });

  test('contraseña con acentos, emoji y 5 000 caracteres → mensaje genérico y campo vacío', async ({
    page,
  }) => {
    await page.goto('/login');
    await page.getByLabel('Correo electrónico').fill(USUARIOS.admin);
    await page.getByLabel('Contraseña', { exact: true }).fill(`ñandú-🔑-${'x'.repeat(5000)}`);
    await page.getByRole('button', { name: 'Entrar' }).click();
    await expect(page.getByRole('alert')).toHaveText('Correo o contraseña incorrectos.');
    await expect(page.getByLabel('Contraseña', { exact: true })).toHaveValue('');
  });

  test('doble Enter seguido → cuenta un único intento fallido', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Correo electrónico').fill(USUARIOS.operador);
    const clave = page.getByLabel('Contraseña', { exact: true });
    await clave.fill('mal');
    await page.keyboard.press('Enter');
    await page.keyboard.press('Enter');
    await expect(page.getByRole('alert')).toHaveText('Correo o contraseña incorrectos.');
    // Con un intento por Enter hay 4 fallos y el éxito entra; si el doble Enter contara dos, serían 5 y daría 429.
    for (let i = 0; i < 3; i++) {
      await clave.fill(`mal-${i}`);
      await page.keyboard.press('Enter');
      await expect(clave).toHaveValue('');
    }
    await clave.fill('prueba-panel-local');
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL('/inicio');
  });
});

test.describe('tarjeta de salud con errores de API', () => {
  test('500 problem+json → mensaje del catálogo sin detalles técnicos y botón Reintentar', async ({
    page,
  }) => {
    await page.route('**/api/v1/salud/listo', (ruta) =>
      ruta.fulfill({
        status: 500,
        contentType: 'application/problem+json',
        body: JSON.stringify({
          type: 'error_interno',
          title: 'Error',
          status: 500,
          detail: 'Traceback (most recent call last): psycopg.OperationalError host=db',
          instance: 'urn:uuid:3f2b8c1e-6d4a-4f7e-9a51-2b0c8d7e6f10',
        }),
      }),
    );
    await iniciarSesion(page, 'admin');
    await expect(page.getByRole('button', { name: 'Reintentar' })).toBeVisible();
    await expect(page.locator('body')).not.toContainText(/Traceback|psycopg|host=db/);
  });

  test('502 HTML del proxy → no se muestra el cuerpo', async ({ page }) => {
    await page.route('**/api/v1/salud/listo', (ruta) =>
      ruta.fulfill({
        status: 502,
        contentType: 'text/html',
        body: '<html><body><h1>502 Bad Gateway</h1>nginx/1.27.0</body></html>',
      }),
    );
    await iniciarSesion(page, 'admin');
    await expect(page.getByRole('button', { name: 'Reintentar' })).toBeVisible();
    await expect(page.locator('body')).not.toContainText(/nginx|Bad Gateway/);
  });

  test('red caída → "Reintentar" y, al volver la red, el estado listo', async ({ page }) => {
    let caida = true;
    await page.route('**/api/v1/salud/listo', (ruta) =>
      caida
        ? ruta.abort('connectionrefused')
        : ruta.fulfill({
            status: 200,
            contentType: 'application/json',
            body: '{"estado":"listo","comprobaciones":{"base_datos":"ok"}}',
          }),
    );
    await iniciarSesion(page, 'admin');
    await expect(page.getByText('No se pudo contactar con el servidor.').first()).toBeVisible();
    caida = false;
    await page.getByRole('button', { name: 'Reintentar' }).click();
    await expect(page.getByText('El sistema está listo.')).toBeVisible();
  });

  test('503 no_listo → cada comprobación en falla, sin detalle técnico', async ({ page }) => {
    await page.route('**/api/v1/salud/listo', (ruta) =>
      ruta.fulfill({
        status: 503,
        contentType: 'application/problem+json',
        body: JSON.stringify({
          type: 'no_listo',
          title: 'No listo',
          status: 503,
          detail: 'connection to server at "db" (10.0.0.5) failed',
          instance: 'urn:uuid:3f2b8c1e-6d4a-4f7e-9a51-2b0c8d7e6f10',
          comprobaciones: { base_datos: 'falla' },
        }),
      }),
    );
    await iniciarSesion(page, 'admin');
    await expect(page.getByText('El sistema no está listo.')).toBeVisible();
    await expect(page.locator('body')).not.toContainText(/10\.0\.0\.5|connection to server/);
  });
});

test('ruta desconocida con sesión → página no encontrada dentro del shell', async ({ page }) => {
  await simularSaludListo(page);
  await iniciarSesion(page, 'operador');
  await page.goto('/ruta-que-no-existe');
  // Recargar pierde la sesión (API simulada sin cookie): se comprueba el 404 tras volver a entrar.
  await enviarLogin(page, 'operador');
  await expect(page).toHaveURL('/ruta-que-no-existe');
  await expect(page.getByRole('heading', { name: /no encontrada|no encontrado/i })).toBeVisible();
});
