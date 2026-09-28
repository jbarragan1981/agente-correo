import { HttpErrorResponse, HttpHeaders } from '@angular/common/http';

import { ID_PRUEBA, problema, respuestaNoProblema } from '../../../testing/ayudas-http';
import {
  TipoError,
  aErrorApp,
  crearErrorApp,
  errorDeRecurso,
  esErrorApp,
  esProblema,
  mensajeDeError,
} from './error-app';

describe('aErrorApp', () => {
  const casos: [string, number, TipoError][] = [
    ['validacion', 400, 'validacion'],
    ['no_autenticado', 401, 'no_autenticado'],
    ['sin_permiso', 403, 'sin_permiso'],
    ['no_encontrado', 404, 'no_encontrado'],
    ['metodo_no_permitido', 405, 'metodo_no_permitido'],
    ['conflicto', 409, 'conflicto'],
    ['proveedor_rechazo', 422, 'proveedor_rechazo'],
    ['limite_excedido', 429, 'limite_excedido'],
    ['proveedor_no_disponible', 502, 'proveedor_no_disponible'],
    ['error_interno', 500, 'error_interno'],
    ['no_listo', 503, 'no_listo'],
    ['error_http', 418, 'error_http'],
    ['tipo_que_no_existe', 418, 'error_http'],
  ];

  it.each(casos)(
    'type %s con estado %i → tipo %s y mensaje del catálogo',
    (tipo, estado, esperado) => {
      const error = aErrorApp(problema(tipo, estado));
      expect(error).toMatchObject({ tipo: esperado, estado, mensaje: mensajeDeError(esperado) });
    },
  );

  it('problem+json → conserva detail como detalle', () => {
    expect(aErrorApp(problema('conflicto', 409)).detalle).toBe('Detalle del servidor.');
  });

  it('instance urn:uuid → idCorrelacion con el UUID', () => {
    expect(aErrorApp(problema('error_interno', 500)).idCorrelacion).toBe(ID_PRUEBA);
  });

  it('instance sin urn:uuid → usa la cabecera X-Request-ID', () => {
    const id = crypto.randomUUID();
    const error = aErrorApp(
      problema('error_interno', 500, { instance: 'otra-cosa' }, { 'X-Request-ID': id }),
    );
    expect(error.idCorrelacion).toBe(id);
  });

  it('instance sin UUID y sin cabecera → idCorrelacion null', () => {
    expect(
      aErrorApp(problema('error_interno', 500, { instance: 'urn:uuid:no-es-uuid' })).idCorrelacion,
    ).toBeNull();
  });

  it('400 con errores[] → conserva campo y mensaje', () => {
    const errores = [{ campo: 'body.email', mensaje: 'Field required' }];
    expect(aErrorApp(problema('validacion', 400, { errores })).errores).toEqual(errores);
  });

  it('400 con errores[] malformados → descarta las entradas inválidas', () => {
    const errores = [{ campo: 'a' }, null, 'texto', { campo: 'b', mensaje: 'm' }];
    expect(aErrorApp(problema('validacion', 400, { errores })).errores).toEqual([
      { campo: 'b', mensaje: 'm' },
    ]);
  });

  it('400 con errores que no es lista → lista vacía', () => {
    expect(aErrorApp(problema('validacion', 400, { errores: 'x' })).errores).toEqual([]);
  });

  it('errores[] fuera de un 400 → se ignoran', () => {
    const errores = [{ campo: 'a', mensaje: 'b' }];
    expect(aErrorApp(problema('conflicto', 409, { errores })).errores).toEqual([]);
  });

  it('503 con comprobaciones → las conserva', () => {
    const error = aErrorApp(
      problema('no_listo', 503, { comprobaciones: { base_datos: 'falla', otra: 3 } }),
    );
    expect(error.comprobaciones).toEqual({ base_datos: 'falla' });
  });

  it('503 con comprobaciones que no son objeto → null', () => {
    expect(
      aErrorApp(problema('no_listo', 503, { comprobaciones: ['falla'] })).comprobaciones,
    ).toBeNull();
  });

  it('429 con Retry-After numérico → reintentarEnS y mensaje con los segundos', () => {
    const error = aErrorApp(problema('limite_excedido', 429, {}, { 'Retry-After': '60' }));
    expect([error.reintentarEnS, error.mensaje.includes('60')]).toEqual([60, true]);
  });

  it('429 con Retry-After no numérico → reintentarEnS null', () => {
    const cabeceras = { 'Retry-After': 'Wed, 21 Oct 2015 07:28:00 GMT' };
    expect(aErrorApp(problema('limite_excedido', 429, {}, cabeceras)).reintentarEnS).toBeNull();
  });

  it('Content-Type problem+json con parámetros → se interpreta', () => {
    const error = new HttpErrorResponse({
      status: 404,
      headers: new HttpHeaders({ 'Content-Type': 'application/problem+json; charset=utf-8' }),
      error: { type: 'no_encontrado', title: 't', status: 404, instance: `urn:uuid:${ID_PRUEBA}` },
    });
    expect(aErrorApp(error).tipo).toBe('no_encontrado');
  });

  it('estado 0 → red con mensaje de conexión', () => {
    const error = aErrorApp(
      new HttpErrorResponse({ status: 0, error: new ProgressEvent('error') }),
    );
    expect(error).toMatchObject({
      tipo: 'red',
      estado: 0,
      mensaje: 'No se pudo contactar con el servidor.',
    });
  });

  it('HTML de un 502 de proxy → desconocido sin exponer el cuerpo', () => {
    const error = aErrorApp(respuestaNoProblema());
    expect([error.tipo, error.detalle, JSON.stringify(error).includes('nginx')]).toEqual([
      'desconocido',
      null,
      false,
    ]);
  });

  it('JSON sin type con Content-Type problem+json → desconocido', () => {
    const error = new HttpErrorResponse({
      status: 500,
      headers: new HttpHeaders({ 'Content-Type': 'application/problem+json' }),
      error: { title: 'x', status: 500 },
    });
    expect(aErrorApp(error).tipo).toBe('desconocido');
  });

  it('problem válido servido como application/json → desconocido', () => {
    const error = new HttpErrorResponse({
      status: 404,
      headers: new HttpHeaders({ 'Content-Type': 'application/json' }),
      error: {
        type: 'no_encontrado',
        title: 't',
        status: 404,
        instance: 'urn:uuid:x',
        detail: 'secreto',
      },
    });
    expect(aErrorApp(error)).toMatchObject({ tipo: 'desconocido', detalle: null });
  });

  it('valor que no es HttpErrorResponse → desconocido', () => {
    expect(aErrorApp(new Error('x')).tipo).toBe('desconocido');
  });

  it('un ErrorApp → se devuelve tal cual', () => {
    const original = crearErrorApp('conflicto', 409);
    expect(aErrorApp(original)).toBe(original);
  });
});

