# Temporal MongoDB Persistence - Validation Suite

> **Production-readiness validation for MongoDB as a Temporal persistence backend**

[![E2E Tests](https://img.shields.io/badge/E2E_Tests-329_passing-success)](./tests)
[![Load Tests](https://img.shields.io/badge/Load_Tests-passing-success)](./scripts/run-load.sh)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0-green)](https://www.mongodb.com/)
[![Temporal](https://img.shields.io/badge/Temporal-1.30.0-blueviolet)](https://temporal.io/)

---

## What is This?

This repository provides **validation tests** for [Temporal](https://temporal.io/) running with MongoDB as its persistence backend. It exists to prove that MongoDB can reliably handle Temporal's persistence requirements under both functional and load conditions.

### Why Does This Exist?

MongoDB persistence support was [proposed to upstream Temporal](https://github.com/temporalio/temporal/pull/8908) but was **not accepted** into the main repository. The maintainers' position is clear:

> _"We don't want to maintain another persistence backend in the core repository. Community-maintained backends should live in separate repositories with their own testing and release cycles."_

This is a reasonable stance - maintaining multiple database backends is a significant burden. Following their guidance, we:

1. **Maintain a dedicated fork** ([sagdelen/temporal](https://github.com/sagdelen/temporal)) exclusively for MongoDB persistence
2. **Provide comprehensive validation** (this repository) to prove production-readiness
3. **Follow upstream releases** via cherry-picking, keeping MongoDB support current

**This fork exists solely for MongoDB persistence.** It tracks upstream Temporal releases and adds only the MongoDB-specific persistence layer implementation.

This test suite validates that the MongoDB implementation:

- ✅ Passes all functional requirements (329 E2E tests)
- ✅ Handles production-like load (omes stress tests)
- ✅ Maintains data integrity under concurrent operations

---


## Compatibility with Upstream Temporal

This test suite follows the **official compatibility criteria** defined by Temporal maintainers for alternative persistence implementations. According to [Temporal's guidance on persistence compatibility](https://github.com/temporalio/temporal/issues/8652#issuecomment-3775536865):

> _"Any persistence implementation that provides similar test coverage should be considered compatible, but it would still be [the community] supporting Temporal and not the other way around."_

### Temporal's Internal Test Regime

Temporal runs the following load tests internally (source: [Roey Bergundy, Temporal Server Maintainer](https://github.com/temporalio/temporal/issues/8652#issuecomment-3775536865)):

| Schedule | Duration | Scenario | Configuration |
|----------|----------|----------|---------------|
| **Nightly** (weekdays) | 2h 5m | `throughput_stress` | `--internal-iterations 25 --continue-as-new-after-iterations 5` |
| **Weekly** | 24h | `throughput_stress` | Extended stress |

**Infrastructure:**
- 4 Go workers backing the load
- Periodic pod restarts (random pod every ~1 minute)
- Nexus endpoint configured

### Our Test Coverage

We provide **comparable test coverage** through:

| Test Type | Coverage | Upstream Equivalent |
|-----------|----------|---------------------|
| **E2E Tests** | 329 functional tests | Functional test parity |
| **Load Tests** | Multiple omes scenarios | Similar to nightly runs |
| **Stress Tests** | `throughput_stress` with child workflows | Same scenario as upstream |

**Note:** While we don't run 24-hour weekly tests in CI (cost/time constraints), the same scenarios can be run locally for extended validation before major releases.

### Running Upstream-Compatible Tests

To run tests matching Temporal's nightly configuration:

```bash
# Start infrastructure
mise run setup

# Run throughput_stress with upstream-like configuration
cd omes/repo && go run ./cmd run-scenario-with-worker \
  --scenario throughput_stress \
  --language go \
  --server-address localhost:7233 \
  --namespace temporal-mongodb \
  --run-id "nightly-$(date +%s)" \
  --duration 2h5m \
  --internal-iterations 25 \
  --continue-as-new-after-iterations 5 \
  --do-not-register-search-attributes
```

---

## Scope

### What We Test

| Area                      | Description                                  | Coverage   |
| ------------------------- | -------------------------------------------- | ---------- |
| **Workflow Persistence**  | Workflows are correctly stored and retrieved | E2E + Load |
| **History Storage**       | Event history is durable and queryable       | E2E + Load |
| **Task Queue Dispatch**   | Tasks are correctly scheduled and dispatched | E2E + Load |
| **Visibility Queries**    | List/search workflows work correctly         | E2E        |
| **Concurrent Operations** | Multiple workers, high throughput            | Load       |
| **Data Integrity**        | No data loss under load                      | Load       |

### What We Don't Test (and Why)

| Area              | Reason                                                                       |
| ----------------- | ---------------------------------------------------------------------------- |
| SDK Compatibility | Already tested by upstream (see explanation below)                           |
| Multi-cluster XDC | Implemented but requires complex multi-cluster infrastructure to test        |
| Archival Provider | Archival uses pluggable providers (S3, GCS, etc.) independent of persistence |

> **Note:** Server core logic (unit, integration, functional tests) is tested in the [main fork repository](https://github.com/sagdelen/temporal) with MongoDB backend. This repository provides **additional** load and E2E tests specifically for validating MongoDB persistence under realistic conditions.

> **Note on Archival:** MongoDB persistence fully implements `ReadHistoryBranch` and all history-related methods that archival depends on. Archival works with MongoDB - we just don't test the archival _providers_ (S3, GCS, filestore) as they're separate pluggable components maintained by upstream.

> **Note on XDC/NDC:** Replication tasks, DLQ, and cluster metadata are fully implemented in the MongoDB persistence layer. Currently, our use cases don't require multi-cluster deployments, so we haven't invested in the complex infrastructure needed to validate XDC/NDC extensively. If our architecture evolves to require multi-region or multi-cluster setups in the future, we'll expand testing to cover these scenarios thoroughly.

### Why We Don't Test SDK Compatibility

```
┌─────────────────────────────────────────────────────────────┐
│                      SDK Workers                            │
│              (Go, Python, Java, TypeScript, .NET)           │
└─────────────────────────┬───────────────────────────────────┘
                          │ gRPC (standard protocol)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Temporal Server                          │
│              (Frontend, History, Matching)                  │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              Persistence Layer                      │   │
│   │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │   │
│   │  │Cassandra│ │PostgreSQL│ │  MySQL  │ │ MongoDB │   │   │
│   │  └─────────┘ └─────────┘ └─────────┘ └────┬────┘   │   │
│   └───────────────────────────────────────────┼─────────┘   │
└───────────────────────────────────────────────┼─────────────┘
                                                │
                            ┌───────────────────┴───────────────┐
                            │  THIS IS WHAT WE TEST             │
                            │  MongoDB correctly implements     │
                            │  the persistence interface        │
                            └───────────────────────────────────┘
```

**Upstream Temporal already tests all SDKs extensively.** Their CI runs [omes](https://github.com/temporalio/omes) against Go, Python, Java, TypeScript, and .NET SDKs on every commit. These tests validate that each SDK correctly implements the Temporal protocol.

**Our scope is different:** We validate that MongoDB correctly implements the persistence interface. The persistence layer sits _below_ the gRPC API - SDKs never interact with it directly. When we prove MongoDB works with one SDK (Go), we've proven the persistence layer works. Testing additional SDKs would only re-test upstream's SDK implementations, not our MongoDB code.

**In other words:**

- Upstream tests: _"Do the SDKs work correctly?"_ → They test this
- Our tests: _"Does MongoDB persistence work correctly?"_ → We test this

Testing Python/Java/TypeScript workers here would duplicate upstream's work without exercising any additional MongoDB code paths.

---

## Quick Start

### Prerequisites

- [mise](https://mise.jdx.dev/) (recommended) or manual tool installation
- Docker & Docker Compose
- Go 1.22+

### Using mise (Recommended)

```bash
# Install tools and setup environment
mise install

# Start infrastructure (MongoDB + Temporal)
mise run setup

# Run E2E tests (329 tests, ~6 minutes)
mise run tests

# Run load tests (quick sanity check)
mise run load

# Run comprehensive load tests (release validation)
mise run load:standard

# Teardown everything
mise run teardown
```

### Manual Setup

```bash
# Start infrastructure
cd docker && docker compose up -d

# Wait for services to be ready, then create namespace
temporal operator namespace create temporal-mongodb

# Add search attribute required by omes
temporal operator search-attribute create \
  --namespace temporal-mongodb \
  --name OmesExecutionID \
  --type Keyword

# Run E2E tests
cd tests && uv run pytest -v --timeout=60

# Run load tests
cd omes/repo && go run ./cmd run-scenario-with-worker \
  --scenario workflow_with_single_noop_activity \
  --language go \
  --iterations 100 \
  --server-address localhost:7233 \
  --namespace temporal-mongodb
```

---

## Test Suites

### Feature Coverage Tests (329 tests)

These tests validate that **MongoDB persistence correctly supports all Temporal features accessible via SDK**. They are integration tests that exercise the full stack:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Python SDK (test client)                    │
└─────────────────────────────┬───────────────────────────────────┘
                              │ gRPC
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Temporal Server                            │
│                (Frontend, History, Matching)                    │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MongoDB Persistence                          │
│         (Execution Store, History, Visibility, Tasks)           │  ← WHAT WE'RE VALIDATING
└─────────────────────────────────────────────────────────────────┘
```

#### Why These Tests Matter

Every SDK operation ultimately requires persistence:

| SDK Operation | Server Action | Persistence Impact |
|---------------|---------------|-------------------|
| `start_workflow()` | Create execution | Write to execution store |
| `execute_activity()` | Dispatch task, record result | Task queue + history events |
| `signal()` | Deliver signal | History event write |
| `query()` | Read state | Mutable state read |
| `describe()` | Get workflow info | Visibility store query |
| `list_workflows()` | Search workflows | Visibility query |
| `continue_as_new()` | Close + start new | Complex multi-write transaction |

By testing all these operations against a real MongoDB-backed server, we prove that:
1. **All persistence interfaces are correctly implemented**
2. **Data is durable and retrievable**
3. **Concurrent operations maintain consistency**
4. **Error handling works correctly**

#### What We Test

| Category          | Tests | Description                                      | Persistence Validated |
| ----------------- | ----- | ------------------------------------------------ | --------------------- |
| Workflow          | ~80   | Start, cancel, terminate, reset, continue-as-new | Execution store, history |
| Activity          | ~60   | Execution, heartbeat, retry, timeout             | Task dispatch, history |
| Signal            | ~40   | Send, receive, signal-with-start                 | History writes |
| Query             | ~30   | Sync queries, query rejection                    | Mutable state |
| Timer             | ~25   | Durable timers, cancellation                     | Timer queue |
| Child Workflow    | ~30   | Parent-child relationships                       | Cross-execution refs |
| Saga              | ~20   | Compensation patterns                            | Multi-activity sequences |
| Search Attributes | ~20   | Custom search attributes, visibility             | Visibility store |
| Persistence       | ~10   | Large payloads, data isolation                   | Data integrity |
| Miscellaneous     | ~14   | Edge cases, error handling                       | Error paths |

#### How This Differs From Upstream Tests

| Test Type | Location | What It Tests |
|-----------|----------|---------------|
| **SDK Unit Tests** | SDK repos | SDK internal logic (often with mock server) |
| **Server Unit Tests** | temporal/temporal | Go code correctness |
| **Server Functional Tests** | temporal/temporal | Server behavior with supported DBs |
| **Our Feature Coverage** | This repo | MongoDB persistence via real SDK operations |

Our tests complement upstream by validating MongoDB specifically—something upstream doesn't do because they don't maintain MongoDB support.

**Run time:** ~6 minutes

| Mode     | Command                  | Iterations | Duration | Purpose            |
| -------- | ------------------------ | ---------- | -------- | ------------------ |
| Quick    | `mise run load`          | 100        | ~4s      | Sanity check       |
| Standard | `mise run load:standard` | 1,500      | ~30s     | Release validation |
| Full     | `mise run load:full`     | 2,000+     | ~2min    | Stress testing     |

**Scenarios used:**

- `workflow_with_single_noop_activity` - Basic workflow + activity
- `throughput_stress` - High concurrency, child workflows, continue-as-new

---

## When to Run Tests

| Situation            | What to Run       | Command                                       |
| -------------------- | ----------------- | --------------------------------------------- |
| During development   | Quick load        | `mise run load`                               |
| Before PR merge      | E2E + Quick load  | `mise run tests && mise run load`             |
| Before release       | Full suite        | `mise run tests && mise run load:standard`    |
| Investigating issues | Specific scenario | See [Load Test Details](#load-test-scenarios) |

### Release Validation Checklist

```bash
# 1. Start fresh environment
mise run teardown
mise run setup

# 2. Run full E2E suite
mise run tests
# Expected: 329 passed

# 3. Run standard load tests
mise run load:standard
# Expected: All scenarios pass

# 4. (Optional) Extended stress test
mise run load:full
```

---

## Load Test Scenarios

### workflow_with_single_noop_activity

Basic scenario that starts a workflow which executes a single no-op activity.

```bash
# Quick test
go run ./cmd run-scenario-with-worker \
  --scenario workflow_with_single_noop_activity \
  --language go \
  --iterations 100 \
  --server-address localhost:7233 \
  --namespace temporal-mongodb
```

**What it validates:**

- Workflow scheduling and execution
- Activity task dispatch
- History persistence
- Basic throughput

### throughput_stress

Comprehensive stress test with child workflows and continue-as-new.

```bash
go run ./cmd run-scenario-with-worker \
  --scenario throughput_stress \
  --language go \
  --iterations 10 \
  --server-address localhost:7233 \
  --namespace temporal-mongodb
```

**What it validates:**

- Concurrent workflow execution
- Child workflow relationships
- Continue-as-new handling
- High-volume task dispatch
- Visibility query accuracy

---

## Architecture

```
temporal-mongodb-tests/
├── docker/
│   └── docker-compose.yml    # MongoDB + Temporal server
├── scripts/
│   ├── setup.sh              # Infrastructure + namespace setup
│   ├── run-tests.sh          # E2E test runner
│   ├── run-load.sh           # Load test runner
│   └── teardown.sh           # Cleanup
├── tests/                    # 329 E2E tests (pytest)
├── omes/
│   └── repo/                 # Omes submodule
├── mise.toml                 # Task runner configuration
└── docs/
    └── planning/             # Roadmap and decisions
```

---

## Configuration

### Environment Variables

| Variable             | Default            | Description                        |
| -------------------- | ------------------ | ---------------------------------- |
| `NAMESPACE`          | `temporal-mongodb` | Temporal namespace                 |
| `TEMPORAL_ADDRESS`   | `localhost:7233`   | Temporal server address            |
| `TEMPORAL_IMAGE_TAG` | `1.30.0`           | Temporal server image tag          |
| `MONGODB_VERSION`    | `7.0`              | MongoDB version                    |
| `DOCKER_REGISTRY`    | `agdelen`          | Docker registry for Temporal image |

### Docker Images

| Image                     | Description                          |
| ------------------------- | ------------------------------------ |
| `agdelen/temporal:1.30.0` | Temporal server with MongoDB support |
| `mongo:7.0`               | MongoDB database                     |
| `temporalio/ui:2.35.0`    | Temporal Web UI                      |

---

## Related Resources

### Repositories

| Repository                                                    | Description                            |
| ------------------------------------------------------------- | -------------------------------------- |
| [sagdelen/temporal](https://github.com/sagdelen/temporal)     | Temporal fork with MongoDB persistence |
| [temporalio/temporal](https://github.com/temporalio/temporal) | Upstream Temporal server               |
| [temporalio/omes](https://github.com/temporalio/omes)         | Official load testing tool             |

### Documentation

- [Temporal Documentation](https://docs.temporal.io/)
- [MongoDB Persistence Setup](https://github.com/sagdelen/temporal/blob/main/docs/mongodb.md) _(coming soon)_

---

## Versioning

This test suite is versioned alongside the MongoDB persistence implementation:

| Test Suite Version | Temporal Base | MongoDB Support |
| ------------------ | ------------- | --------------- |
| 1.30.0-mongo.1     | 1.30.0        | Initial release |

---

## Contributing

1. Fork this repository
2. Create a feature branch
3. Run tests locally: `mise run tests && mise run load`
4. Submit a pull request

---

## License

MIT License - see [LICENSE](LICENSE) for details
