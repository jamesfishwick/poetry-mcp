.PHONY: format lint typecheck test check

format:
	uv run ruff format src/ tests/

lint:
	uv run ruff check src/ tests/

typecheck:
	uv run mypy src

test:
	uv run pytest

# Mirrors CI (mypy is advisory, not gating).
check: lint test
	uv run ruff format --check src/ tests/