describe('esProblema', () => {
  it.each([null, 'texto', [], { type: 'x' }, { type: 1, title: 't', status: 1, instance: 'i' }])(
    'cuerpo inválido %j → false',
    (cuerpo) => {
      expect(esProblema(cuerpo)).toBe(false);
    },
  );

  it('cuerpo con type, title, status e instance → true', () => {
    expect(esProblema({ type: 'x', title: 't', status: 400, instance: 'i' })).toBe(true);
  });
});

describe('esErrorApp y errorDeRecurso', () => {
  it('objeto con la misma forma no creado por el módulo → no es ErrorApp', () => {
    expect(esErrorApp({ ...crearErrorApp('red', 0) })).toBe(false);
  });

  it('error envuelto por resource() → recupera el ErrorApp de cause', () => {
    const original = crearErrorApp('no_listo', 503);
    expect(errorDeRecurso(new Error('envuelto', { cause: original }))).toBe(original);
  });

  it('error sin cause → lo convierte', () => {
    expect(errorDeRecurso(new Error('x')).tipo).toBe('desconocido');
  });
});

describe('mensajeDeError', () => {
  it.each<TipoError>(['red', 'desconocido', 'no_listo', 'limite_excedido'])(
    'tipo %s → mensaje no vacío',
    (tipo) => {
      expect(mensajeDeError(tipo).length).toBeGreaterThan(0);
    },
  );
});
