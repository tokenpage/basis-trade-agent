install:
	@ pip install uv
	@ uv sync --active --all-extras

install-updates:
	@ pip install uv
	@ uv sync --active --upgrade --refresh --all-extras

list-outdated: install
	@ pip list -o

main:
	uv run --active main.py --config config.yaml

agent:
	uv run --active agent.py

lint:
	uv run --active ruff check .

lint-fix:
	uv run --active ruff check --fix . && uv run ruff format .

test:
	uv run --active pytest
