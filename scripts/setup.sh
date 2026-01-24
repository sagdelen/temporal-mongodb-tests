#!/bin/bash
# Setup infrastructure for MongoDB load tests
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
NAMESPACE="${NAMESPACE:-temporal-mongodb}"
TEMPORAL_ADDRESS="${TEMPORAL_ADDRESS:-localhost:7233}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-120}"

log_info "Starting infrastructure setup..."

# Start Docker containers
log_info "Starting Docker containers..."
cd "$ROOT_DIR/docker"
docker compose up -d

# Wait for Temporal server to be healthy
log_info "Waiting for Temporal server to be healthy (timeout: ${WAIT_TIMEOUT}s)..."
elapsed=0
while ! nc -z localhost 7233 2>/dev/null; do
    sleep 2
    elapsed=$((elapsed + 2))
    if [ $elapsed -ge $WAIT_TIMEOUT ]; then
        log_error "Timeout waiting for Temporal server"
        docker compose logs temporal-server | tail -50
        exit 1
    fi
    echo -n "."
done
echo ""
log_info "Temporal server is reachable"

# Additional wait for server to fully initialize
sleep 5

# Create namespace using uv for dependency management
log_info "Creating namespace: $NAMESPACE"
cd "$ROOT_DIR"

uv run --with temporalio python - << 'PYTHON'
import asyncio
import os
from temporalio.client import Client
from temporalio.api.workflowservice.v1 import RegisterNamespaceRequest
from temporalio.api.operatorservice.v1 import AddSearchAttributesRequest
from temporalio.api.enums.v1 import IndexedValueType
from google.protobuf.duration_pb2 import Duration

NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")

async def main():
    client = await Client.connect(ADDRESS)
    retention = Duration(seconds=86400)
    
    # Create namespace
    try:
        await client.workflow_service.register_namespace(
            RegisterNamespaceRequest(
                namespace=NAMESPACE,
                workflow_execution_retention_period=retention,
            )
        )
        print(f"✓ Created namespace: {NAMESPACE}")
    except Exception as e:
        if "already" in str(e).lower():
            print(f"✓ Namespace {NAMESPACE} already exists")
        else:
            print(f"⚠ Namespace creation note: {e}")
    
    # Add search attribute for omes
    try:
        await client.operator_service.add_search_attributes(
            AddSearchAttributesRequest(
                namespace=NAMESPACE,
                search_attributes={
                    "OmesExecutionID": IndexedValueType.INDEXED_VALUE_TYPE_KEYWORD
                }
            )
        )
        print("✓ Added OmesExecutionID search attribute")
    except Exception as e:
        if "already exists" in str(e).lower():
            print("✓ OmesExecutionID search attribute already exists")
        else:
            print(f"⚠ Search attribute note: {e}")

asyncio.run(main())
PYTHON

log_info "Infrastructure setup complete!"
log_info "  Temporal: $TEMPORAL_ADDRESS"
log_info "  Namespace: $NAMESPACE"
