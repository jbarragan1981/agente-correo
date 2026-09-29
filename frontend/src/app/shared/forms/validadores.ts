/**
 * Punto único de acceso a Signal Forms (ADR-0005): si la API cambia, se ajusta aquí.
 * Validadores con mensajes en español para los formularios del panel.
 */
import { SchemaPath, email, maxLength, required } from '@angular/forms/signals';

export { FormField, form, submit } from '@angular/forms/signals';
export type { FieldTree } from '@angular/forms/signals';

/** Campo obligatorio con mensaje en español. */
export function requerido(campo: SchemaPath<string>, mensaje: string): void {
  required(campo, { message: mensaje });
}

/** Dirección de correo con formato válido. */
export function correo(campo: SchemaPath<string>, mensaje: string): void {
  email(campo, { message: mensaje });
}

/** Longitud máxima de un texto (también fija `maxlength` en el control enlazado). */
export function longitudMaxima(campo: SchemaPath<string>, maximo: number, mensaje: string): void {
  maxLength(campo, maximo, { message: mensaje });
}

/** Primer mensaje de error de un campo o `null`. */
export function primerError(errores: readonly { message?: string }[]): string | null {
  return errores.find((e) => typeof e.message === 'string')?.message ?? null;
}
