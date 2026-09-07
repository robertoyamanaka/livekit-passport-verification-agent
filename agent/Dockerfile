# syntax=docker/dockerfile:1

# Use the official UV Python base image with Python 3.13 on Debian Bookworm.
# UV is a fast Python package manager that provides better performance than pip.
# We use the slim variant to keep the image size smaller while still having essential tools.
ARG PYTHON_VERSION=3.13
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim AS base

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

# Compile Python source to bytecode (.pyc) during install so the first import
# doesn't pay the compilation cost. This reduces agent cold-start time at the
# expense of a slightly longer build.
ENV UV_COMPILE_BYTECODE=1

# --- Build stage ---
# Install dependencies, build native extensions, and prepare the application.
FROM base AS build

# Build dependencies required for Python packages with native extensions
# (e.g. reportlab's font/image handling). Cleaned up in the production stage,
# which is built FROM base, not FROM build.
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy just the dependency files first, for more efficient layer caching.
COPY pyproject.toml uv.lock ./

# --locked ensures we use exact versions from uv.lock for reproducible builds.
RUN uv sync --locked

# Copy the rest of the application source (respects .dockerignore).
COPY . .

# --- Production stage ---
# Build tools (gcc, g++, python3-dev) are not included in the final image.
FROM base

# Create a non-privileged user that the app runs under.
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/app" \
    --shell "/sbin/nologin" \
    --uid "${UID}" \
    appuser

WORKDIR /app

# Copy the application and virtual environment with correct ownership in a
# single layer, avoiding an expensive recursive chown.
COPY --from=build --chown=appuser:appuser /app /app

USER appuser

# LiveKit Cloud injects LIVEKIT_URL/LIVEKIT_API_KEY/LIVEKIT_API_SECRET at
# runtime — they must not be set here. OPENAI_API_KEY/RESEND_API_KEY are
# pushed separately via `lk agent update-secrets`.
#
# The entrypoint lives at src/agent.py (not the repo root), unlike the
# stock LiveKit CLI template this Dockerfile is otherwise based on.
CMD ["uv", "run", "src/agent.py", "start"]
