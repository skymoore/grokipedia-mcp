FROM python:3.14-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project config
COPY pyproject.toml .
COPY uv.lock .
COPY README.md .
COPY LICENSE .

# Copy source code
COPY grokipedia_mcp ./grokipedia_mcp

ENV UV_COMPILE_BYTECODE=1

# Build and install
RUN uv build && \
  uv pip install --system dist/*.whl

LABEL org.opencontainers.image.description="Grokipedia MCP Server"

# Start the server
ENTRYPOINT ["grokipedia-mcp"]
