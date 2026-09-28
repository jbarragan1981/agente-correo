.DEFAULT_GOAL := help
SHELL := /bin/bash
COMPOSE := docker compose -f infra/docker-compose.yml

help: ## Lista los comandos
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

keys: ## Genera APP_MASTER_KEY y JWT_SECRET para tu .env local
	@python3 -c "import secrets,base64; print('APP_MASTER_KEY='+base64.b64encode(secrets.token_bytes(32)).decode()); print('JWT_SECRET='+secrets.token_urlsafe(48))"

db: ## Levanta solo PostgreSQL
	$(COMPOSE) up -d db

dev: db ## PostgreSQL + API con recarga + worker + frontend
	@echo "API: cd backend && uv run uvicorn app.main:app --reload | Worker: uv run python -m app.worker | Front: cd frontend && npm start"

check: check-backend check-frontend marcar-verificado ## Todo lo que corre CI (rápido, sin contenedores)

check-backend: ## ruff + pyrefly + pytest rápido
	@if [ -f backend/pyproject.toml ]; then cd backend && uv run ruff check . && uv run ruff format --check . && uv run pyrefly check && uv run pytest -q -m "not integracion and not e2e and not eval"; else echo "backend no inicializado"; fi

check-frontend: ## eslint + tsc + vitest + build
	@if [ -f frontend/package.json ]; then cd frontend && npm run lint && npx tsc --noEmit -p tsconfig.app.json && npm run test -- --run && npm run build -- --configuration production; else echo "frontend no inicializado"; fi

test-int: ## Pruebas de integración con contenedores
	cd backend && uv run pytest -q -m integracion

security: ## SAST y auditorías de dependencias
	@if [ -f backend/pyproject.toml ]; then cd backend && uv run bandit -q -r app -ll && uv run pip-audit && uv run semgrep --config p/owasp-top-ten --config p/python --error app; fi
	@if [ -f frontend/package.json ]; then cd frontend && npm audit --audit-level=high; fi
	@command -v gitleaks >/dev/null && gitleaks detect --no-git -s . --redact || echo "gitleaks no instalado (opcional)"

e2e: ## Compose completo con proveedores falsos + Playwright
	FAKE_PROVIDERS=true $(COMPOSE) up -d --build && cd frontend && npx playwright test

evals: ## Evaluación del clasificador (requiere claves de staging)
	cd backend && uv run python -m evals.clasificador --motor jev --limite 300

marcar-verificado: ## Actualiza la marca usada por el hook de Stop de Claude Code
	@mkdir -p .claude && touch .claude/.ultima-verificacion

down: ## Detiene los contenedores (conserva volúmenes)
	$(COMPOSE) down

.PHONY: help keys db dev check check-backend check-frontend test-int security e2e evals marcar-verificado down
