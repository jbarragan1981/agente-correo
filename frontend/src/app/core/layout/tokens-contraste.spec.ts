import tokensCss from '../../../styles/tokens.css' with { loader: 'text' };

import { PARES_CONTRASTE, contraste, leerTokens } from './tokens-contraste';

const claro = leerTokens(tokensCss, ':root');
const oscuro = { ...claro, ...leerTokens(tokensCss, 'oscuro') };

function casos(tokens: Record<string, string>): [string, string, number, string, string][] {
  return PARES_CONTRASTE.map((p) => [
    p.primerPlano,
    p.fondo,
    p.minimo,
    tokens[p.primerPlano] ?? '',
    tokens[p.fondo] ?? '',
  ]);
}

describe('contraste de tokens (AA)', () => {
  it.each(casos(claro))('claro: %s sobre %s ≥ %d', (_pp, _f, minimo, a, b) => {
    expect(contraste(a, b)).toBeGreaterThanOrEqual(minimo);
  });

  it.each(casos(oscuro))('oscuro: %s sobre %s ≥ %d', (_pp, _f, minimo, a, b) => {
    expect(contraste(a, b)).toBeGreaterThanOrEqual(minimo);
  });

  it('blanco sobre la marca → no cumple AA (por eso existe --vm-texto-sobre-marca)', () => {
    expect(contraste(claro['--vm-blanco'] ?? '', claro['--vm-azul-marca'] ?? '')).toBeLessThan(4.5);
  });

  it('contraste de negro sobre blanco → 21', () => {
    expect(contraste(claro['--vm-blanco'] ?? '', claro['--vm-oscuro'] ?? '')).toBeGreaterThan(17);
  });

  it('los tokens de todos los pares existen en tokens.css', () => {
    const faltan = PARES_CONTRASTE.flatMap((p) => [p.primerPlano, p.fondo]).filter(
      (t) => !(t in claro),
    );
    expect(faltan).toEqual([]);
  });
});
