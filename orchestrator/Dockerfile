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

# Install uv for fast Python package management
RUN pip install --no-cache-dir uv

# Copy project configuration and lock files
COPY pyproject.toml uv.lock README.md ./

# Copy source code
COPY src/ ./src/

# Install the project and dependencies using uv
RUN uv pip install --system --no-cache .

# Create non-root user for security
RUN useradd -m -u 10001 orchestrator && chown -R orchestrator:orchestrator /app
USER orchestrator

# Expose port 8080 for Cloud Run / Vertex AI Agent Runtime
EXPOSE 8080

# Run the ADK orchestrator service
CMD ["python", "-m", "orchestrator.planner"]
