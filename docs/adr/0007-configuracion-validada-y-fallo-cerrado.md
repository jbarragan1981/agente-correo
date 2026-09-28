# ADR-0007 · Configuración validada con fallo cerrado y sin eco de valores

**Estado:** Aceptada · 2026-09-28 · Épica E0.1

## Contexto
`docs/07-seguridad.md` §7 exige que el proceso no arranque en `ENV=production` si faltan `APP_MASTER_KEY` o `JWT_SECRET`, o si `DEBUG=true`. La skill `fastapi-backend` proponía `SettingsConfigDict(env_file=".env", extra="forbid")`. Al diseñar E0.1 aparecieron tres problemas concretos:

1. Con `extra="forbid"`, pydantic-settings rechaza cualquier clave del archivo `.env` que no sea un campo de `Settings`. El `.env` de la raíz es compartido: Docker Compose lo usa para interpolar (`POSTGRES_USER`, `POSTGRES_PASSWORD`) y contiene variables de épicas futuras (`TYPESAFE_API_KEY`, `DB_AUTO_CREATE`, `FAKE_PROVIDERS`…). El backend no arrancaría en local con un `.env` válido.
2. `pydantic.ValidationError` incluye `input_value=...` en su texto. Un `JWT_SECRET` demasiado corto o una `DATABASE_URL` mal formada acabarían impresos en la traza de arranque y en los logs del contenedor.
3. `FastAPI(debug=True)` hace que `ServerErrorMiddleware` devuelva trazas HTML al cliente, lo que contradice "errores sin trazas al cliente" (`docs/07-seguridad.md` §5).

## Decisión
- `Settings` (en `app/core/config.py`, único módulo que lee el entorno) usa `SettingsConfigDict(extra="ignore", hide_input_in_errors=True, case_sensitive=False, env_file=<raíz del repo>/.env, env_file_encoding="utf-8")`. Si el archivo no existe (contenedores), solo se leen variables de proceso.
- La protección contra erratas que daba `extra="forbid"` se sustituye por validadores de campo explícitos y por la documentación de variables en `backend/README.md`.
- Un validador `model_validator(mode="after")` aplica el **fallo cerrado de producción**: con `ENV=production` exige `APP_MASTER_KEY` (base64 de 32 bytes exactos), `JWT_SECRET` (≥ 32 bytes), `DEBUG=false`, `DATABASE_URL` definida explícitamente y `CORS_ORIGENES` no vacío y solo `https`.
- `cargar_settings()` captura `ValidationError` y lanza `ConfiguracionInvalida` con solo `loc` y `msg` de cada error; el proceso termina con código ≠ 0 y un log JSON sin valores.
- Los secretos se tipan como `SecretStr` (incluida `DATABASE_URL`, que lleva contraseña); `repr(settings)` nunca los muestra.
- `DEBUG` solo sube el nivel de log. La app se construye siempre con `FastAPI(debug=False)`.
- La app se crea con una fábrica `crear_app(settings)` y Uvicorn la arranca con `--factory app.main:crear_app`; importar `app.main` no tiene efectos laterales (no lee entorno ni abre conexiones), lo que permite construir apps de prueba con `Settings` explícitos.

## Alternativas consideradas
- **`extra="forbid"` y declarar en `Settings` todas las variables de `.env.example`:** acopla E0.1 a variables de épicas futuras (proveedores de IA) y rompe con las variables de Compose. Descartada.
- **`.env` separado para el backend (`backend/.env`):** duplica secretos en dos archivos y complica `make keys`. Descartada.
- **Envolver `ValidationError` sin `hide_input_in_errors`:** frágil ante cualquier ruta que imprima la excepción original (p. ej. Uvicorn al fallar la fábrica). Descartada: se usan ambas medidas.
- **Instancia de módulo `app = FastAPI(...)`:** obliga a tener entorno válido al importar y complica las pruebas por entorno. Descartada.

## Consecuencias
- (+) El backend arranca en local con el `.env` compartido y falla cerrado en producción con mensajes que no filtran valores.
- (+) Las pruebas construyen `Settings(_env_file=None, ...)` y `crear_app(settings)` sin tocar `os.environ`.
- (−) Una variable con errata (p. ej. `CORS_ORIGEN`) se ignora sin aviso. Se mitiga con valores por defecto seguros (deny-by-default: sin CORS, sin docs en producción) y validadores que fallan si falta lo imprescindible.
- (−) El `CMD` del Dockerfile y el `command` de Compose deben usar `--factory`.
