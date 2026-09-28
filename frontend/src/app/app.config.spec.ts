import { appConfig } from './app.config';

describe('appConfig', () => {
  it('declara proveedores de arranque → lista no vacía', () => {
    expect(appConfig.providers.length).toBeGreaterThan(0);
  });
});
