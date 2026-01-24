#!/bin/bash
# Run E2E/functional tests
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
NAMESPACE="${NAMESPACE:-temporal-mongodb}"
TEMPORAL_ADDRESS="${TEMPORAL_ADDRESS:-localhost:7233}"
TIMEOUT="${TEST_TIMEOUT:-60}"
PYTEST_ARGS="${PYTEST_ARGS:--v --timeout=$TIMEOUT}"

cd "$ROOT_DIR/tests"

# Setup virtual environment if not exists
if [ ! -d ".venv" ]; then
    log_info "Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Activate and install deps
log_info "Activating virtual environment and installing dependencies..."
source .venv/bin/activate
pip install -q -r requirements.txt

# Export env vars for tests
export NAMESPACE
export TEMPORAL_ADDRESS

# Run tests
log_info "Running tests with: pytest $PYTEST_ARGS"
log_info "  Namespace: $NAMESPACE"
log_info "  Temporal: $TEMPORAL_ADDRESS"
log_info "  Timeout: ${TIMEOUT}s per test"

if python -m pytest $PYTEST_ARGS; then
    log_info "✓ All tests passed!"
    exit 0
else
    log_error "✗ Some tests failed"
    exit 1
fi
