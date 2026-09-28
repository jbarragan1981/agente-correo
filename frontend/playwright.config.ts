import { defineConfig, devices } from '@playwright/test';

/**
 * Pruebas e2e del panel (plan E0.4 §6.2). Playwright 1.56.1 usa el Chromium de /opt/pw-browsers
 * (PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers). El servidor reproduce las cabeceras y el nonce de Nginx.
 * Las pruebas @backend solo se ejecutan con API_DESTINO (p. ej. http://127.0.0.1:8000): se arranca
 * el backend real con ENV=test y el servidor del panel le reenvía /api/.
 */
const PUERTO = Number(process.env['PUERTO'] ?? 4300);
const URL_BASE = `http://127.0.0.1:${PUERTO}`;
const API_DESTINO = process.env['API_DESTINO'] ?? '';
const REUTILIZAR = !process.env['CI'];

const servidorPanel = {
  command: 'npx ng build --configuration e2e --output-path dist/e2e && node e2e/servidor-panel.mjs',
  url: URL_BASE,
  reuseExistingServer: REUTILIZAR,
  timeout: 180_000,
  env: { DIST: 'dist/e2e/browser', PUERTO: String(PUERTO), API_DESTINO },
};

const servidorBackend = API_DESTINO
  ? [
      {
        command: `uv run --directory ../backend uvicorn --factory app.main:crear_app --host 127.0.0.1 --port ${new URL(API_DESTINO).port || '8000'} --no-server-header --no-access-log`,
        url: `${API_DESTINO}/api/v1/salud`,
        reuseExistingServer: REUTILIZAR,
        timeout: 120_000,
        env: { ENV: 'test' },
      },
    ]
  : [];

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env['CI'],
  retries: 0,
  reporter: [['list']],
  grepInvert: API_DESTINO ? undefined : /@backend/,
  use: {
    baseURL: URL_BASE,
    trace: 'retain-on-failure',
    locale: 'es-EC',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [...servidorBackend, servidorPanel],
});
