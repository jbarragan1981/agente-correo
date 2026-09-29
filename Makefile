.DEFAULT_GOAL := help
SHELL := /bin/bash
COMPOSE := docker compose -f infra/docker-compose.yml
COMPOSE_DEV := $(COMPOSE) -f infra/docker-compose.dev.yml
# Contraseñas locales evidentes solo si el usuario no las definió; la configuración base
# (infra/docker-compose.yml) no tiene valores por defecto (ADR-0008, observación M1).
DEV_ENV := POSTGRES_PASSWORD=$${POSTGRES_PASSWORD:-postgres} AGENTE_MIGRADOR_PASSWORD=$${AGENTE_MIGRADOR_PASSWORD:-migrador_local} AGENTE_APP_PASSWORD=$${AGENTE_APP_PASSWORD:-app_local}
SEMGREP_VERSION := 1.178.0

help: ## Lista los comandos
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

keys: ## Genera APP_MASTER_KEY y JWT_SECRET para tu .env local
	@python3 -c "import secrets,base64; print('APP_MASTER_KEY='+base64.b64encode(secrets.token_bytes(32)).decode()); print('JWT_SECRET='+secrets.token_urlsafe(48))"

db: ## PostgreSQL de desarrollo (127.0.0.1:5432)
	$(DEV_ENV) $(COMPOSE_DEV) up -d db

db-roles: ## Aplica roles.sql y contraseñas a un volumen de BD ya existente
	$(DEV_ENV) $(COMPOSE_DEV) exec -T db sh /docker-entrypoint-initdb.d/00-roles.sh

bootstrap: ## Crea/migra/siembra la BD local (idempotente)
	cd backend && uv run python -m app.bootstrap

dev: db bootstrap ## PostgreSQL + bootstrap; indica cómo arrancar API, worker y frontend
	@echo "API: cd backend && uv run uvicorn --factory app.main:crear_app --reload --no-server-header --no-access-log | Worker (E1.3): uv run python -m app.worker | Front (E0.4): cd frontend && npm start"

check: check-backend check-frontend marcar-verificado ## Todo lo que corre CI (rápido, sin contenedores)

check-backend: ## ruff + pyrefly + pytest rápido
	@if [ -f backend/pyproject.toml ]; then cd backend && uv run ruff check . && uv run ruff format --check . && uv run pyrefly check && uv run pytest -q -m "not integracion and not e2e and not eval"; else echo "backend no inicializado"; fi

NODE_FRONT := $(shell cat frontend/.nvmrc 2>/dev/null)
NPM_FRONT  := $(shell node -e "const [a,b,c]=process.versions.node.split('.').map(Number);process.stdout.write(a>22||(a===22&&(b>22||(b===22&&c>=3)))?'npm':'npx -y -p node@$(NODE_FRONT) -- npm')" 2>/dev/null)

check-frontend: ## eslint + tsc + vitest + build + i18n (Node >= 22.22.3; ver frontend/.nvmrc)
	@if [ -f frontend/package.json ]; then cd frontend && $(NPM_FRONT) run verificar; else echo "frontend no inicializado"; fi

test-int: ## Integración con PostgreSQL efímero (PRUEBAS_PG_DSN, Docker o binarios locales)
	cd backend && uv run pytest -q -m integracion

security: ## SAST y auditorías de dependencias
	@if [ -f backend/pyproject.toml ]; then cd backend && uv run bandit -q -r app -ll && uv run pip-audit && uvx semgrep@$(SEMGREP_VERSION) --config p/owasp-top-ten --config p/python --error app; fi
	@if [ -f frontend/package.json ]; then cd frontend && npm audit --audit-level=high; fi
	@command -v gitleaks >/dev/null && gitleaks detect --no-git -s . --redact || echo "gitleaks no instalado (opcional)"

e2e: ## Compose completo con proveedores falsos + Playwright
	FAKE_PROVIDERS=true $(DEV_ENV) $(COMPOSE_DEV) up -d --build && cd frontend && npx playwright test

evals: ## Evaluación del clasificador (requiere claves de staging)
	cd backend && uv run python -m evals.clasificador --motor jev --limite 300

marcar-verificado: ## Actualiza la marca usada por el hook de Stop de Claude Code
	@mkdir -p .claude && touch .claude/.ultima-verificacion

down: ## Detiene los contenedores (conserva volúmenes)
	$(DEV_ENV) $(COMPOSE_DEV) down

.PHONY: help keys db db-roles bootstrap dev check check-backend check-frontend test-int security e2e evals marcar-verificado down
