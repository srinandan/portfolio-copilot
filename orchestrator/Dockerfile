# Build and runtime stage
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install required system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Download the specific version (e.g., 1.7.1) and make it executable
RUN curl -L -o /usr/local/bin/jq https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-linux64 && \
    chmod +x /usr/local/bin/jq

# Install uv for fast Python package management
RUN pip install --no-cache-dir uv

# Copy project configuration and lock files
COPY orchestrator/pyproject.toml orchestrator/uv.lock orchestrator/README.md ./

# Copy source code and runtime skills
COPY orchestrator/src/ ./src/
COPY skills/ ./skills/

ENV SKILLS_DIR=/app/skills
ENV GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES=false
ENV GOOGLE_GENAI_USE_ENTERPRISE=true
ENV AGENT_REGISTRY_LOCATION=global
ENV GOOGLE_CLOUD_LOCATION=us-central1

# Install the project and dependencies using uv
RUN uv pip install --system --no-cache .

# Create non-root user for security
RUN useradd -m -u 10001 orchestrator && chown -R orchestrator:orchestrator /app
USER orchestrator

# Expose port 8080 for Agent Platform Agent Runtime custom-container serving.
# Agent Runtime probes /livez + /readyz and proxies query requests to the container.
EXPOSE 8080

# Serve the ADK planner over HTTP so Agent Runtime can invoke it.
# PORT is honored (Agent Runtime may set it); default 8080.
CMD ["sh", "-c", "uvicorn orchestrator.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
