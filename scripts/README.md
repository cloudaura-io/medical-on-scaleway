# Scripts

Helper scripts for provisioning, configuring, and validating the workshop environment.

## Usage Order

```
setup.sh → (develop) → teardown.sh
```

`setup.sh` orchestrates everything below automatically. Individual scripts can be run standalone if needed.

## Scripts

| Script | Description |
|---|---|
| `setup.sh` | Full project setup: provisions infra, generates `.env`, inits DB, creates venv, loads knowledge base, validates services. Use `--skip-tofu` / `--skip-knowledge` to skip steps. |
| `teardown.sh` | Destroys all Scaleway resources (DB, bucket, inference) and cleans up `.env`. Use `--auto` to skip confirmation. |
| `generate-env.sh` | Generates `.env` from OpenTofu outputs and `.tfvars` credentials. Backs up existing `.env` before overwriting. |
| `init-db.sh` | Runs `infrastructure/init-db.sql` against PostgreSQL — creates pgvector extension, tables, and indexes. Reads `DATABASE_URL` from `.env`. |
| `load-knowledge-base.py` | Chunks Markdown files from `data/knowledge_base/`, generates embeddings via Managed Inference, and stores them in pgvector. Use `--dry-run` to preview, `--clear` to reload. |
| `validate.py` | Tests all infrastructure components (APIs, DB, pgvector, S3). Use `-v` for verbose output. Exits with code 1 on failure. |

## Prerequisites

- Python 3.11+
- `psql` (PostgreSQL client)
- `tofu` (OpenTofu) — only for provisioning
- Scaleway credentials in `infrastructure/terraform.tfvars`
