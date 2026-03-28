#!/usr/bin/env bash
################################################################################
# Generate .env from OpenTofu outputs
#
# Reads outputs from the OpenTofu state and writes a complete .env file.
# If .env already exists, creates a backup before overwriting.
#
# Usage:
#   ./scripts/generate-env.sh
################################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$PROJECT_ROOT/infrastructure"
ENV_FILE="$PROJECT_ROOT/.env"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ─────────────────────────────────────────────────────────────────────────────
# OpenTofu outputs
# ─────────────────────────────────────────────────────────────────────────────

get_tf_output() {
    local key="$1"
    (cd "$INFRA_DIR" && tofu output -raw "$key" 2>/dev/null) || true
}

echo "Reading OpenTofu outputs..."

DATABASE_URL=$(get_tf_output "database_connection_url")
DB_HOST=$(get_tf_output "database_host")
DB_PORT=$(get_tf_output "database_port")
INFERENCE_ENDPOINT=$(get_tf_output "inference_endpoint")
BUCKET_NAME=$(get_tf_output "object_storage_bucket_name")
VOXTRAL_REALTIME_ENDPOINT=$(get_tf_output "voxtral_realtime_endpoint")

# Read Scaleway credentials from any .tfvars file in infrastructure/
get_tfvar() {
    grep -h "^${1}" "$INFRA_DIR"/*.tfvars 2>/dev/null \
        | head -1 | sed 's/.*=\s*"\(.*\)"/\1/'
}

SCW_ACCESS_KEY=$(get_tfvar "access_key")
SCW_SECRET_KEY=$(get_tfvar "secret_key")
SCW_PROJECT_ID=$(get_tfvar "project_id")

# ─────────────────────────────────────────────────────────────────────────────
# Validate
# ─────────────────────────────────────────────────────────────────────────────

MISSING=0
check_var() {
    if [ -z "${!1:-}" ]; then
        echo -e "  ${RED}✗ $1 is empty${NC}"
        MISSING=$((MISSING + 1))
    else
        echo -e "  ${GREEN}✓${NC} $1"
    fi
}

echo "Validating outputs..."
check_var DATABASE_URL
check_var INFERENCE_ENDPOINT
check_var VOXTRAL_REALTIME_ENDPOINT
check_var BUCKET_NAME
check_var SCW_ACCESS_KEY
check_var SCW_SECRET_KEY
check_var SCW_PROJECT_ID

if [ "$MISSING" -gt 0 ]; then
    echo -e "\n${RED}$MISSING variable(s) missing. Check OpenTofu state and tfvars.${NC}"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# Write .env
# ─────────────────────────────────────────────────────────────────────────────

if [ -f "$ENV_FILE" ]; then
    BACKUP="${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$ENV_FILE" "$BACKUP"
    echo -e "${YELLOW}Existing .env backed up to: $(basename "$BACKUP")${NC}"
fi

cat > "$ENV_FILE" <<EOF
# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  Scaleway Medical AI Lab — Environment Configuration                     ║
# ║  Generated: $(date -Iseconds)                              ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

# Scaleway API credentials
SCW_ACCESS_KEY=${SCW_ACCESS_KEY}
SCW_SECRET_KEY=${SCW_SECRET_KEY}
SCW_PROJECT_ID=${SCW_PROJECT_ID}

# Scaleway Generative APIs (chat, STT, vision — serverless, no provisioning)
SCW_GENERATIVE_API_URL=https://api.scaleway.ai/v1

# Scaleway Managed Inference (BGE embeddings on dedicated L4 GPU)
SCW_INFERENCE_ENDPOINT=${INFERENCE_ENDPOINT}

# Scaleway Managed Inference (Voxtral Realtime STT on dedicated L4 GPU)
SCW_VOXTRAL_REALTIME_ENDPOINT=${VOXTRAL_REALTIME_ENDPOINT}

# PostgreSQL + pgvector (from OpenTofu)
DATABASE_URL=${DATABASE_URL}

# Object Storage — S3-compatible (from OpenTofu)
SCW_S3_ENDPOINT=https://s3.fr-par.scw.cloud
SCW_S3_BUCKET=${BUCKET_NAME}
EOF

echo -e "${GREEN}.env written to: $ENV_FILE${NC}"
