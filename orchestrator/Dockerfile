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

# Stage 2: Distroless hardened minimal runtime
FROM gcr.io/distroless/cc-debian12:nonroot AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:/usr/local/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV SKILLS_DIR=/app/skills
ENV GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES=false
ENV GOOGLE_GENAI_USE_ENTERPRISE=true
ENV AGENT_REGISTRY_LOCATION=global
ENV GOOGLE_CLOUD_LOCATION=us-central1

# Copy system shared libraries required by Python C extensions
COPY --from=builder /lib/x86_64-linux-gnu /lib/x86_64-linux-gnu
COPY --from=builder /usr/lib/x86_64-linux-gnu /usr/lib/x86_64-linux-gnu

# Copy Python 3.12 runtime and virtual environment
COPY --from=builder /usr/local /usr/local
COPY --from=builder /opt/venv /opt/venv

# Copy runtime skills and source code
COPY orchestrator/src/ ./src/
COPY skills/ ./skills/

# Expose port 8080 for Agent Platform Agent Runtime custom-container serving.
EXPOSE 8080

# Serve the ADK planner over HTTP so Agent Runtime can invoke it.
ENTRYPOINT ["python3", "-m", "uvicorn", "orchestrator.server:app", "--host", "0.0.0.0", "--port", "8080"]
