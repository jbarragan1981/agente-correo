import { RUTA_POR_DEFECTO, rutaInternaSegura } from './ruta-segura';

/** Vectores adicionales de redirección abierta (CA10) aportados por QA. */
describe('rutaInternaSegura · vectores adicionales (QA)', () => {
  it.each([
    '///evil.test',
    '////evil.test',
    '/\\/evil.test',
    '/\\\\evil.test',
    '/%5C%5Cevil.test',
    '/%09/evil.test',
    '/%0D%0Alocation:%20https://evil.test',
    '/%00',
    '\u0000/inicio',
    '/inicio\u0000',
    '/inicio\r\nSet-Cookie: a=b',
    '/ /evil.test'.replace(' ', '\t'),
    'HTTPS://EVIL.TEST',
    'data:text/html,<script>alert(1)</script>',
    'vbscript:msgbox(1)',
    'JaVaScRiPt:alert(1)',
    '/jAvAsCrIpT:alert(1)',
    '//%2F/evil.test',
    '/%252F%252Fevil.test',
    '/%',
    '/%E0%A4%A',
    '/%ZZ',
    'evil.test/inicio',
    '?volver=/inicio',
    '#/inicio',
  ])('vector %j → /inicio', (vector) => {
    expect(rutaInternaSegura(vector)).toBe(RUTA_POR_DEFECTO);
  });

  it.each([
    '/inicio',
    '/agentes/3f2b8c1e-6d4a-4f7e-9a51-2b0c8d7e6f10',
    '/bandeja?estado=abierto&pagina=2',
    '/auditoria?desde=2026-09-01#tabla',
    '/cuentas/a%20b',
    '/bandeja?q=https://evil.test',
    '/bandeja?q=%2F%2Fevil.test',
    '/bandeja?q=javascript:alert(1)',
  ])('ruta interna legítima %s → se conserva', (ruta) => {
    expect(rutaInternaSegura(ruta)).toBe(ruta);
  });

  it.each([1, 0, {}, [], ['/inicio'], true] as unknown[])(
    'valor que no es cadena %j → /inicio',
    (valor) => {
      expect(rutaInternaSegura(valor as string)).toBe(RUTA_POR_DEFECTO);
    },
  );

  it('ruta de exactamente 2048 caracteres → se conserva; de 2049 → /inicio', () => {
    const limite = `/${'a'.repeat(2047)}`;
    expect([rutaInternaSegura(limite), rutaInternaSegura(`${limite}a`)]).toEqual([
      limite,
      RUTA_POR_DEFECTO,
    ]);
  });
});
