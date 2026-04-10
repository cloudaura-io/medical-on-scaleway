#!/usr/bin/env bash
################################################################################
# Scaleway Medical AI Lab - Full Infrastructure Setup
#
#   1. Check prerequisites
#   2. Provision infrastructure with OpenTofu
#   3. Build and push Docker images to Scaleway Container Registry
#   4. Generate .env from OpenTofu outputs
#   5. Database and knowledge base (schema created lazily by backend)
#   6. Wait for application services to start
#
# Architecture: VPC-enclosed with Public Load Balancer + Container Registry.
# All three showcases run as pre-built Docker images on a single instance.
# Database schema is initialized automatically via cloud-init.
################################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$PROJECT_ROOT/infrastructure"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SKIP_TOFU=false

for arg in "$@"; do
    case "$arg" in
        --skip-tofu) SKIP_TOFU=true ;;
        --help|-h)
            echo "Usage: $0 [--skip-tofu]"
            echo "  --skip-tofu  Skip OpenTofu provisioning (infra already exists)"
            exit 0
            ;;
        *) echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

step() { echo -e "\n${BLUE}━━━ [$1/6] $2${NC}\n"; }
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗ $1${NC}"; exit 1; }

# -----------------------------------------------------------------------------
# 1. Prerequisites
# -----------------------------------------------------------------------------
step 1 "Checking prerequisites"

check_cmd() {
    if command -v "$1" &>/dev/null; then
        ok "$1 found"
    else
        fail "$1 is required but not installed. $2"
    fi
}

check_cmd docker  "Install from https://docs.docker.com/get-docker/"

if [ "$SKIP_TOFU" = false ]; then
    check_cmd tofu "Install from https://opentofu.org/docs/intro/install/"
fi

# -----------------------------------------------------------------------------
# 2. Provision infrastructure
# -----------------------------------------------------------------------------
step 2 "Provisioning infrastructure (OpenTofu)"

if [ "$SKIP_TOFU" = true ]; then
    warn "Skipped (--skip-tofu)"
else
    if [ ! -f "$INFRA_DIR/terraform.tfvars" ]; then
        echo -e "${CYAN}No terraform.tfvars found. Creating from template...${NC}"
        cp "$INFRA_DIR/terraform.tfvars.example" "$INFRA_DIR/terraform.tfvars"
        echo -e "${YELLOW}Please edit infrastructure/terraform.tfvars with your Scaleway credentials.${NC}"
        read -rp "Press ENTER after editing (or Ctrl+C to abort)... "
    fi

    ok "terraform.tfvars found"

    (cd "$INFRA_DIR" && tofu init -input=false)
    ok "OpenTofu initialized"
    (cd "$INFRA_DIR" && tofu plan -out=tfplan)

    read -rp "  Apply this plan? [y/N] " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        (cd "$INFRA_DIR" && tofu apply tfplan)
        rm -f "$INFRA_DIR/tfplan"
        ok "Infrastructure provisioned"
    else
        rm -f "$INFRA_DIR/tfplan"
        fail "OpenTofu apply cancelled"
    fi
fi

# -----------------------------------------------------------------------------
# 3. Build and push Docker images
# -----------------------------------------------------------------------------
step 3 "Building and pushing Docker images to Container Registry"

"$SCRIPT_DIR/build-push-images.sh"
ok "All showcase images pushed"

# -----------------------------------------------------------------------------
# 4. Generate .env
# -----------------------------------------------------------------------------
step 4 "Generating .env configuration"

"$SCRIPT_DIR/generate-env.sh"
ok ".env generated from OpenTofu outputs"

# -----------------------------------------------------------------------------
# 5. Database + knowledge base
# -----------------------------------------------------------------------------
step 5 "Database and knowledge base"
ok "Schema created lazily by the backend on first request"
echo -e "  ${YELLOW}To seed the RAG knowledge base, SSH into the app instance after boot:${NC}"
echo -e "  ${CYAN}ssh -p 2201 root@<domain-or-lb-ip>${NC}"
echo -e "  ${CYAN}docker compose -f /opt/app/docker-compose.yaml exec showcase2 python scripts/load-knowledge-base.py${NC}"

# -----------------------------------------------------------------------------
# 6. Wait for services
# -----------------------------------------------------------------------------
step 6 "Waiting for application services"

BASE_URL=$(cd "$INFRA_DIR" && tofu output -raw base_url)
echo -e "  Base URL: ${CYAN}${BASE_URL}${NC}"
echo -e "  ${YELLOW}Cloud-init is installing Docker and pulling images (~3-5 min)${NC}"

MAX_RETRIES=20
for i in $(seq 1 $MAX_RETRIES); do
    if curl -sf --insecure "${BASE_URL}/consultation-assistant/api/health" > /dev/null 2>&1; then
        ok "Showcase 1 (Consultation Assistant) is healthy"
        break
    fi
    echo -e "  ${YELLOW}Waiting... (attempt $i/$MAX_RETRIES)${NC}"
    sleep 30
done

if ! curl -sf --insecure "${BASE_URL}/consultation-assistant/api/health" > /dev/null 2>&1; then
    warn "Showcase 1 not yet healthy. Cloud-init may still be running."
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Scaleway Medical AI Lab - Workshop Ready${NC}"
echo ""
echo -e "  ${CYAN}Landing page:${NC}              ${BASE_URL}/"
echo -e "  ${CYAN}Consultation Assistant:${NC}     ${BASE_URL}/consultation-assistant/"
echo -e "  ${CYAN}Document Intelligence:${NC}      ${BASE_URL}/document-intelligence/"
echo -e "  ${CYAN}Research Agent:${NC}             ${BASE_URL}/research-agent/"
echo ""
echo -e "  All services run inside a VPC. Only the Load Balancer is public."
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
