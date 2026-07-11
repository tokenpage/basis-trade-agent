FROM python:3.14.6-slim

RUN apt-get update && apt-get install --yes --no-install-recommends make git gcc libc6-dev

WORKDIR /app
COPY pyproject.toml .
COPY uv.lock .
RUN pip install uv && uv sync --active --all-extras

COPY . .

EXPOSE 5001
CMD ["uv", "run", "--active", "uvicorn", "application:app", "--host", "0.0.0.0", "--port", "5001", "--no-access-log"]
