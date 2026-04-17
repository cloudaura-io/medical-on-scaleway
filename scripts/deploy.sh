#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$PROJECT_ROOT/infrastructure"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

fail() { echo -e "${RED}Error: $1${NC}" >&2; exit 1; }

command -v tofu &>/dev/null || fail "tofu is not installed. Install from https://opentofu.org/docs/intro/install/"
command -v docker &>/dev/null || fail "docker is not installed. Install from https://docs.docker.com/get-docker/"
command -v curl &>/dev/null || fail "curl is not installed."

TFVARS="$INFRA_DIR/terraform.tfvars"

if [ ! -f "$TFVARS" ]; then
    echo -e "${YELLOW}No terraform.tfvars found.${NC}"
    echo ""
    echo "  Create it from the example:"
    echo -e "  ${CYAN}cp infrastructure/terraform.tfvars.example infrastructure/terraform.tfvars${NC}"
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
    if [ -z "$value" ] || [[ "$value" == SCW...* ]] || [[ "$value" == xxx* ]]; then
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

echo -e "${CYAN}Provisioning infrastructure (~34 resources)...${NC}"
tofu apply -input=false -auto-approve

DOMAIN=$(tofu output -raw domain_name)
echo -e "${CYAN}Domain: ${DOMAIN}${NC}"

echo -e "${CYAN}Building and pushing Docker images...${NC}"
"$SCRIPT_DIR/build-push-images.sh"

echo -e "${YELLOW}Waiting for showcase services (cloud-init + docker pull)...${NC}"

MAX_RETRIES=60
for i in $(seq 1 $MAX_RETRIES); do
    if curl -sf --max-time 5 "https://${DOMAIN}/consultation-assistant/api/health" > /dev/null 2>&1; then
        break
    fi
    printf "  Waiting... (%d/%d)\r" "$i" "$MAX_RETRIES"
    sleep 10
done

if ! curl -sf --max-time 5 "https://${DOMAIN}/consultation-assistant/api/health" > /dev/null 2>&1; then
    echo -e "\n${YELLOW}Health check not passing after $((MAX_RETRIES * 10))s. Cloud-init may still be running.${NC}"
    echo -e "Try manually: curl https://${DOMAIN}/consultation-assistant/api/health"
fi

BASE_URL=$(tofu output -raw base_url)

VLLM_STATUS="${YELLOW}loading (model downloading from HuggingFace, ~10-15 min on first boot)${NC}"
if curl -sf --max-time 5 "https://${DOMAIN}/vllm-health" > /dev/null 2>&1; then
    VLLM_STATUS="${GREEN}ready${NC}"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Medical AI Lab Ready${NC}"
echo ""
echo -e "  ${CYAN}Landing page:${NC}              ${BASE_URL}/"
echo -e "  ${CYAN}Consultation Assistant:${NC}     ${BASE_URL}/consultation-assistant/"
echo -e "  ${CYAN}Document Intelligence:${NC}      ${BASE_URL}/document-intelligence/"
echo -e "  ${CYAN}Research Agent:${NC}             ${BASE_URL}/drug-interactions/"
echo ""
echo -e "  ${CYAN}Live transcription (vLLM):${NC} ${VLLM_STATUS}"
echo -e "  ${YELLOW}File upload transcription works immediately (uses Scaleway Generative APIs).${NC}"
echo -e "  ${YELLOW}Live mic mode requires the vLLM GPU instance to finish loading.${NC}"
echo -e "  ${YELLOW}Check: curl https://${DOMAIN}/vllm-health${NC}"
echo ""
echo -e "  ${CYAN}Destroy:${NC}     bash scripts/destroy.sh"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
