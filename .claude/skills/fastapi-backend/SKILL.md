---
name: fastapi-backend
description: Convenciones y patrones del backend de Agente Correo con FastAPI, Pydantic v2, SQLAlchemy 2 async, arquitectura hexagonal, inyección de dependencias, errores problem+json, autenticación JWT/RBAC, rate limiting y observabilidad. Úsalo al crear o modificar routers, casos de uso, repositorios, esquemas, configuración o el arranque de la aplicación.
---

# Backend FastAPI · convenciones

## Estructura (ver `docs/01-arquitectura.md` §3)
```
backend/app/{domain,application,agents,providers,infrastructure,api,core}/ · backend/tests/{unit,contrato,integracion,api,agentes}/
```
Dirección de dependencias: `api → application → domain`; `infrastructure`, `providers` implementan puertos de `application/ports`; `agents` usa puertos, nunca adaptadores.

## Configuración (`core/config.py`)
`pydantic-settings` con `Settings(BaseSettings)`, `model_config = SettingsConfigDict(env_file=".env", extra="forbid")`. Validadores: en `ENV=production` exigir `APP_MASTER_KEY`, `JWT_SECRET` (≥ 32 bytes), `DEBUG=false`, `CORS_ORIGENES` no vacío. Nunca leer `os.environ` fuera de este módulo.

## Arranque (`main.py`)
```python
@asynccontextmanager
async def lifespan(app):
    await bootstrap_base_de_datos(settings)   # crea BD, lock, alembic, checkpointer, semillas
    app.state.registro = RegistroProveedores.desde_bd(...)
    yield
    await cerrar_recursos()
app = FastAPI(lifespan=lifespan, docs_url=None if settings.es_produccion else "/api/v1/docs")
```
Middlewares en este orden: CorrelationId → OTel → Cabeceras de seguridad → CORS (allowlist) → RateLimit (slowapi) → Tamaño máximo de body.

## Casos de uso
Clase por caso de uso en `application/use_cases/`, método `async def ejecutar(self, cmd: Comando) -> Resultado`. Dependencias por constructor (puertos). Sin FastAPI ni SQLAlchemy dentro. Transacción controlada por un `UnitOfWorkPort`.

## Repositorios
`infrastructure/db/repositorios/<entidad>.py` con SQLAlchemy 2 async (`select()`, `AsyncSession`). Sin SQL crudo salvo en migraciones o consultas de agregados documentadas (`text()` con parámetros). Paginación por cursor (`(fecha, id)`).

## Routers
```python
router = APIRouter(prefix="/cuentas", tags=["cuentas"])

@router.post("", status_code=201, response_model=CuentaOut, dependencies=[Depends(requiere_rol("admin"))])
@limiter.limit("10/minute")
async def crear_cuenta(body: CuentaIn, uc: CrearCuenta = Depends(dep_crear_cuenta), actor: Usuario = Depends(usuario_actual)):
    return await uc.ejecutar(body.a_comando(actor))
```
- Esquemas en `api/schemas/` con `model_config = ConfigDict(extra="forbid")`, `Field(max_length=...)` en todo string libre, `SecretStr` para secretos de entrada (nunca en salida).
- Errores de dominio → `ExcepcionDominio` → handler global que responde `application/problem+json` (`type`, `title`, `status`, `detail`, `instance`= correlation id). Nunca exponer trazas.
- Mutaciones: emitir `auditoria.registrar(actor, accion, entidad, id, diff_redactado)` dentro de la misma transacción.
- Idempotencia en `POST` de aprobación/envío: cabecera `Idempotency-Key` guardada 24 h.

## Autenticación
`core/seguridad.py`: `crear_access_token(usuario, jti)`, `verificar_access_token`, `hash_password`/`verificar_password` (argon2-cffi con parámetros de `docs/07-seguridad.md`). Refresh en cookie `HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`. `requiere_rol(*roles)` como dependencia. Autorización por recurso dentro del caso de uso.

## Logging y trazas
`structlog` JSON con procesador `redactar_secretos` (claves: password, secreto, token, authorization, api_key; emails parcialmente). `logger.bind(correlation_id, usuario_id, cuenta_id, mensaje_id)`. Spans OTel manuales en nodos del grafo y llamadas a proveedores (`with tracer.start_as_current_span("agente.clasificador")`).

## Salida de correo y webhooks (SSRF)
Antes de conectar a cualquier host configurado: resolver DNS, rechazar IP privadas/loopback/link-local salvo `RED_PRIVADA_PERMITIDA=true` + allowlist; timeout ≤ 10 s; sin seguir redirecciones en webhooks; TLS verificado.

## Comandos
```
cd backend
uv sync --all-extras --group dev
uv run uvicorn app.main:app --reload            # API
uv run python -m app.worker                     # worker
uv run ruff check . && uv run ruff format . && uv run pyrefly check
uv run pytest -q
uv run alembic revision --autogenerate -m "..." && uv run alembic upgrade head
```

## Anti-patrones que rechazamos
Lógica de negocio en routers · `Depends` con sesiones globales · `except Exception: pass` · `print` · devolver modelos ORM directamente · `datetime.now()` sin `ClockPort` en dominio · flags booleanos que cambian el comportamiento de una función (dividir en dos funciones).
