.PHONY: help install dev migrate loaddata fixtures test lint format schema shell clean \
        docker-up docker-down docker-shell docker-logs docker-rebuild

PYTHON ?= .venv/bin/python
RUFF   ?= .venv/bin/ruff

# Default goal: print the menu.
help:
	@echo "Targets (run from vtf/api/):"
	@echo "  install        - create .venv and install requirements.txt"
	@echo "  dev            - run Django dev server on :8000"
	@echo "  migrate        - apply migrations"
	@echo "  loaddata       - load all catalog fixtures (idempotent on a clean DB)"
	@echo "  fixtures       - regenerate fixtures from vtf/front/src/mocks/"
	@echo "  test           - run pytest"
	@echo "  lint           - ruff check + ruff format --check"
	@echo "  format         - ruff format (writes)"
	@echo "  schema         - emit + validate OpenAPI schema (schema.yml)"
	@echo "  shell          - Django shell"
	@echo "  clean          - remove .data/, __pycache__, *.pyc"
	@echo "  docker-up      - docker compose up (from repo root)"
	@echo "  docker-down    - docker compose down"
	@echo "  docker-shell   - shell inside the api container"
	@echo "  docker-logs    - tail logs from the api container"
	@echo "  docker-rebuild - rebuild the api image"

install:
	./scripts/dev_setup.sh

dev:
	$(PYTHON) manage.py runserver 0.0.0.0:8000

migrate:
	$(PYTHON) manage.py migrate

loaddata:
	$(PYTHON) manage.py loaddata pricing_rules villages activities meals fuel_options promos

fixtures:
	$(PYTHON) scripts/build_fixtures_from_front_mocks.py

test:
	$(PYTHON) -m pytest

lint:
	$(RUFF) check apps config scripts
	$(RUFF) format --check apps config scripts

format:
	$(RUFF) format apps config scripts

schema:
	$(PYTHON) manage.py spectacular --file schema.yml --validate

shell:
	$(PYTHON) manage.py shell

clean:
	rm -rf .data
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete

docker-up:
	cd ../.. && docker compose up

docker-down:
	cd ../.. && docker compose down

docker-shell:
	cd ../.. && docker compose exec api bash

docker-logs:
	cd ../.. && docker compose logs -f api

docker-rebuild:
	cd ../.. && docker compose build api
