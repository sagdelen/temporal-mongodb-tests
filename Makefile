.PHONY: up down tests load clean all

# Default target
all: up tests load

# Start infrastructure
up:
	cd docker && docker compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 10
	cd tests && source .venv/bin/activate && python -c "from tests.conftest import *; import asyncio; asyncio.run(ensure_namespace())" 2>/dev/null || true
	@echo "✓ Infrastructure ready"

# Stop infrastructure
down:
	cd docker && docker compose down -v

# Run E2E tests
tests:
	cd tests && source .venv/bin/activate && python -m pytest -v --timeout=60

# Run E2E tests (quick - subset)
tests-quick:
	cd tests && source .venv/bin/activate && python -m pytest tests/core tests/workflow -v --timeout=60

# Run load tests
load:
	cd omes && ./run-scenarios.sh

# Run load tests (quick)
load-quick:
	cd omes && ./run-scenarios.sh quick

# Setup Python environment
setup-tests:
	cd tests && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Setup omes
setup-omes:
	cd omes && git clone --recursive https://github.com/temporalio/omes.git repo || true
	cd omes/repo && git submodule update --init --recursive

# Clean up
clean:
	cd docker && docker compose down -v
	rm -rf tests/.venv
	rm -rf omes/repo

# Full test suite
test: up tests load
	@echo "✓ All tests completed"

# Health check
health:
	@docker ps --filter name=temporal-mongodb --format "table {{.Names}}\t{{.Status}}"
	@echo ""
	@nc -zv localhost 7233 2>&1 || echo "⚠ Temporal server not reachable"
