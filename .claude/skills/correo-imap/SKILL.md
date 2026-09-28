---
name: correo-imap
description: >-
  Conexión segura a cuentas de correo en Agente Correo: IMAP IDLE y polling con aioimaplib, parseo robusto de mensajes (email stdlib, codificaciones, multipart, adjuntos), saneado de HTML con nh3, deduplicación, cursor UID/UIDVALIDITY, marcado de procesados, envío SMTP con aiosmtplib (respuestas en hilo), pruebas con GreenMail y particularidades de Gmail/Microsoft 365. Úsalo al tocar infrastructure/correo o el nodo Ingestor.
---

# Correo · IMAP/SMTP

Referencias: `docs/01-arquitectura.md` §6, `docs/03-modelo-de-datos.md` §2.3, `docs/07-seguridad.md`.

## Puerto
`MailboxPort`: `probar_conexion() -> Capacidades`, `listar_carpetas()`, `escuchar(carpeta) -> AsyncIterator[NuevoUid]` (IDLE con renovación cada 25 min o polling cada `intervalo_polling_s`), `obtener(uid) -> MensajeCrudo`, `marcar(uid, banderas, etiquetas)`, `mover(uid, carpeta)`, `enviar(MensajeSaliente) -> str (message_id)`.

## Conexión
- `aioimaplib.IMAP4_SSL(host, 993)` o `IMAP4` + `starttls()`; `ssl.create_default_context()` con verificación obligatoria; timeout 30 s; una conexión IDLE por cuenta en el worker, con reconexión exponencial (1, 2, 4… 300 s) y métrica `imap_conexion_errores_total`.
- Antes de conectar: validar host contra IPs privadas (SSRF) salvo allowlist; nunca registrar credenciales.
- `UIDVALIDITY` cambiado → reiniciar cursor y reprocesar solo lo no visto por `message_id`/`hash_contenido`.
- Gmail: IMAP requiere contraseña de aplicación (2FA); etiquetas vía `X-GM-LABELS`; carpeta `[Gmail]/Todos`. Microsoft 365: IMAP básico está deshabilitado en muchos tenants → OAuth2 (`XOAUTH2`) en Fase 2; documentar el error claro en "Probar conexión".

## Descarga y parseo
- `FETCH uid (RFC822.SIZE BODY.PEEK[] FLAGS INTERNALDATE)` (PEEK para no marcar leído). Límite 5 MB de cuerpo; adjuntos solo metadatos (`nombre`, `mime`, `tamano`, `sha256` si se descarga bajo demanda).
- `email.message_from_bytes(raw, policy=email.policy.default)`; texto preferido `text/plain`, si no, `text/html` → texto con `nh3.clean` + conversión a texto (`html2text` sin enlaces de imágenes); normalizar codificaciones (`get_content(errors="replace")`), cabeceras decodificadas (`str(msg["Subject"])`).
- Extraer: `Message-ID`, `In-Reply-To`, `References`, `From/To/Cc` (`email.utils.getaddresses`), `Date` (`parsedate_to_datetime`, fallback INTERNALDATE), `Authentication-Results` → spf/dkim/dmarc, `List-Unsubscribe` (señal de boletín), URLs (dominios) y adjuntos.
- Deduplicación: `UNIQUE(cuenta_id, uidvalidity, uid_imap)` + `hash_contenido = sha256(message_id or (from+date+subject+cuerpo[:2000]))`.
- HTML saneado para el panel: `nh3.clean(html, tags=…seguros…, attributes=…, link_rel="noopener noreferrer", strip_comments=True)`, eliminar `style` con `display:none`/`font-size:0`/`color` igual al fondo y guardar el texto oculto como señal de riesgo.

## Marcado y acciones
Etiqueta privada `$AgenteProcesado` (keyword IMAP) + `\Seen` solo si la política lo indica; `mover` con `MOVE` si el servidor lo soporta (`CAPABILITY`), si no `COPY`+`\Deleted`+`EXPUNGE`. Todas las acciones idempotentes y auditadas.

## Envío SMTP
`aiosmtplib.send(mensaje, hostname, port=587, start_tls=True | port=465 use_tls=True, username, password, timeout=30)`. Construir con `EmailMessage`: `In-Reply-To` y `References` del original para mantener el hilo; `Subject: Re: …`; multipart `text/plain` + `text/html` generado desde el texto del borrador (nunca HTML del LLM); firma de la cuenta; cabecera `X-Agente-Correo-Ejecucion: <id>`. Límite de envíos por cuenta/hora desde `politica`. Guardar `message_id_enviado`.

## Ingestor (nodo sin LLM)
Convierte `MensajeCrudo` → `MensajeNormalizado` (texto recortado para Jev, cuerpo completo saneado para el panel, señales deterministas). Sin llamadas de red. Pruebas con los `.eml` de `tests/fixtures/correos/`.

## Pruebas
- Unitarias de parseo con `.eml` reales anonimizados: multipart anidado, HTML sin texto, codificaciones `iso-8859-1`/`utf-7`, adjuntos inline, cabeceras malformadas, correo sin `Message-ID`.
- Integración con GreenMail en testcontainers (`greenmail/standalone`): IDLE/polling detecta un correo nuevo; `UIDVALIDITY` cambiado; marcar/mover; envío SMTP y verificación del hilo.
- Nunca pruebas contra cuentas reales en CI.
