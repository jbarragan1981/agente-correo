import { TestBed } from '@angular/core/testing';
import { MatSnackBar } from '@angular/material/snack-bar';

import { ID_PRUEBA } from '../../../testing/ayudas-http';
import { crearErrorApp } from './error-app';
import { NotificadorErrores } from './notificador-errores';

describe('NotificadorErrores', () => {
  const open = vi.fn();

  beforeEach(() => {
    open.mockReset();
    TestBed.configureTestingModule({ providers: [{ provide: MatSnackBar, useValue: { open } }] });
  });

  it('5xx con id → texto con el código de referencia', () => {
    const texto = TestBed.inject(NotificadorErrores).texto(
      crearErrorApp('error_interno', 500, { idCorrelacion: ID_PRUEBA }),
    );
    expect(texto).toContain(`Código de referencia: ${ID_PRUEBA}`);
  });

  it('4xx → solo el mensaje del catálogo', () => {
    const error = crearErrorApp('conflicto', 409, { idCorrelacion: ID_PRUEBA });
    expect(TestBed.inject(NotificadorErrores).texto(error)).toBe(error.mensaje);
  });

  it('mostrar → abre un snackbar con el texto', async () => {
    await TestBed.inject(NotificadorErrores).mostrar(crearErrorApp('red', 0));
    expect(open).toHaveBeenCalledWith(
      'No se pudo contactar con el servidor.',
      'Cerrar',
      expect.any(Object),
    );
  });
});
