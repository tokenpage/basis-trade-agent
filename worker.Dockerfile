FROM python:3.14.6-slim

RUN apt-get update && apt-get install --yes --no-install-recommends make git gcc libc6-dev

WORKDIR /app
COPY pyproject.toml .
COPY uv.lock .
RUN pip install uv && uv sync --active --all-extras

COPY . .

CMD ["sh", "-lc", "uv run --active python main.py --config ${BASIS_TRADE_CONFIG_PATH:-/app/shared/config.yaml}"]
