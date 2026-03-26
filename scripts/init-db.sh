#!/usr/bin/env bash
################################################################################
# Initialize PostgreSQL database schema
#
# Connects to the managed PostgreSQL instance and runs init-db.sql
# (pgvector extension, tables, indexes).
#
# Usage:
#   ./scripts/init-db.sh              # reads DATABASE_URL from .env
#   DATABASE_URL=... ./scripts/init-db.sh   # explicit URL
################################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
SQL_FILE="$PROJECT_ROOT/infrastructure/init-db.sql"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

# ─────────────────────────────────────────────────────────────────────────────
# Load DATABASE_URL
# ─────────────────────────────────────────────────────────────────────────────

if [ -z "${DATABASE_URL:-}" ]; then
    if [ -f "$ENV_FILE" ]; then
        DATABASE_URL=$(grep "^DATABASE_URL=" "$ENV_FILE" | cut -d= -f2-)
    fi
fi

if [ -z "${DATABASE_URL:-}" ]; then
    echo -e "${RED}Error: DATABASE_URL not set. Run generate-env.sh first or set it manually.${NC}"
    exit 1
fi

if [ ! -f "$SQL_FILE" ]; then
    echo -e "${RED}Error: $SQL_FILE not found${NC}"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# Test connectivity
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${CYAN}Testing database connection...${NC}"
if ! psql "$DATABASE_URL" -c "SELECT 1" &>/dev/null; then
    echo -e "${RED}Error: Cannot connect to database.${NC}"
    echo "Check that:"
    echo "  - The Scaleway RDB instance is running"
    echo "  - Your IP is allowed (Scaleway RDB uses IP allowlists)"
    echo "  - DATABASE_URL is correct"
    echo ""
    echo "To allow your IP, go to:"
    echo "  Scaleway Console > Managed Databases > your instance > Allowed IPs"
    echo "  Add your public IP: $(curl -s ifconfig.me 2>/dev/null || echo '<unknown>')/32"
    exit 1
fi
echo -e "${GREEN}✓${NC} Database connection OK"

# ─────────────────────────────────────────────────────────────────────────────
# Run schema
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${CYAN}Applying schema from init-db.sql...${NC}"
psql "$DATABASE_URL" -f "$SQL_FILE"

# Verify tables
TABLES=$(psql "$DATABASE_URL" -t -c "
    SELECT string_agg(tablename, ', ' ORDER BY tablename)
    FROM pg_tables
    WHERE schemaname = 'public'
")
echo -e "${GREEN}✓${NC} Tables created: $TABLES"

# Verify pgvector
PGVECTOR=$(psql "$DATABASE_URL" -t -c "SELECT extversion FROM pg_extension WHERE extname = 'vector'" | tr -d ' ')
echo -e "${GREEN}✓${NC} pgvector extension: v${PGVECTOR}"
