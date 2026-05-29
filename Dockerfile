FROM python:3.13-slim

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Put the venv outside the bind-mount path so dev volume mounts don't shadow it
ENV UV_PROJECT_ENVIRONMENT=/venv

# Install dependencies as a separate layer (rebuilt only when lockfile changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

# Copy source (overridden by bind mount in dev; present for CI/production)
COPY . .
