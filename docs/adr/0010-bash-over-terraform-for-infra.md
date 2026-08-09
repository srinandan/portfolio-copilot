# ADR 0010: Bash/gcloud over Terraform for infrastructure provisioning

## Status
Accepted

## Context
The project requires setting up various GCP infrastructure components like BigQuery datasets, Firestore, Cloud Run services, Secret Manager secrets, and Agent Engine configurations. Initially, the plan indicated using Terraform in an `infra/` folder. However, for scaffolding and provisioning these basic components, Terraform was found to be too complex and heavy for what are mostly one-time initialization scripts and straightforward setup commands.

## Decision
We will use simple `bash` scripts leveraging `gcloud` CLI, `bq`, and Python scripts (with Agent Platform SDK) instead of Terraform. These scripts will be consolidated into the `scripts/` directory, and the `infra/` directory will be removed. Makefiles may also be used to wrap these scripts if convenient.

## Consequences
- **Pros:** Faster onboarding, simpler to execute, less state management overhead (no tfstate files), easier to integrate into simple CI/CD or local setup workflows.
- **Cons:** Less robust drift detection, not fully declarative (though scripts should be written idempotently where possible).
