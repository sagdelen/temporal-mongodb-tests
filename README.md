# Temporal MongoDB Persistence Tests

Load and E2E tests for validating MongoDB as a persistence backend for Temporal.

## Status

| Test Suite      | Status                                                   |
| --------------- | -------------------------------------------------------- |
| E2E Tests (329) | ![E2E](https://img.shields.io/badge/E2E-passing-green)   |
| Load Tests      | ![Load](https://img.shields.io/badge/Load-passing-green) |

## Overview

This repository contains:

- **E2E Tests**: 329 functional tests covering workflows, activities, signals, queries, etc.
- **Load Tests**: Omes-based load testing scenarios for throughput validation

## Quick Start

```bash
# Start MongoDB + Temporal server
make up

# Run E2E tests
make e2e

# Run load tests
make load
```

## Test Suites

### E2E Tests (pytest)

- 329 tests covering all major Temporal features
- 60s timeout per test
- Categories: workflow, activity, signal, query, saga, timer, etc.

### Load Tests (omes)

- `workflow_with_single_noop_activity` - Basic throughput test
- `throughput_stress` - Extended stress test
- Python worker (Go worker has SDK compatibility issues)

## Running Tests Manually

### Prerequisites

- Docker & Docker Compose
- Python 3.10+
- Go 1.21+ (for omes)

### Start Infrastructure

```bash
cd docker
docker compose up -d
```

### Run E2E Tests

```bash
cd e2e
python -m pytest -v --timeout=60
```

### Run Load Tests

```bash
cd omes
./run-scenarios.sh
```

## CI/CD

Tests are run via GitHub Actions on:

- Manual trigger (`workflow_dispatch`) before version releases
- Test against specific Temporal + MongoDB version combinations

## Compatibility Matrix

See [COMPATIBILITY.md](COMPATIBILITY.md) for tested version combinations.

## Related Repositories

- [temporalio/temporal](https://github.com/temporalio/temporal) - Temporal server
- [sagdelen/temporal](https://github.com/sagdelen/temporal) - MongoDB persistence fork
- [temporalio/omes](https://github.com/temporalio/omes) - Load testing tool

## License

MIT
