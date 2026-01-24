#!/bin/bash
# Omes Load Test Scenarios for MongoDB Persistence

set -e

OMES_DIR="${OMES_DIR:-./repo}"
SERVER_ADDRESS="${SERVER_ADDRESS:-localhost:7233}"
NAMESPACE="${NAMESPACE:-temporal-mongodb}"
LANGUAGE="${LANGUAGE:-python}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log_success() { echo -e "${GREEN}✓ $1${NC}"; }
log_error() { echo -e "${RED}✗ $1${NC}"; }

# Check if omes is available
if [ ! -d "$OMES_DIR" ]; then
    echo "Omes not found at $OMES_DIR"
    echo "Run: git clone --recursive https://github.com/temporalio/omes.git $OMES_DIR"
    exit 1
fi

cd "$OMES_DIR"

# Activate mise if available
if command -v mise &> /dev/null; then
    eval "$(mise activate bash)"
fi

run_scenario() {
    local scenario=$1
    local iterations=$2
    local max_concurrent=${3:-10}
    local run_id="mongo-${scenario}-$(date +%s)"
    
    echo "Running: $scenario ($iterations iterations, $max_concurrent concurrent)"
    
    if go run ./cmd run-scenario-with-worker \
        --scenario "$scenario" \
        --language "$LANGUAGE" \
        --server-address "$SERVER_ADDRESS" \
        --namespace "$NAMESPACE" \
        --run-id "$run_id" \
        --iterations "$iterations" \
        --max-concurrent "$max_concurrent" \
        --do-not-register-search-attributes 2>&1; then
        log_success "$scenario completed"
        return 0
    else
        log_error "$scenario failed"
        return 1
    fi
}

# Quick mode for CI
if [ "$1" = "quick" ]; then
    echo "=== Quick Load Test ==="
    run_scenario "workflow_with_single_noop_activity" 100 20
    exit $?
fi

# Full load test suite
echo "=== MongoDB Load Test Suite ==="
echo "Server: $SERVER_ADDRESS"
echo "Namespace: $NAMESPACE"
echo "Language: $LANGUAGE"
echo ""

FAILED=0

# Test 1: Basic workflow throughput
echo "--- Test 1: Basic Workflow Throughput ---"
run_scenario "workflow_with_single_noop_activity" 500 50 || ((FAILED++))

# Test 2: Higher concurrency
echo ""
echo "--- Test 2: High Concurrency ---"
run_scenario "workflow_with_single_noop_activity" 1000 100 || ((FAILED++))

# Test 3: Sustained load (if time permits)
if [ "$1" = "full" ]; then
    echo ""
    echo "--- Test 3: Sustained Load (30 min) ---"
    go run ./cmd run-scenario-with-worker \
        --scenario "throughput_stress" \
        --language "$LANGUAGE" \
        --server-address "$SERVER_ADDRESS" \
        --namespace "$NAMESPACE" \
        --run-id "mongo-stress-$(date +%s)" \
        --duration "30m" \
        --do-not-register-search-attributes 2>&1 || ((FAILED++))
fi

echo ""
echo "=== Load Test Summary ==="
if [ $FAILED -eq 0 ]; then
    log_success "All load tests passed!"
    exit 0
else
    log_error "$FAILED test(s) failed"
    exit 1
fi
