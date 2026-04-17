#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd "$SCRIPT_DIR/../infrastructure" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}Destroying workshop infrastructure...${NC}"
cd "$INFRA_DIR" && tofu destroy -auto-approve
echo -e "${GREEN}Workshop destroyed.${NC}"
