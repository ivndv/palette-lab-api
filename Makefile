# Comandos de desarrollo de palette-lab-api
.PHONY: help install dev test lint format docs docker-build docker-run

help: ## Muestra esta ayuda
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Crea el venv e instala dependencias de desarrollo
	uv venv .venv
	uv pip install --python .venv/bin/python -r requirements-dev.txt

dev: ## Arranca el servidor con recarga automática
	.venv/bin/uvicorn app.main:app --reload --port 8010

test: ## Corre los tests
	.venv/bin/pytest -q

lint: ## Revisa lint y formato (ruff)
	.venv/bin/ruff check .
	.venv/bin/ruff format --check .

format: ## Formatea el código
	.venv/bin/ruff format .

docs: ## Abre Swagger en el navegador
	xdg-open http://localhost:8010/docs

docker-build: ## Construye la imagen local
	docker build -t palette-lab-api .

docker-run: ## Corre la imagen local con el .env
	docker run --rm -p 8010:8000 --env-file .env palette-lab-api
