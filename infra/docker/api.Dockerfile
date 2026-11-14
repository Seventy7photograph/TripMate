FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/apps/api/.venv/bin:$PATH"

RUN pip install --no-cache-dir uv==0.9.5

WORKDIR /app
COPY apps/api/pyproject.toml apps/api/uv.lock ./apps/api/
WORKDIR /app/apps/api
RUN uv sync --frozen --no-dev

COPY apps/api ./
EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
