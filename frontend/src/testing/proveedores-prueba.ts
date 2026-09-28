import { provideZonelessChangeDetection } from '@angular/core';

/** Proveedores comunes de todas las pruebas Vitest (providersFile en angular.json). */
const proveedoresPrueba = [provideZonelessChangeDetection()];

export default proveedoresPrueba;
