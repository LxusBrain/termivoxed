# TermiVoxed Makefile
# Author: Santhosh T / LxusBrain
#
# Common development commands for the project
# Usage: make <command>

.PHONY: help install install-dev lint format test test-unit test-integration \
        coverage build docker-build docker-run clean frontend-install frontend-build \
        frontend-dev pre-commit security-scan docs serve

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[34m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

# Python and Node versions
PYTHON := python3
NODE := node
NPM := npm

# Directories
BACKEND_DIRS := backend core models subscription web_ui/api
FRONTEND_DIR := web_ui/frontend
TESTS_DIR := tests

# ============================================================================
# Help
# ============================================================================

help: ## Show this help message
	@echo ""
	@echo "$(BLUE)TermiVoxed Development Commands$(RESET)"
	@echo "================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ============================================================================
# Installation
# ============================================================================

install: ## Install production dependencies
	@echo "$(BLUE)Installing production dependencies...$(RESET)"
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

install-dev: install ## Install development dependencies
	@echo "$(BLUE)Installing development dependencies...$(RESET)"
	$(PYTHON) -m pip install pytest pytest-asyncio pytest-cov pytest-mock httpx
	$(PYTHON) -m pip install black flake8 isort mypy bandit safety
	$(PYTHON) -m pip install pre-commit
	pre-commit install
	@echo "$(GREEN)Development environment ready!$(RESET)"

install-all: install-dev frontend-install ## Install all dependencies (backend + frontend)
	@echo "$(GREEN)All dependencies installed!$(RESET)"

# ============================================================================
# Code Quality
# ============================================================================

lint: ## Run all linters
	@echo "$(BLUE)Running linters...$(RESET)"
	@echo "$(YELLOW)Running flake8...$(RESET)"
	flake8 $(BACKEND_DIRS) --max-line-length=120 --max-complexity=15 --exclude=__pycache__,venv
	@echo "$(YELLOW)Running mypy...$(RESET)"
	mypy $(BACKEND_DIRS) --ignore-missing-imports || true
	@echo "$(GREEN)Linting complete!$(RESET)"

format: ## Format code with black and isort
	@echo "$(BLUE)Formatting code...$(RESET)"
	@echo "$(YELLOW)Running isort...$(RESET)"
	isort $(BACKEND_DIRS) $(TESTS_DIR) --profile=black --line-length=100
	@echo "$(YELLOW)Running black...$(RESET)"
	black $(BACKEND_DIRS) $(TESTS_DIR) --line-length=100
	@echo "$(GREEN)Formatting complete!$(RESET)"

format-check: ## Check code formatting without making changes
	@echo "$(BLUE)Checking code formatting...$(RESET)"
	black --check --diff $(BACKEND_DIRS) $(TESTS_DIR) --line-length=100
	isort --check-only --diff $(BACKEND_DIRS) $(TESTS_DIR) --profile=black --line-length=100

pre-commit: ## Run pre-commit hooks on all files
	@echo "$(BLUE)Running pre-commit hooks...$(RESET)"
	pre-commit run --all-files

# ============================================================================
# Testing
# ============================================================================

test: ## Run all tests
	@echo "$(BLUE)Running all tests...$(RESET)"
	PYTHONPATH=. pytest $(TESTS_DIR) -v --tb=short

test-unit: ## Run unit tests only
	@echo "$(BLUE)Running unit tests...$(RESET)"
	PYTHONPATH=. pytest $(TESTS_DIR) -v --tb=short -m "not slow and not integration"

test-integration: ## Run integration tests only
	@echo "$(BLUE)Running integration tests...$(RESET)"
	PYTHONPATH=. pytest $(TESTS_DIR) -v --tb=short -m "integration"

test-fast: ## Run fast tests only (skip slow tests)
	@echo "$(BLUE)Running fast tests...$(RESET)"
	PYTHONPATH=. pytest $(TESTS_DIR) -v --tb=short -m "not slow" --timeout=60

coverage: ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(RESET)"
	PYTHONPATH=. pytest $(TESTS_DIR) -v \
		--cov=backend \
		--cov=core \
		--cov=models \
		--cov=subscription \
		--cov-report=html \
		--cov-report=term-missing \
		--cov-fail-under=50
	@echo "$(GREEN)Coverage report generated in htmlcov/$(RESET)"

# ============================================================================
# Security
# ============================================================================

security-scan: ## Run security scans
	@echo "$(BLUE)Running security scans...$(RESET)"
	@echo "$(YELLOW)Running safety (dependency vulnerabilities)...$(RESET)"
	safety check --full-report || true
	@echo "$(YELLOW)Running bandit (code security)...$(RESET)"
	bandit -r $(BACKEND_DIRS) -ll --exclude '**/tests/**' || true
	@echo "$(GREEN)Security scan complete!$(RESET)"

# ============================================================================
# Frontend
# ============================================================================

frontend-install: ## Install frontend dependencies
	@echo "$(BLUE)Installing frontend dependencies...$(RESET)"
	cd $(FRONTEND_DIR) && $(NPM) ci

frontend-build: ## Build frontend for production
	@echo "$(BLUE)Building frontend...$(RESET)"
	cd $(FRONTEND_DIR) && $(NPM) run build
	@echo "$(GREEN)Frontend built in $(FRONTEND_DIR)/dist$(RESET)"

frontend-dev: ## Start frontend development server
	@echo "$(BLUE)Starting frontend dev server...$(RESET)"
	cd $(FRONTEND_DIR) && $(NPM) run dev

frontend-lint: ## Lint frontend code
	@echo "$(BLUE)Linting frontend...$(RESET)"
	cd $(FRONTEND_DIR) && npx tsc --noEmit

# ============================================================================
# Docker
# ============================================================================

docker-build: ## Build Docker image
	@echo "$(BLUE)Building Docker image...$(RESET)"
	docker build -t termivoxed:latest .
	@echo "$(GREEN)Docker image built: termivoxed:latest$(RESET)"

docker-run: ## Run Docker container
	@echo "$(BLUE)Running Docker container...$(RESET)"
	docker-compose up

docker-run-detached: ## Run Docker container in detached mode
	@echo "$(BLUE)Running Docker container (detached)...$(RESET)"
	docker-compose up -d
	@echo "$(GREEN)Container running. Access at http://localhost:8000$(RESET)"

docker-stop: ## Stop Docker containers
	@echo "$(BLUE)Stopping Docker containers...$(RESET)"
	docker-compose down

docker-logs: ## View Docker container logs
	docker-compose logs -f

docker-shell: ## Open shell in Docker container
	docker-compose exec termivoxed /bin/bash

# ============================================================================
# Development Server
# ============================================================================

serve: ## Start the development server
	@echo "$(BLUE)Starting development server...$(RESET)"
	PYTHONPATH=. $(PYTHON) -m uvicorn web_ui.api.main:app --reload --host 0.0.0.0 --port 8000

serve-prod: ## Start production server
	@echo "$(BLUE)Starting production server...$(RESET)"
	PYTHONPATH=. $(PYTHON) -m uvicorn web_ui.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# ============================================================================
# Build & Release
# ============================================================================

build: frontend-build ## Build the application
	@echo "$(BLUE)Building application...$(RESET)"
	$(PYTHON) -m build
	@echo "$(GREEN)Build complete! Check dist/ directory$(RESET)"

clean: ## Clean build artifacts
	@echo "$(BLUE)Cleaning build artifacts...$(RESET)"
	rm -rf build/ dist/ *.egg-info/
	rm -rf .pytest_cache/ .mypy_cache/ .coverage htmlcov/
	rm -rf $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/node_modules/.cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)Clean complete!$(RESET)"

# ============================================================================
# Documentation
# ============================================================================

docs: ## Generate documentation
	@echo "$(BLUE)Generating documentation...$(RESET)"
	@echo "$(YELLOW)Documentation generation not yet configured$(RESET)"

# ============================================================================
# CI/CD Simulation
# ============================================================================

ci: format-check lint test-unit ## Run CI checks locally
	@echo "$(GREEN)All CI checks passed!$(RESET)"

ci-full: format-check lint test coverage security-scan docker-build ## Run full CI pipeline locally
	@echo "$(GREEN)Full CI pipeline passed!$(RESET)"
