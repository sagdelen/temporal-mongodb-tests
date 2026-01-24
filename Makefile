# Wrapper for users without mise - prefer `mise run <task>`
.PHONY: setup teardown load tests clean

setup:
	@./scripts/setup.sh

teardown:
	@docker compose -f docker/docker-compose.yml down -v

load:
	@./scripts/run-load.sh quick

tests:
	@./scripts/run-tests.sh

clean:
	@docker compose -f docker/docker-compose.yml down -v 2>/dev/null || true
	@rm -rf omes/repo tests/.venv
