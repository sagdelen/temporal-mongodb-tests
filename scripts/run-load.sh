#!/bin/bash
# Run Omes load tests
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
LANGUAGE="${LANGUAGE:-python}"
MODE="${1:-quick}"

OMES_DIR="$ROOT_DIR/omes/repo"

# Clone omes if needed
if [ ! -d "$OMES_DIR" ]; then
    log_info "Cloning omes..."
    cd "$ROOT_DIR/omes"
    git clone --recursive https://github.com/temporalio/omes.git repo
fi

cd "$OMES_DIR"

run_scenario() {
    local scenario=$1
    local iterations=$2
    local concurrent=${3:-10}
    
    log_info "Running: $scenario ($iterations iterations, $concurrent concurrent)"
    
    go run ./cmd run-scenario-with-worker \
        --scenario "$scenario" \
        --language "$LANGUAGE" \
        --server-address "$TEMPORAL_ADDRESS" \
        --namespace "$NAMESPACE" \
        --run-id "mongo-$(date +%s)" \
        --iterations "$iterations" \
        --max-concurrent "$concurrent" \
        --do-not-register-search-attributes
}

log_info "=== Load Tests (mode: $MODE) ==="

case "$MODE" in
    quick)
        run_scenario "workflow_with_single_noop_activity" 100 20
        ;;
    standard)
        run_scenario "workflow_with_single_noop_activity" 500 50
        run_scenario "workflow_with_single_noop_activity" 1000 100
        ;;
    full)
        run_scenario "workflow_with_single_noop_activity" 1000 100
        go run ./cmd run-scenario-with-worker \
            --scenario "throughput_stress" \
            --language "$LANGUAGE" \
            --server-address "$TEMPORAL_ADDRESS" \
            --namespace "$NAMESPACE" \
            --run-id "mongo-stress-$(date +%s)" \
            --duration "30m" \
            --do-not-register-search-attributes
        ;;
esac

log_info "✓ Load tests completed!"
