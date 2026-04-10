#!/usr/bin/env bash
################################################################################
# Build and push showcase Docker images to Scaleway Container Registry
#
# Reads the registry endpoint and SCW credentials from OpenTofu outputs
# and terraform.tfvars, then builds and pushes all three showcase images.
#
# Usage:
#   ./scripts/build-push-images.sh
################################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$PROJECT_ROOT/infrastructure"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

# -----------------------------------------------------------------------------
# Read registry endpoint and credentials
# -----------------------------------------------------------------------------

source "$SCRIPT_DIR/lib.sh"

REGISTRY=$(cd "$INFRA_DIR" && tofu output -raw registry_endpoint 2>/dev/null)

SCW_SECRET_KEY=$(get_tfvar "secret_key")

if [ -z "$REGISTRY" ] || [ -z "$SCW_SECRET_KEY" ]; then
    echo -e "${RED}Error: Could not read registry endpoint or SCW credentials.${NC}"
    echo "Ensure 'tofu apply' has been run and terraform.tfvars exists."
    exit 1
fi

echo -e "${CYAN}Registry: ${REGISTRY}${NC}"

# -----------------------------------------------------------------------------
# Authenticate with Scaleway Container Registry
# -----------------------------------------------------------------------------

echo -e "${CYAN}Authenticating with registry...${NC}"
echo "$SCW_SECRET_KEY" | docker login "$REGISTRY" -u nologin --password-stdin
echo -e "${GREEN}Authenticated.${NC}"

# -----------------------------------------------------------------------------
# Build base image (shared across all showcases)
# -----------------------------------------------------------------------------

echo -e "${CYAN}Building base image...${NC}"
docker build -t medical-lab-base:latest "$PROJECT_ROOT"
echo -e "${GREEN}Base image built.${NC}"

# -----------------------------------------------------------------------------
# Tag and push showcase images
# -----------------------------------------------------------------------------

# CMD is set at runtime via docker-compose.yaml in cloud-init, not baked into the image.
# All three tags point to the same base image.
SHOWCASES=("showcase1" "showcase2" "showcase3")

for i in "${!SHOWCASES[@]}"; do
    name="${SHOWCASES[$i]}"
    tag="${REGISTRY}/${name}:latest"

    echo -e "${CYAN}Tagging ${name}...${NC}"
    # Tag the base image - the CMD is set at runtime via docker-compose
    docker tag medical-lab-base:latest "$tag"

    echo -e "${CYAN}Pushing ${tag}...${NC}"
    docker push "$tag"
    echo -e "${GREEN}Pushed ${name}.${NC}"
done

echo ""
echo -e "${GREEN}All images pushed to ${REGISTRY}${NC}"
echo -e "  ${REGISTRY}/showcase1:latest"
echo -e "  ${REGISTRY}/showcase2:latest"
echo -e "  ${REGISTRY}/showcase3:latest"
