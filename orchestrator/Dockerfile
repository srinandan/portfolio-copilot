# Stage 1: Build virtual environment with all dependencies
FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install and upgrade packaging tools in builder stage
RUN pip install --no-cache-dir --upgrade "pip>=26.1.2" uv

# Create a clean virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy project configuration files
COPY orchestrator/pyproject.toml orchestrator/uv.lock orchestrator/README.md ./
COPY orchestrator/src/ ./src/

# Install the project and dependencies into /opt/venv
RUN uv pip install --no-cache .

# Stage 2: Hardened minimal runtime
FROM python:3.12-slim-bookworm AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"
ENV SKILLS_DIR=/app/skills
ENV GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES=false
ENV GOOGLE_GENAI_USE_ENTERPRISE=true
ENV AGENT_REGISTRY_LOCATION=global
ENV GOOGLE_CLOUD_LOCATION=us-central1

# Apply OS-level security updates, upgrade pip, and clean package cache
RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir --upgrade "pip>=26.1.2"

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy runtime skills and source code
COPY orchestrator/src/ ./src/
COPY skills/ ./skills/

# Create non-root user for security
RUN useradd -m -u 10001 orchestrator && chown -R orchestrator:orchestrator /app
USER orchestrator

# Expose port 8080 for Agent Platform Agent Runtime custom-container serving.
# Agent Runtime probes /livez + /readyz and proxies query requests to the container.
EXPOSE 8080

# Serve the ADK planner over HTTP so Agent Runtime can invoke it.
# PORT is honored (Agent Runtime may set it); default 8080.
CMD ["sh", "-c", "uvicorn orchestrator.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
