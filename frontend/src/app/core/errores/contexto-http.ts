import { HttpContextToken } from '@angular/common/http';

/** La petición no lleva `Authorization` (login, refresh, logout). */
export const SIN_TOKEN = new HttpContextToken<boolean>(() => false);

/** Los errores de la petición no se notifican al usuario; quien llama los gestiona. */
export const SILENCIAR_ERRORES = new HttpContextToken<boolean>(() => false);

/** La petición ya se repitió tras un refresh; un nuevo 401 cierra la sesión. */
export const REINTENTADA = new HttpContextToken<boolean>(() => false);
