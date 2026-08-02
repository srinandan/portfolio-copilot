# 12. Structured Logging across all components

Date: 2024-05-18

## Status

Accepted

## Context

Observability is a crucial requirement for microservice and agent-based architectures. The Portfolio Copilot project relies on Google Cloud Run and the Gemini Enterprise Agent Platform. To correctly view, trace, and alert on application behavior, logs need to be parsed, queryable, and correlated across different parts of the system (e.g. Gateway to Orchestrator to Skills). Text-based or simple `print` statements make it difficult to query fields like latency, user_id, or trace IDs, and do not conform to Google Cloud Logging expectations.

## Decision

We will always implement structured JSON logging across all backend and agent components.
Specifically:
- In Go (Gateway and Packages), we will use the standard library `log/slog` with a JSON handler.
- In Python (Orchestrator and Skills), we will use the standard `logging` library configured to output JSON.
- We will rely on HTTP trace propagation headers (`X-Request-ID`, `X-Cloud-Trace-Context`, or `traceparent`) and propagate them to the logs.
- In Go, we will extract headers in middleware and use the `context.Context` to propagate values.
- In Python, we will use `contextvars` to store trace IDs and inject them dynamically into log records, making correlation transparent to the skill implementations.
- Log levels must be configurable via the `LOG_LEVEL` environment variable.
- We will avoid logging sensitive PII or credentials.

## Consequences

- **Positive:** Improved observability and compatibility with Google Cloud Logging. Easy filtering of logs by trace context across the entire stack. Standardized approach reduces friction for developers.
- **Negative:** Slightly more verbose setup compared to simple `fmt.Println` or `print()`. Development mode might require pretty-printing tools to easily read JSON logs on a local console, though most tools support this natively.
