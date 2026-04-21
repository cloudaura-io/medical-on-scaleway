#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd "$SCRIPT_DIR/../infrastructure" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

fail() { echo -e "${RED}Error: $1${NC}" >&2; exit 1; }

command -v tofu &>/dev/null || fail "tofu is not installed. Install from https://opentofu.org/docs/intro/install/"
command -v curl &>/dev/null || fail "curl is not installed."

TFVARS="$INFRA_DIR/terraform.tfvars"

if [ ! -f "$TFVARS" ]; then
    echo -e "${YELLOW}No terraform.tfvars found.${NC}"
    echo ""
    echo "  Create it from the example:"
    echo -e "  ${CYAN}cp workshop/infrastructure/terraform.tfvars.example workshop/infrastructure/terraform.tfvars${NC}"
    echo ""
    echo "  Then fill in the required values:"
    echo "    access_key       Scaleway API access key (SCW...)"
    echo "    secret_key       Scaleway API secret key (UUID)"
    echo "    organization_id  Scaleway organization ID (UUID)"
    echo "    project_id       Scaleway project ID (UUID)"
    echo ""
    echo "  See README.md 'First-time Scaleway account setup' for details."
    exit 1
fi

REQUIRED_VARS=(access_key secret_key organization_id project_id)
MISSING=()

for var in "${REQUIRED_VARS[@]}"; do
    value=$(grep -E "^\s*${var}\s*=" "$TFVARS" 2>/dev/null | head -1 | sed 's/.*=\s*"\(.*\)".*/\1/' || true)
    if [ -z "$value" ] || [[ "$value" == SCW...* ]] || [[ "$value" == xxx* ]] || [[ "$value" == ssh-* && "$var" != "ssh_public_key" ]]; then
        MISSING+=("$var")
    fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
    fail "Missing or placeholder values in terraform.tfvars: ${MISSING[*]}
  Edit: $TFVARS"
fi

cd "$INFRA_DIR"

if [ ! -d ".terraform" ]; then
    echo -e "${CYAN}Running tofu init...${NC}"
    tofu init -input=false
fi

echo -e "${CYAN}Provisioning workshop infrastructure...${NC}"
tofu apply -input=false -auto-approve

IP=$(tofu output -raw public_ip)
DOMAIN="${IP//./-}.sslip.io"
echo -e "${CYAN}Instance IP: ${IP}${NC}"
echo -e "${YELLOW}Waiting for services and TLS certificate...${NC}"

MAX_RETRIES=60
for i in $(seq 1 $MAX_RETRIES); do
    if curl -sf --max-time 5 "https://${DOMAIN}/healthz" > /dev/null 2>&1; then
        break
    fi
    printf "  Waiting... (%d/%d)\r" "$i" "$MAX_RETRIES"
    sleep 10
done

if ! curl -sf --max-time 5 "https://${DOMAIN}/healthz" > /dev/null 2>&1; then
    echo -e "\n${YELLOW}HTTPS health check not passing after $((MAX_RETRIES * 10))s.${NC}"
    echo -e "HTTP fallback: http://${IP}/healthz"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Workshop Ready${NC}"
echo ""
echo -e "  ${CYAN}JupyterLab:${NC}  $(tofu output -raw jupyter_url)"
echo ""
echo -e "  ${CYAN}Destroy:${NC}     bash workshop/scripts/destroy.sh"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
