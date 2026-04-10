#!/usr/bin/env bash
################################################################################
# Shared helpers for scripts/
################################################################################

# Read a variable from infrastructure/*.tfvars
# Usage: get_tfvar "secret_key"
get_tfvar() {
    local key="$1"
    local infra_dir="${INFRA_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../infrastructure" && pwd)}"
    grep -hE "^${key}[[:space:]]*=" "$infra_dir"/*.tfvars 2>/dev/null \
        | head -1 \
        | sed -E 's/^[^=]*=[[:space:]]*"([^"]*)".*/\1/'
}
