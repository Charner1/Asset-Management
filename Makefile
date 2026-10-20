PYTHON ?= python3.12
VENV   := .venv
BIN    := $(VENV)/bin
# Newest release date allowed in lock files: today minus 14 days (ADR 0011).
CUTOFF ?= $(shell date -u -d '14 days ago' +%Y-%m-%d)

.PHONY: dev lock test lint scan clean

dev: ## Create venv, install hash-locked deps, install pre-commit hooks
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --require-hashes --no-deps -r requirements-dev.lock
	$(BIN)/pip install --no-deps --no-build-isolation -e .
	$(BIN)/pre-commit install

lock: ## Re-resolve lock files with the 14-day cutoff (needs uv)
	uv pip compile pyproject.toml --python-version 3.12 --exclude-newer $(CUTOFF) \
		--generate-hashes --custom-compile-command "make lock" -o requirements.lock
	uv pip compile pyproject.toml --extra dev --python-version 3.12 --exclude-newer $(CUTOFF) \
		--generate-hashes --custom-compile-command "make lock" -o requirements-dev.lock

test: ## Run tests with coverage (fails under 80%)
	$(BIN)/pytest

lint: ## Lint, format check, type check
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .
	$(BIN)/mypy

scan: ## Secret scan of the full git history
	$(BIN)/pre-commit run gitleaks --all-files
	gitleaks git --redact --verbose .

clean:
	rm -rf $(VENV) .mypy_cache .ruff_cache .pytest_cache .coverage htmlcov build dist src/*.egg-info
