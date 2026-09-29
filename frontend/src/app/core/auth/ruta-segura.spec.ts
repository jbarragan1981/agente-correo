import { RUTA_POR_DEFECTO, rutaInternaSegura } from './ruta-segura';

describe('rutaInternaSegura', () => {
  it.each(['/inicio', '/bandeja?filtro=hoy', '/agentes/123#detalle', '/cuentas/a%20b'])(
    'ruta interna %s → se conserva',
    (ruta) => {
      expect(rutaInternaSegura(ruta)).toBe(ruta);
    },
  );

  it.each([
    null,
    undefined,
    '',
    '//evil.test',
    'https://evil.test',
    'http://evil.test/inicio',
    '/\\evil.test',
    '\\\\evil.test',
    'javascript:alert(1)',
    '/javascript:alert(1)',
    '%2F%2Fevil.test',
    '/%2F%2Fevil.test',
    '/%2Fevil.test',
    '/%5Cevil.test',
    '/%252F%252Fevil.test',
    '/%25252F%25252Fevil.test',
    ' /inicio',
    '/\t/evil.test',
    '/inicio%0A',
    '/%E0%A4%A',
    'inicio',
    `/${'a'.repeat(2100)}`,
  ])('vector %j → /inicio', (valor) => {
    expect(rutaInternaSegura(valor)).toBe(RUTA_POR_DEFECTO);
  });
});
