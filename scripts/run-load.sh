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
#   quick     - 100 iterations (~10s)     - Development sanity check
#   standard  - ~600 iterations (~2min)   - PR/Release validation
#   full      - Extended stress (~5min)   - Comprehensive validation
#   nightly   - 2h5m throughput_stress    - Upstream-compatible nightly
#   weekly    - 24h throughput_stress     - Upstream-compatible weekly
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
LANGUAGE="go"
MODE="${1:-quick}"

OMES_DIR="$ROOT_DIR/omes/repo"
SUMMARY_FILE="${LOAD_TEST_SUMMARY:-/tmp/load-test-summary.md}"

# Initialize summary
TOTAL_WORKFLOWS=0
TOTAL_DURATION=0
PHASES=()

# Clone omes if needed
if [ ! -d "$OMES_DIR" ]; then
    log_info "Cloning omes..."
    mkdir -p "$ROOT_DIR/omes"
    git clone --recursive https://github.com/temporalio/omes.git "$OMES_DIR"
fi

cd "$OMES_DIR"

# Track background worker PIDs for cleanup
WORKER_PIDS=()

cleanup_workers() {
    for pid in "${WORKER_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
    done
    WORKER_PIDS=()
}

trap cleanup_workers EXIT

add_phase() {
    local phase=$1
    local scenario=$2
    local iterations=$3
    local concurrent=$4
    local duration=$5
    local workflows=$6
    local note=$7
    
    PHASES+=("$phase|$scenario|$iterations|$concurrent|$duration|$workflows|$note")
    if [[ "$workflows" =~ ^[0-9]+$ ]]; then
        TOTAL_WORKFLOWS=$((TOTAL_WORKFLOWS + workflows))
    fi
    TOTAL_DURATION=$((TOTAL_DURATION + duration))
}

run_scenario() {
    local scenario=$1
    local iterations=$2
    local concurrent=${3:-10}
    local options=$4
    local phase_num=$5
    local run_id="mongo-$(date +%s)-$RANDOM"
    
    log_info "Scenario: $scenario"
    log_info "  Iterations: $iterations | Concurrency: $concurrent"
    
    local start_time=$(date +%s)
    
    local output
    output=$(go run ./cmd run-scenario-with-worker \
        --scenario "$scenario" \
        --language "$LANGUAGE" \
        --server-address "$TEMPORAL_ADDRESS" \
        --namespace "$NAMESPACE" \
        --run-id "$run_id" \
        --iterations "$iterations" \
        --max-concurrent "$concurrent" \
        --do-not-register-search-attributes \
        $options 2>&1) || { echo "$output"; return 1; }
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    log_info "  ✓ Completed in ${duration}s"
    
    # Calculate workflows based on scenario
    local workflows=$iterations
    if [[ "$scenario" == "throughput_stress" ]]; then
        workflows=$((iterations * 14))
    fi
    
    add_phase "$phase_num" "$scenario" "$iterations" "$concurrent" "$duration" "$workflows" ""
}

run_scenario_multi_tq() {
    local scenario=$1
    local iterations=$2
    local concurrent=$3
    local tq_count=$4
    local phase_num=$5
    local run_id="mongo-mtq-$(date +%s)-$RANDOM"
    
    log_info "Scenario: $scenario (multi-task-queue)"
    log_info "  Iterations: $iterations | Concurrency: $concurrent | Task Queues: $tq_count"
    
    local start_time=$(date +%s)
    
    log_info "  Starting worker for $tq_count task queues..."
    go run ./cmd run-worker \
        --scenario "$scenario" \
        --language "$LANGUAGE" \
        --server-address "$TEMPORAL_ADDRESS" \
        --namespace "$NAMESPACE" \
        --run-id "$run_id" \
        --task-queue-suffix-index-start 0 \
        --task-queue-suffix-index-end $((tq_count - 1)) \
        --log-level warn &
    local worker_pid=$!
    WORKER_PIDS+=($worker_pid)
    
    sleep 2
    
    go run ./cmd run-scenario \
        --scenario "$scenario" \
        --server-address "$TEMPORAL_ADDRESS" \
        --namespace "$NAMESPACE" \
        --run-id "$run_id" \
        --iterations "$iterations" \
        --max-concurrent "$concurrent" \
        --do-not-register-search-attributes \
        --option "task-queue-count=$tq_count"
    
    kill "$worker_pid" 2>/dev/null || true
    wait "$worker_pid" 2>/dev/null || true
    WORKER_PIDS=("${WORKER_PIDS[@]/$worker_pid}")
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    log_info "  ✓ Completed in ${duration}s"
    
    add_phase "$phase_num" "$scenario" "$iterations" "$concurrent" "$duration" "$iterations" "$tq_count task queues"
}

run_duration_scenario() {
    local scenario=$1
    local test_duration=$2
    local phase_num=$3
    local run_id="mongo-stress-$(date +%s)-$RANDOM"
    
    log_info "Scenario: $scenario (duration: $test_duration)"
    
    local start_time=$(date +%s)
    
    go run ./cmd run-scenario-with-worker \
        --scenario "$scenario" \
        --language "$LANGUAGE" \
        --server-address "$TEMPORAL_ADDRESS" \
        --namespace "$NAMESPACE" \
        --run-id "$run_id" \
        --duration "$test_duration" \
        --do-not-register-search-attributes
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    log_info "  ✓ Completed in ${duration}s"
    
    add_phase "$phase_num" "$scenario" "-" "-" "$duration" "~" "duration: $test_duration"
}

