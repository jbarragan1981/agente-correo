// Comprueba que Node cumple engines.node (^22.22.3 || ^24.15.0) antes de ejecutar el CLI de Angular.
import { readFileSync } from 'node:fs';

const [mayor, menor, parche] = process.versions.node.split('.').map(Number);
const valido =
  (mayor === 22 && (menor > 22 || (menor === 22 && parche >= 3))) ||
  (mayor === 24 && menor >= 15) ||
  mayor >= 26;

if (!valido) {
  const recomendado = readFileSync(new URL('../.nvmrc', import.meta.url), 'utf8').trim();
  process.stderr.write(
    `Node ${process.versions.node} no es compatible con Angular CLI 22 (requiere ^22.22.3 || ^24.15.0).\n` +
      `Usa 'nvm use' (frontend/.nvmrc = ${recomendado}) o 'npx -y -p node@${recomendado} -- npm run <script>'.\n`,
  );
  process.exit(1);
}
