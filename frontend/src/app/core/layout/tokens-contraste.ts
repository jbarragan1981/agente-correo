/**
 * Pares de color del panel que deben cumplir contraste WCAG AA (plan E0.4 §4.3.2).
 * Solo nombres de token: los valores se leen de src/styles/tokens.css en la prueba.
 */
export interface ParContraste {
  readonly primerPlano: string;
  readonly fondo: string;
  /** 4,5 para texto normal; 3 para componentes de interfaz y texto grande. */
  readonly minimo: 4.5 | 3;
  readonly uso: string;
}

export const PARES_CONTRASTE: readonly ParContraste[] = [
  { primerPlano: '--vm-texto', fondo: '--vm-superficie', minimo: 4.5, uso: 'texto principal' },
  { primerPlano: '--vm-texto', fondo: '--vm-fondo-pagina', minimo: 4.5, uso: 'texto sobre fondo' },
  {
    primerPlano: '--vm-texto-secundario',
    fondo: '--vm-superficie',
    minimo: 4.5,
    uso: 'texto secundario',
  },
  {
    primerPlano: '--vm-texto-secundario',
    fondo: '--vm-fondo-pagina',
    minimo: 4.5,
    uso: 'texto secundario',
  },
  {
    primerPlano: '--vm-texto-sobre-marca',
    fondo: '--vm-azul-marca',
    minimo: 4.5,
    uso: 'botón primario',
  },
  { primerPlano: '--vm-enlace', fondo: '--vm-superficie', minimo: 4.5, uso: 'enlaces' },
  { primerPlano: '--vm-enlace', fondo: '--vm-fondo-pagina', minimo: 4.5, uso: 'enlaces' },
  { primerPlano: '--vm-error-texto', fondo: '--vm-superficie', minimo: 4.5, uso: 'errores' },
  { primerPlano: '--vm-error-texto', fondo: '--vm-fondo-pagina', minimo: 4.5, uso: 'errores' },
  { primerPlano: '--vm-exito-texto', fondo: '--vm-superficie', minimo: 4.5, uso: 'estado OK' },
  { primerPlano: '--vm-exito-texto', fondo: '--vm-fondo-pagina', minimo: 4.5, uso: 'estado OK' },
  { primerPlano: '--vm-alerta-texto', fondo: '--vm-superficie', minimo: 4.5, uso: 'advertencias' },
  {
    primerPlano: '--vm-alerta-texto',
    fondo: '--vm-fondo-pagina',
    minimo: 4.5,
    uso: 'advertencias',
  },
  {
    primerPlano: '--vm-sidebar-texto',
    fondo: '--vm-sidebar-fondo',
    minimo: 4.5,
    uso: 'menú lateral',
  },
  {
    primerPlano: '--vm-topbar-texto',
    fondo: '--vm-topbar-fondo',
    minimo: 4.5,
    uso: 'barra superior',
  },
  {
    primerPlano: '--vm-aviso-texto',
    fondo: '--vm-aviso-fondo',
    minimo: 4.5,
    uso: 'aviso modo simulado',
  },
  { primerPlano: '--vm-foco', fondo: '--vm-superficie', minimo: 3, uso: 'anillo de foco' },
  { primerPlano: '--vm-foco', fondo: '--vm-fondo-pagina', minimo: 3, uso: 'anillo de foco' },
  {
    primerPlano: '--vm-foco-inverso',
    fondo: '--vm-sidebar-fondo',
    minimo: 3,
    uso: 'foco en menú lateral',
  },
  {
    primerPlano: '--vm-foco-inverso',
    fondo: '--vm-topbar-fondo',
    minimo: 3,
    uso: 'foco en barra superior',
  },
];

/** Luminancia relativa WCAG 2.x de un color `#rrggbb`. */
export function luminancia(hex: string): number {
  const limpio = hex.replace('#', '');
  const canales = [0, 2, 4].map((i) => Number.parseInt(limpio.slice(i, i + 2), 16) / 255);
  const [r = 0, g = 0, b = 0] = canales.map((c) =>
    c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4,
  );
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** Relación de contraste WCAG entre dos colores `#rrggbb`. */
export function contraste(a: string, b: string): number {
  const [claro, oscuro] = [luminancia(a), luminancia(b)].sort((x, y) => y - x) as [number, number];
  return (claro + 0.05) / (oscuro + 0.05);
}

/** Extrae los tokens `--vm-*: #rrggbb` de un bloque CSS (claro = `:root {`, oscuro = `[data-tema='oscuro']`). */
export function leerTokens(css: string, selector: ':root' | 'oscuro'): Record<string, string> {
  const sinComentarios = css.replace(/\/\*[\s\S]*?\*\//g, '');
  const bloques = [...sinComentarios.matchAll(/([^{}]+)\{([^}]*)\}/g)];
  const bloque = bloques.find(([, sel = '']) =>
    selector === ':root' ? sel.trim() === ':root' : sel.includes("data-tema='oscuro'"),
  );
  const tokens: Record<string, string> = {};
  for (const [, nombre = '', valor = ''] of (bloque?.[2] ?? '').matchAll(
    /(--vm-[\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g,
  )) {
    tokens[nombre] = valor.toLowerCase();
  }
  return tokens;
}
