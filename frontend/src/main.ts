import { bootstrapApplication } from '@angular/platform-browser';

import { App } from './app/app';
import { appConfig } from './app/app.config';

bootstrapApplication(App, appConfig).catch((error: unknown) => {
  // Sin consola (CA20): el fallo de arranque se hace visible en el propio documento.
  document.body.dataset['errorArranque'] = error instanceof Error ? error.name : 'desconocido';
});
