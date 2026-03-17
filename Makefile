.DEFAULT_GOAL := help

.PHONY: help install sync lint typecheck test run

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install deps + pre-commit hooks
	uv sync --all-extras
	pre-commit install

sync: ## Update packages & lock file
	uv sync --all-extras

lint: ## Run ruff linter + formatter
	uv run ruff check . --fix
	uv run ruff format .

typecheck: ## Run pyright + mypy
	uv run pyright
	uv run mypy src/macos_automator_mcp

test: ## Run tests
	uv run pytest

run: ## Start MCP server (stdio)
	uv run python -m macos_automator_mcp
