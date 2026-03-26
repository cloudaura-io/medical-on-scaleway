#!/usr/bin/env bash
################################################################################
# Scaleway Medical AI Lab — Infrastructure Teardown
#
# Destroys all OpenTofu-provisioned resources:
#   - Managed PostgreSQL instance
#   - Object Storage bucket
#   - Managed Inference deployment (L4 GPU)
#
# Usage:
#   ./scripts/teardown.sh          # interactive confirmation
#   ./scripts/teardown.sh --auto   # skip confirmation (CI/scripts)
################################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$PROJECT_ROOT/infrastructure"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

AUTO_APPROVE=false
for arg in "$@"; do
    case "$arg" in
        --auto) AUTO_APPROVE=true ;;
        --help|-h)
            echo "Usage: $0 [--auto]"
            echo "  --auto  Skip confirmation prompt"
            exit 0
            ;;
    esac
done

if [ ! -f "$INFRA_DIR/terraform.tfvars" ]; then
    echo -e "${RED}Error: infrastructure/terraform.tfvars not found.${NC}"
    echo "Nothing to destroy — infrastructure was never provisioned."
    exit 1
fi

# Show what will be destroyed
echo -e "${YELLOW}The following Scaleway resources will be DESTROYED:${NC}"
echo ""
(cd "$INFRA_DIR" && tofu plan -destroy -compact-warnings 2>&1 | grep -E "will be destroyed|Plan:")
echo ""

if [ "$AUTO_APPROVE" = false ]; then
    echo -e "${RED}This action is irreversible. All data will be lost.${NC}"
    read -rp "Type 'destroy' to confirm: " confirm
    if [ "$confirm" != "destroy" ]; then
        echo "Aborted."
        exit 0
    fi
fi

echo -e "\n${CYAN}Destroying infrastructure...${NC}\n"
(cd "$INFRA_DIR" && tofu destroy -auto-approve)

# Clean up local state
echo ""
echo -e "${CYAN}Cleaning up local files...${NC}"

if [ -f "$PROJECT_ROOT/.env" ]; then
    rm "$PROJECT_ROOT/.env"
    echo -e "  ${GREEN}✓${NC} Removed .env"
fi

echo ""
echo -e "${GREEN}Teardown complete. All Scaleway resources have been destroyed.${NC}"
