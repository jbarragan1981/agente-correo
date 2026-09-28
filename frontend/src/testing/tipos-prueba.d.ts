/** Importación de CSS como texto en pruebas (`with { loader: 'text' }`). */
declare module '*.css' {
  const contenido: string;
  export default contenido;
}