# Upstream-compatible throughput_stress runner
run_upstream_stress() {
    local test_duration=$1
    local description=$2
    local run_id="upstream-$(date +%s)-$RANDOM"
    
    log_info "Running upstream-compatible throughput_stress"
    log_info "  Duration: $test_duration"
    log_info "  Internal iterations: 25"
    log_info "  Continue-as-new after: 5 iterations"
    
    local start_time=$(date +%s)
    
    go run ./cmd run-scenario-with-worker \
        --scenario throughput_stress \
        --language "$LANGUAGE" \
        --server-address "$TEMPORAL_ADDRESS" \
        --namespace "$NAMESPACE" \
        --run-id "$run_id" \
        --duration "$test_duration" \
        --internal-iterations 25 \
        --continue-as-new-after-iterations 5 \
        --do-not-register-search-attributes
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    log_info "  ✓ Completed in ${duration}s"
    
    add_phase "1" "throughput_stress" "-" "-" "$duration" "~" "$description"
}

write_summary() {
    cat > "$SUMMARY_FILE" << EOF
### 📊 Load Test Results

| Phase | Scenario | Iterations | Concurrency | Duration | Workflows | Notes |
|:-----:|----------|:----------:|:-----------:|:--------:|:---------:|-------|
EOF
    
    for phase_data in "${PHASES[@]}"; do
        IFS='|' read -r phase scenario iters conc dur wf note <<< "$phase_data"
        echo "| **$phase** | \`$scenario\` | $iters | $conc | ${dur}s | $wf | $note |" >> "$SUMMARY_FILE"
    done
    
    cat >> "$SUMMARY_FILE" << EOF

---

**📈 Summary:**
- **Total Duration:** ${TOTAL_DURATION}s (~$((TOTAL_DURATION / 60))m $((TOTAL_DURATION % 60))s)
- **Total Workflows:** ~${TOTAL_WORKFLOWS}
- **Mode:** \`$MODE\`

EOF
    
    log_info "Summary written to $SUMMARY_FILE"
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
        run_scenario "workflow_with_single_noop_activity" 100 20 "" 1
        ;;
        
    standard)
        log_section "Standard Validation (Release)"
        log_info "Phase 1: Basic workflows"
        run_scenario "workflow_with_single_noop_activity" 500 50 "" 1
        
        log_info "Phase 2: Child workflows & continue-as-new"
        run_scenario "throughput_stress" 20 10 "" 2
        
        log_info "Phase 3: Multi-task-queue distribution"
        run_scenario_multi_tq "workflow_on_many_task_queues" 100 20 5 3
        ;;
        
    full)
        log_section "Full Stress Test"
        
        log_info "Phase 1: High-volume basic workflows"
        run_scenario "workflow_with_single_noop_activity" 2000 100 "" 1
        
        log_info "Phase 2: Throughput stress (child workflows, continue-as-new)"
        run_scenario "throughput_stress" 50 20 "" 2
        
        log_info "Phase 3: Many actions (sequential)"
        run_scenario "workflow_with_many_actions" 20 1 "" 3
        
        log_info "Phase 4: Multi-task-queue distribution"
        run_scenario_multi_tq "workflow_on_many_task_queues" 200 50 5 4
        
        log_info "Phase 5: Scheduler stress"
        run_duration_scenario "scheduler_stress" "30s" 5
        
        log_info "Phase 6: State transitions"
        run_duration_scenario "state_transitions_steady" "30s" 6
        ;;
        
    nightly)
        log_section "Nightly Validation (Upstream-Compatible)"
        log_warn "⏱️  This test takes approximately 2 hours 5 minutes"
        log_warn "📋 Matches Temporal's internal nightly test configuration"
        log_info ""
        log_info "Source: https://github.com/temporalio/temporal/issues/8652\#issuecomment-3775536865"
        log_info ""
        
        run_upstream_stress "2h5m" "nightly (2h5m, upstream-compatible)"
        ;;
        
    weekly)
        log_section "Weekly Validation (Upstream-Compatible)"
        log_warn "⏱️  This test takes 24 HOURS"
        log_warn "📋 Matches Temporal's internal weekly test configuration"
        log_info ""
        log_info "Source: https://github.com/temporalio/temporal/issues/8652#issuecomment-3775536865"
        log_info ""
        
        # Safety confirmation for 24h test
        if [[ "${SKIP_CONFIRMATION:-}" != "true" ]]; then
            echo -e "${YELLOW}Are you sure you want to run a 24-hour test? (yes/no):${NC} "
            read -r confirm
            if [[ "$confirm" != "yes" ]]; then
                log_warn "Aborted."
                exit 0
            fi
        fi
        
        run_upstream_stress "24h" "weekly (24h, upstream-compatible)"
        ;;
        
    *)
        log_error "Unknown mode: $MODE"
        echo "Usage: $0 [quick|standard|full|nightly|weekly]"
        exit 1
        ;;
esac

# Write summary
write_summary

# Final output
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  ✓ Load tests completed successfully                           ║"
echo "║  📊 Total: ~${TOTAL_WORKFLOWS} workflows in ${TOTAL_DURATION}s                         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
