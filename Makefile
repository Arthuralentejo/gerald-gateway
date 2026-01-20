
.PHONY: help install install-dev lint lint-fix format \
        test test-unit test-integration test-fast coverage \
        run \
        docker-up docker-down docker-logs \
        db-up db-down \
        mock-up mock-down clean openapi

help:
	@echo "Gerald Gateway - BNPL Approval Service"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Development:"
	@echo "  install        Install dependencies"
	@echo "  install-dev    Install development dependencies"
	@echo "  lint           Run linters (ruff, mypy)"
	@echo "  lint-fix       Auto-fix linting issues"
	@echo "  format         Format code with black and ruff"
	@echo ""
	@echo "Testing:"
	@echo "  test           Run all tests"
	@echo "  test-unit      Run unit tests only"
	@echo "  test-integration  Run integration tests only"
	@echo "  test-fast      Run tests, stop on first failure"
	@echo "  coverage       Run tests with coverage report"
	@echo ""
	@echo "Running:"
	@echo "  run            Run the server"
	@echo ""
	@echo "Docker:"
	@echo "  docker-up      Start app + database with Docker Compose"
	@echo "  docker-down    Stop all Docker services"
	@echo "  docker-logs    View Docker Compose logs"
	@echo ""
	@echo "Database:"
	@echo "  db-up          Start PostgreSQL only"
	@echo "  db-down        Stop PostgreSQL"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean          Remove build artifacts and cache"

# =====================================
# Installation
# =====================================

install:
	poetry install

install-dev:
	poetry install --with dev

# =====================================
# Code Quality
# =====================================

lint:
	@echo "Running ruff linter..."
	ruff check src/ tests/
	@echo "Running mypy type checker..."
	mypy src/ --ignore-missing-imports

lint-fix:
	@echo "Fixing linting issues..."
	ruff check --fix src/ tests/

format:
	@echo "Formatting code with black..."
	black src/ tests/
	@echo "Sorting imports with ruff..."
	ruff check --select I --fix src/ tests/


# =====================================
# Testing
# =====================================

test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-fast:
	pytest tests/ -v -x --ff

coverage:
	pytest tests/ --cov=src --cov-report=html
	@echo "Coverage report generated at htmlcov/index.html"

# =====================================
# Running (Local)
# =====================================

run:
	uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# =====================================
# Docker
# =====================================

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

# =====================================
# Database
# =====================================

db-up:
	docker compose up -d db

db-down:
	docker compose stop db


# =====================================
# Mock Services
# =====================================

mock-up:
	@echo "Starting mock services..."
	docker compose -f assets/docker-compose.yml up -d 2>/dev/null || echo "mock docker-compose.yml not found"

mock-down:
	docker compose -f assets/docker-compose.yml down 2>/dev/null || true

# =====================================
# Maintenance
# =====================================

clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "Clean complete"


# =====================================
# Documentation
# =====================================

openapi:
	python -c "import json; from src.main import app; print(json.dumps(app.openapi(), indent=2))" > openapi.json
	@echo "OpenAPI spec exported to openapi.json"
