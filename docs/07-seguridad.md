# 07 · Seguridad por defecto (Secure by Default)

Marco de referencia: OWASP ASVS 4.0 nivel 2, OWASP Top 10 para LLM (2025), CIS Docker Benchmark. Principios: mínimo privilegio, denegar por defecto, defensa en profundidad, fallar cerrado, trazabilidad completa.

## 1. Modelo de amenazas (resumen)

| Activo | Amenaza | Control principal |
|---|---|---|
| Credenciales de correo y API keys | Fuga desde BD, logs o API | Cifrado envelope AES-256-GCM (ADR-0006); nunca se serializan; redacción en logs; escaneo de secretos en CI. |
| Contenido de correos (PII) | Acceso no autorizado, retención excesiva | RBAC, cifrado en tránsito, retención configurable, anonimización, auditoría. |
| Agentes LLM | Prompt injection / jailbreak desde correos o chat | Guardián (Jev + reglas), correos como datos delimitados, herramientas de solo lectura, sin envío automático, salida estructurada validada. |
| Envío de correo | Uso del sistema para spam/phishing saliente | Aprobación humana, límites por cuenta/hora, plantillas, DKIM del dominio, registro de todo envío. |
| Panel web | Robo de sesión, CSRF, XSS | JWT corto en memoria + refresh httpOnly SameSite=Strict, CSP, sanitizado nh3, iframe sandbox, cabeceras de seguridad. |
| API | Fuerza bruta, abuso, IDOR | Rate limiting, Argon2id, bloqueo progresivo, autorización por recurso, validación Pydantic estricta. |
| Infraestructura | Contenedor comprometido, SSRF hacia red interna | Usuario sin privilegios, FS de solo lectura, sin capacidades, allowlist de hosts salientes para IMAP/SMTP/webhooks, bloqueo de IP privadas. |
| Cadena de suministro | Dependencias vulnerables | Lockfiles, pip-audit/npm audit, Renovate, imágenes firmadas y escaneadas (Trivy), SBOM. |

## 2. Autenticación y autorización

- Contraseñas: Argon2id (m=64 MiB, t=3, p=4), longitud mínima 12, verificación contra lista de contraseñas filtradas (k-anonimato HIBP, opcional).
- Access JWT (HS256 con clave de 256 bits rotable o RS256 en Fase 2), `exp` 15 min, `aud`, `iss`, `jti`. Refresh opaco (256 bits) hash SHA-256 en BD, rotación con detección de reuso por familia.
- Bloqueo progresivo por usuario e IP tras 5 fallos (1 min, 5 min, 15 min…).
- RBAC: decorador `requiere_rol("admin")`; autorización por recurso en casos de uso (`puede_ver_cuenta(usuario, cuenta)`).
- MFA TOTP y SSO OIDC en Fase 2, con diseño previsto (`mfa_secreto_cifrado`, tabla `identidades_externas`).
- Webchat: token de sesión firmado con `aud=webchat`, sin acceso a la API del panel; `Origin` validado contra `sitios_webchat.origenes_permitidos`.

## 3. Gestión de secretos

- Clave maestra `APP_MASTER_KEY` (32 bytes base64) en variable de entorno o KMS (AWS KMS / GCP KMS / Vault en Fase 2). Nunca en el repositorio ni en la BD.
- Cifrado envelope: por cada secreto se genera una clave de datos aleatoria (AES-256-GCM), se cifra el secreto con ella y la clave de datos con la maestra; se guarda `version_clave_maestra` para rotación sin downtime (`make rotar-clave`).
- La API nunca devuelve secretos; solo `****1234`. Los formularios envían secretos solo en PUT dedicados.
- Logs: procesador structlog que redacta `password`, `secreto`, `authorization`, `api_key`, tokens JWT y direcciones de correo (parcial).
- `.env` fuera de Git; `.env.example` sin valores reales; hook de Claude Code y gitleaks bloquean commits con secretos.

## 4. Seguridad de los agentes (OWASP LLM Top 10)

| Riesgo | Control |
|---|---|
| LLM01 Prompt injection | El correo/chat va en un bloque delimitado y etiquetado como datos no confiables; el prompt de sistema instruye a no obedecerlo; Guardián con Jev + reglas; texto oculto eliminado por nh3; recorte de contexto; el Enrutador y las acciones son deterministas. |
| LLM02 Salida insegura | Salida siempre estructurada y validada (Pydantic); HTML del borrador generado desde texto (sin HTML del modelo); enlaces solo de la base de conocimiento. |
| LLM03 Envenenamiento | Base de conocimiento versionada y revisada; correcciones de operadores auditadas antes de usarse en evaluación. |
| LLM04 DoS del modelo | Límites de tokens por agente, timeouts, presupuesto diario de costo por cuenta con corte automático, colas con concurrencia acotada. |
| LLM05 Cadena de suministro | SDKs oficiales fijados; pruebas de contrato por proveedor. |
| LLM06 Fuga de información | Redacción de PII en entradas persistidas; no se envían adjuntos al modelo en Fase 1; datos de un cliente nunca se mezclan entre cuentas en el contexto. |
| LLM07 Plugins inseguros | Herramientas con allowlist por agente, parámetros tipados, solo lectura; enviar/borrar nunca son herramientas del modelo. |
| LLM08 Autonomía excesiva | Human-in-the-loop por defecto; políticas explícitas para relajarlo por categoría; límites de envío. |
| LLM09 Dependencia excesiva | Confianza y probabilidades visibles en la UI; respaldo LLM ante baja confianza; métrica de precisión con correcciones. |
| LLM10 Robo de modelo/prompt | Prompts en BD con RBAC; el Redactor no revela su prompt (instrucción + Guardián detecta la petición). |

