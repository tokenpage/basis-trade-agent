.PHONY: setup run lint lint-fix test

setup:
	uv sync

run:
	uv run python -m basis_trade_agent.main --config config.yaml

lint:
	uv run ruff check .

lint-fix:
	uv run ruff check --fix . && uv run ruff format .

test:
	uv run pytest
