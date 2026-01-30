#!/bin/bash
# =============================================================================
# Temporal MongoDB - Load Test Runner
# =============================================================================
# Validates MongoDB persistence under load using Temporal's official load
# generator (omes). Tests workflow scheduling, history persistence, and
# task dispatch at various throughput levels.
#
# Usage:
#   ./run-load.sh [mode]
#
# Modes:
#   quick     - 100 iterations (~4s)  - Development sanity check
#   standard  - 1,500 iterations (~30s) - Release validation
#   full      - Extended stress test (~2min) - Deep validation
#
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_section() { echo -e "\n${BLUE}━━━ $1 ━━━${NC}"; }

# Configuration
NAMESPACE="${NAMESPACE:-temporal-mongodb}"
TEMPORAL_ADDRESS="${TEMPORAL_ADDRESS:-localhost:7233}"
LANGUAGE="go"  # Go worker is sufficient for MongoDB validation
MODE="${1:-quick}"

OMES_DIR="$ROOT_DIR/omes/repo"

# Clone omes if needed
if [ ! -d "$OMES_DIR" ]; then
    log_info "Cloning omes..."
    mkdir -p "$ROOT_DIR/omes"
    git clone --recursive https://github.com/temporalio/omes.git "$OMES_DIR"
fi

cd "$OMES_DIR"

run_scenario() {
    local scenario=$1
    local iterations=$2
    local concurrent=${3:-10}
    local run_id="mongo-$(date +%s)-$RANDOM"
    
    log_info "Scenario: $scenario"
    log_info "  Iterations: $iterations | Concurrency: $concurrent"
    
    local start_time=$(date +%s)
    
    go run ./cmd run-scenario-with-worker \
        --scenario "$scenario" \
        --language "$LANGUAGE" \
        --server-address "$TEMPORAL_ADDRESS" \
        --namespace "$NAMESPACE" \
        --run-id "$run_id" \
        --iterations "$iterations" \
        --max-concurrent "$concurrent" \
        --do-not-register-search-attributes
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    log_info "  ✓ Completed in ${duration}s"
}

run_duration_scenario() {
    local scenario=$1
    local duration=$2
    local run_id="mongo-stress-$(date +%s)-$RANDOM"
    
    log_info "Scenario: $scenario (duration: $duration)"
    
    go run ./cmd run-scenario-with-worker \
        --scenario "$scenario" \
        --language "$LANGUAGE" \
        --server-address "$TEMPORAL_ADDRESS" \
        --namespace "$NAMESPACE" \
        --run-id "$run_id" \
        --duration "$duration" \
        --do-not-register-search-attributes
}

# Header
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║       Temporal MongoDB - Load Test Suite                       ║"
echo "╠════════════════════════════════════════════════════════════════╣"
echo "║  Mode:      $MODE"
echo "║  Namespace: $NAMESPACE"
echo "║  Server:    $TEMPORAL_ADDRESS"
echo "║  Worker:    $LANGUAGE"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

case "$MODE" in
    quick)
        log_section "Quick Sanity Check"
        run_scenario "workflow_with_single_noop_activity" 100 20
        ;;
        
    standard)
        log_section "Standard Validation (Release)"
        log_info "Phase 1: Basic throughput"
        run_scenario "workflow_with_single_noop_activity" 500 50
        
        log_info "Phase 2: Higher load"
        run_scenario "workflow_with_single_noop_activity" 1000 100
        ;;
        
    full)
        log_section "Full Stress Test"
        log_info "Phase 1: High-volume basic workflows"
        run_scenario "workflow_with_single_noop_activity" 2000 100
        
        log_info "Phase 2: Throughput stress (child workflows, continue-as-new)"
        run_scenario "throughput_stress" 10 5
        ;;
        
    *)
        log_error "Unknown mode: $MODE"
        echo "Usage: $0 [quick|standard|full]"
        exit 1
        ;;
esac

# Summary
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  ✓ Load tests completed successfully                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
