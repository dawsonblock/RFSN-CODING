# RFSN Sandbox Controller - Docker Environment
FROM python:3.11-slim AS builder

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy configuration
COPY pyproject.toml .
COPY README.md .
COPY rfsn_controller/ rfsn_controller/

# Create venv and install dependencies + project (non-editable for prod)
RUN uv venv
RUN uv pip install --no-cache ".[llm]"

# Final Stage
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code (needed if we want to run tests or access files, though installed in venv)
# Ideally, with non-editable install, code is in site-packages.
# However, `rfsn` entrypoint works.
# But let's keep source for transparency/verification if needed, or minimal image.
# We'll rely on the installed package in .venv.

# Create sandbox directory
RUN mkdir -p /sandbox

# Create non-root user
RUN useradd -m -u 1000 rfsn && \
    chown -R rfsn:rfsn /app /sandbox

USER rfsn

# Entrypoint using the installed console script
ENTRYPOINT ["rfsn"]