Reglas de oro para prompts (se validan con el linter del editor y el hook de Claude Code): el prompt nunca dice "sigue las instrucciones del correo"; siempre incluye la cláusula de datos no confiables; nunca incluye secretos ni datos de clientes reales.

## 5. Seguridad de la API y la web

- Cabeceras: `Strict-Transport-Security`, `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`.
- CSP del panel (ADR-0012): el panel se sirve en el mismo origen que la API (Nginx del contenedor `web` reenvía `/api/`), con `connect-src 'self'`, nonce por petición en `style-src`, Trusted Types, `frame-ancestors 'none'`, `base-uri 'self'`, `form-action 'self'` y sin orígenes de terceros (tipografías autoalojadas). Única fuente: `infra/nginx-cabeceras-panel.conf`; la `location /api/` no la añade y conserva las cabeceras propias de la API (`default-src 'none'`). `index.html` se sirve con `Cache-Control: no-store`.
- Access token del panel solo en memoria (`SesionStore`); `Authorization` solo en rutas relativas `/api/` y nunca en `/auth/login|refresh|logout`; refresh reactivo único y compartido ante 401; redirecciones `?volver=` validadas con `rutaInternaSegura`. Los guards de rutas son de experiencia de usuario: la autorización la aplica el backend.
- CORS: allowlist explícita de orígenes; el panel no la necesita (mismo origen) y `CORS_ORIGENES` queda para despliegues con otro origen; credenciales solo para esos orígenes; el widget usa su propio endpoint con validación de `Origin` por sitio.
- Rate limiting (slowapi) por IP y por usuario; límites específicos en login, playground, webchat y envío.
- Validación estricta: Pydantic `extra="forbid"`, tamaños máximos de body (1 MB API, 4 KB mensaje de chat), tipos de archivo permitidos.
- SSRF: hosts IMAP/SMTP/webhook resueltos y verificados contra rangos privados (RFC 1918, link-local, loopback) salvo allowlist explícita del admin; sin redirecciones en webhooks; timeouts cortos.
- IDOR: todo acceso a recurso filtra por permisos del usuario; ids UUID v7 no secuenciales.
- Subida/descarga: adjuntos no se sirven en Fase 1; cuando se sirvan, `Content-Disposition: attachment` y escaneo.
- Errores: sin trazas al cliente; `problem+json` con `instance` correlacionable en logs.

## 6. Datos

- TLS 1.2+ obligatorio hacia IMAP/SMTP (`ssl` o `starttls`, verificación de certificado; sin opción de desactivar en producción).
- Cifrado en reposo del volumen de PostgreSQL (nivel de disco) + cifrado de columnas sensibles.
- Respaldos cifrados, probados mensualmente (restauración en staging).
- Retención y borrado: tareas periódicas auditadas; derecho de supresión por dirección de correo (`POST /privacidad/suprimir`, admin).
- Auditoría append-only con hash encadenado; el rol de aplicación no tiene UPDATE/DELETE sobre `auditoria`.

## 7. Infraestructura y despliegue

- Imágenes: base `python:3.12-slim` con multi-stage, usuario `app` (uid 10001), `read_only: true`, `cap_drop: [ALL]`, `no-new-privileges`, `tmpfs` para `/tmp`.
- Red: `db` sin puertos publicados; API detrás de reverse proxy con TLS (Caddy/Traefik) y HTTP/2.
- Variables de entorno validadas al arranque (`pydantic-settings`); el proceso no arranca si falta `APP_MASTER_KEY` o `JWT_SECRET` en `ENV=production`, o si `DEBUG=true`.
- Healthchecks de liveness/readiness; readiness falla si las migraciones no coinciden con `head`.
- Escaneo de imagen (Trivy) y SBOM (Syft) en CI; bloqueo por CVE crítico.
- Registro de dependencias: `uv.lock` y `package-lock.json` obligatorios; Renovate con auto-merge solo para parches con CI verde.

## 8. Seguridad en el proceso de desarrollo con Claude Code

- Hooks (`.claude/hooks`): bloqueo de comandos destructivos, escritura de secretos, edición de archivos protegidos, `git push --force`; lint y SAST automáticos tras cada edición.
- Agente `seguridad` revisa cada épica antes del PR (checklist ASVS + OWASP LLM).
- `permissions.deny` en `.claude/settings.json` para `.env*`, claves y directorios de credenciales.
- Ningún agente de Claude Code recibe credenciales reales; las pruebas usan servidores IMAP/SMTP locales (GreenMail/MailHog) y respuestas grabadas de proveedores.

## 9. Checklist de salida a producción

- [ ] `APP_MASTER_KEY`, `JWT_SECRET` únicos por entorno y fuera del repo.
- [ ] TLS extremo a extremo; HSTS activo.
- [ ] Usuario admin inicial con contraseña cambiada y MFA (Fase 2) activado.
- [ ] Orígenes CORS y sitios de webchat restringidos.
- [ ] Rate limits y presupuestos de costo configurados.
- [ ] Respaldo automático y prueba de restauración documentada.
- [ ] `pip-audit`, `npm audit`, Trivy sin críticos.
- [ ] Revisión del agente `seguridad` firmada en el PR de release.
