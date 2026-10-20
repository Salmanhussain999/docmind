# syntax=docker/dockerfile:1

# ---- Build the React app ----
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Python runtime: FastAPI serves the API and the built app ----
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --extra local

COPY backend/app ./app
COPY --from=web /web/dist ./web

ENV PATH="/app/.venv/bin:$PATH" \
    DATA_DIR=/data \
    WEB_DIST_DIR=/app/web \
    FASTEMBED_CACHE_PATH=/data/models

RUN useradd --create-home docmind && mkdir -p /data && chown docmind /data
USER docmind
VOLUME /data
EXPOSE 8000

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
