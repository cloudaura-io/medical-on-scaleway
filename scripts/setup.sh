#!/usr/bin/env bash
################################################################################
# Scaleway Medical AI Lab — Full Infrastructure Setup
#
# This script orchestrates the entire setup:
#   1. Check prerequisites
#   2. Provision infrastructure with OpenTofu
#   3. Generate .env from OpenTofu outputs
#   4. Initialize database schema (pgvector + tables)
#   5. Install Python dependencies
#   6. Load knowledge base into pgvector
#   7. Validate all services
#
# Usage:
#   ./scripts/setup.sh                     # interactive (prompts for missing vars)
#   ./scripts/setup.sh --skip-tofu          # skip OpenTofu (infra already exists)
#   ./scripts/setup.sh --skip-knowledge    # skip knowledge base loading
################################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$PROJECT_ROOT/infrastructure"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Flags
SKIP_TOFU=false
SKIP_KNOWLEDGE=false

for arg in "$@"; do
    case "$arg" in
        --skip-tofu) SKIP_TOFU=true ;;
        --skip-knowledge) SKIP_KNOWLEDGE=true ;;
        --help|-h)
            echo "Usage: $0 [--skip-tofu] [--skip-knowledge]"
            echo ""
            echo "  --skip-tofu       Skip OpenTofu provisioning (infra already exists)"
            echo "  --skip-knowledge  Skip loading knowledge base into pgvector"
            exit 0
            ;;
        *) echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

step() { echo -e "\n${BLUE}━━━ [$1/7] $2${NC}\n"; }
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗ $1${NC}"; exit 1; }

# ─────────────────────────────────────────────────────────────────────────────
# 1. Prerequisites
# ─────────────────────────────────────────────────────────────────────────────
step 1 "Checking prerequisites"

check_cmd() {
    if command -v "$1" &>/dev/null; then
        ok "$1 found: $(command -v "$1")"
    else
        fail "$1 is required but not installed. $2"
    fi
}

check_cmd python3 "Install Python 3.11+ from https://python.org"
check_cmd pip     "Should be bundled with Python 3"
check_cmd psql    "Install: apt install postgresql-client / brew install libpq"

if [ "$SKIP_TOFU" = false ]; then
    check_cmd tofu "Install from https://opentofu.org/docs/intro/install/"
fi

# Verify Python version >= 3.11
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
    ok "Python $PY_VERSION (>= 3.11)"
else
    fail "Python >= 3.11 required, found $PY_VERSION"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 2. OpenTofu — provision Scaleway infrastructure
# ─────────────────────────────────────────────────────────────────────────────
step 2 "Provisioning infrastructure (OpenTofu)"

if [ "$SKIP_TOFU" = true ]; then
    warn "Skipped (--skip-tofu)"
else
    # Ensure terraform.tfvars exists
    if [ ! -f "$INFRA_DIR/terraform.tfvars" ]; then
        echo -e "${CYAN}No terraform.tfvars found. Creating from template...${NC}"
        cp "$INFRA_DIR/terraform.tfvars.example" "$INFRA_DIR/terraform.tfvars"

        echo ""
        echo -e "${YELLOW}Please edit infrastructure/terraform.tfvars with your Scaleway credentials:${NC}"
        echo "  - access_key       (from Scaleway Console > IAM > API Keys)"
        echo "  - secret_key       (from Scaleway Console > IAM > API Keys)"
        echo "  - organization_id  (from Scaleway Console > Organization Settings)"
        echo "  - project_id       (from Scaleway Console > Project Settings)"
        echo "  - student_id      (unique identifier, e.g. student-01)"
        echo "  - db_password     (minimum 12 characters)"
        echo ""
        read -rp "Press ENTER after editing terraform.tfvars (or Ctrl+C to abort)... "
    fi

    ok "terraform.tfvars found"

    echo -e "  ${CYAN}Running tofu init...${NC}"
    (cd "$INFRA_DIR" && tofu init -input=false)
    ok "OpenTofu initialized"

    echo -e "  ${CYAN}Running tofu plan...${NC}"
    (cd "$INFRA_DIR" && tofu plan -out=tfplan)

    echo ""
    read -rp "  Apply this plan? [y/N] " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        (cd "$INFRA_DIR" && tofu apply tfplan)
        rm -f "$INFRA_DIR/tfplan"
        ok "Infrastructure provisioned"
    else
        rm -f "$INFRA_DIR/tfplan"
        fail "OpenTofu apply cancelled by user"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# 3. Generate .env from OpenTofu outputs
# ─────────────────────────────────────────────────────────────────────────────
step 3 "Generating .env configuration"

"$SCRIPT_DIR/generate-env.sh"
ok ".env generated from OpenTofu outputs"

# ─────────────────────────────────────────────────────────────────────────────
# 4. Initialize database schema
# ─────────────────────────────────────────────────────────────────────────────
step 4 "Initializing database schema"

"$SCRIPT_DIR/init-db.sh"
ok "Database schema initialized"

# ─────────────────────────────────────────────────────────────────────────────
# 5. Python virtual environment + dependencies
# ─────────────────────────────────────────────────────────────────────────────
step 5 "Setting up Python venv and dependencies"

VENV_DIR="$PROJECT_ROOT/.venv"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    ok "Created venv at .venv/"
else
    ok "Existing venv found at .venv/"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
ok "Activated venv ($(python3 --version))"

pip install -q -r "$PROJECT_ROOT/requirements.txt"
ok "Python dependencies installed"

# ─────────────────────────────────────────────────────────────────────────────
# 6. Load knowledge base
# ─────────────────────────────────────────────────────────────────────────────
step 6 "Loading knowledge base into pgvector"

if [ "$SKIP_KNOWLEDGE" = true ]; then
    warn "Skipped (--skip-knowledge)"
else
    python3 "$SCRIPT_DIR/load-knowledge-base.py"
    ok "Knowledge base loaded"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 7. Validate
# ─────────────────────────────────────────────────────────────────────────────
step 7 "Validating setup"

python3 "$SCRIPT_DIR/validate.py"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Setup complete! Run a showcase:${NC}"
echo ""
echo -e "  ${CYAN}cd 01_ambient_scribe  && uvicorn main:app --reload --port 8000${NC}"
echo -e "  ${CYAN}cd 02_document_intelligence && uvicorn main:app --reload --port 8001${NC}"
echo -e "  ${CYAN}cd 03_research_agent  && uvicorn main:app --reload --port 8002${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
