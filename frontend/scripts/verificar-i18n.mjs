// Comprueba que src/locale/messages.es.xlf está al día (CA17): extrae los mensajes a un
// directorio temporal con el CLI de Angular y compara el resultado con el archivo versionado.
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const raiz = fileURLToPath(new URL('..', import.meta.url));
const versionado = join(raiz, 'src/locale/messages.es.xlf');
const temporal = mkdtempSync(join(tmpdir(), 'panel-i18n-'));
const ng = createRequire(import.meta.url).resolve('@angular/cli/bin/ng.js');

try {
  execFileSync(
    process.execPath,
    [
      ng,
      'extract-i18n',
      '--output-path',
      temporal,
      '--out-file',
      'messages.es.xlf',
      '--format',
      'xlf2',
    ],
    {
      cwd: raiz,
      stdio: ['ignore', 'ignore', 'inherit'],
      env: { ...process.env, NG_CLI_ANALYTICS: 'false' },
    },
  );
  const extraido = readFileSync(join(temporal, 'messages.es.xlf'), 'utf8');
  let actual = '';
  try {
    actual = readFileSync(versionado, 'utf8');
  } catch {
    actual = '';
  }
  if (extraido !== actual) {
    process.stderr.write(
      'verificar-i18n: src/locale/messages.es.xlf no está al día. Ejecuta "npm run i18n:extraer" y versiona el resultado.\n',
    );
    process.exit(1);
  }
  const unidades = (extraido.match(/<unit /g) ?? []).length;
  process.stdout.write(`verificar-i18n: ${unidades} mensajes al día\n`);
} finally {
  rmSync(temporal, { recursive: true, force: true });
}
