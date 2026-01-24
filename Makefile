.PHONY: all setup tests load teardown clean help

all: setup tests load

setup:
	@./scripts/setup.sh

tests:
	@./scripts/run-tests.sh

load:
	@./scripts/run-load.sh quick

load-standard:
	@./scripts/run-load.sh standard

load-full:
	@./scripts/run-load.sh full

teardown:
	@./scripts/teardown.sh

clean: teardown
	rm -rf tests/.venv omes/repo

help:
	@echo "make setup    - Start infrastructure"
	@echo "make tests    - Run functional tests"
	@echo "make load     - Run load tests (quick)"
	@echo "make teardown - Stop infrastructure"
	@echo "make all      - setup + tests + load"
