#!/bin/bash
# ==========================================================
# Kat Records Studio Environment Verifier
# Validate required tooling before development.
# ==========================================================

set -euo pipefail
trap 'echo "❌ verify_env.sh failed on line $LINENO"; exit 1' ERR

# ---- Logging helpers mirroring init_vibe_repo.sh ----
log_step() {
    printf "   ▹ %s\n" "$1"
}

log_done() {
    printf "   ✅ %s\n" "$1"
}

log_fail() {
    printf "   ❌ %s\n" "$1" >&2
}

# ---- Tool check helpers ----
check_python() {
    log_step "Checking Python installation"
    local python_cmd=""
    if command -v python3 >/dev/null 2>&1; then
        python_cmd="python3"
    elif command -v python >/dev/null 2>&1; then
        python_cmd="python"
    else
        log_fail "Python interpreter not found. Install Python 3.10+."
        exit 1
    fi

    local python_version
    python_version="$("$python_cmd" --version 2>&1)"
    log_done "Detected ${python_cmd}: ${python_version}"
}

check_git() {
    log_step "Checking Git installation"
    if ! command -v git >/dev/null 2>&1; then
        log_fail "Git not found. Install Git before continuing."
        exit 1
    fi

    local git_version
    git_version="$(git --version)"
    log_done "Detected git: ${git_version}"
}

check_node() {
    log_step "Checking Node.js installation"
    if ! command -v node >/dev/null 2>&1; then
        log_fail "Node.js not found. Install Node.js 18+."
        exit 1
    fi

    local node_version
    node_version="$(node --version)"
    log_done "Detected node: ${node_version}"
}

main() {
    echo "🧪 Validating development environment prerequisites..."
    check_python
    check_git
    check_node
    echo "✅ Environment verification complete."
}

main "$@"
