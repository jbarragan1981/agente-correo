import { SECCIONES, seccionPorRuta, seccionesPara } from './navegacion';

describe('navegacion', () => {
  it('11 secciones con rutas únicas', () => {
    expect(new Set(SECCIONES.map((s) => s.ruta)).size).toBe(11);
  });

  it('admin → ve todas las secciones', () => {
    expect(seccionesPara(['admin']).length).toBe(SECCIONES.length);
  });

  it('auditor → no ve aprobaciones, taxonomía, webchat ni usuarios', () => {
    const rutas = seccionesPara(['auditor']).map((s) => s.ruta);
    expect(
      rutas.filter((r) => ['aprobaciones', 'taxonomia', 'webchat', 'usuarios'].includes(r)),
    ).toEqual([]);
  });

  it('sin roles → ninguna sección', () => {
    expect(seccionesPara([])).toEqual([]);
  });

  it('seccionPorRuta → encuentra la sección o undefined', () => {
    expect([seccionPorRuta('bandeja')?.epica, seccionPorRuta('nada')]).toEqual(['E1.7', undefined]);
  });
});
