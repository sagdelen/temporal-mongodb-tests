# Temporal MongoDB Compatibility Matrix

## Tested Versions

| Temporal Version | MongoDB Version | Go SDK | Python SDK | Status  | Date       |
| ---------------- | --------------- | ------ | ---------- | ------- | ---------- |
| v1.30.0-mongo.1  | 7.0.24          | 1.37.0 | 1.11.0     | ✅ Pass | 2026-01-24 |

## Test Results Summary

### v1.30.0-mongo.1 + MongoDB 7.0.24

**E2E Tests**: 329/329 passed

- workflow: 36 ✅
- signal: 33 ✅
- activity: 27 ✅
- longrunning: 22 ✅
- update: 19 ✅
- dataflow: 19 ✅
- retry: 18 ✅
- local_activities: 15 ✅
- parallel: 14 ✅
- metadata: 14 ✅
- core: 14 ✅
- eagerwf: 10 ✅
- context: 10 ✅
- visibility: 9 ✅
- search: 9 ✅
- saga: 9 ✅
- lifecycle: 9 ✅
- persistence: 7 ✅
- timeout: 6 ✅
- concurrency: 6 ✅
- taskqueue: 5 ✅
- dataconverter: 5 ✅
- batch: 5 ✅
- timer: 4 ✅
- schedule: 4 ✅

**Load Tests (omes)**:

- workflow_with_single_noop_activity: 200 iterations, 50 concurrent, 6.4s ✅
- Throughput: ~31 workflows/sec

## Known Limitations

1. **Go SDK Worker**: Omes Go worker has timeout issues (SDK v1.39.0 bug suspected)
2. **Search Attributes**: Custom search attributes require manual registration
3. **Namespace**: Must be created manually (no auto-setup in custom image)

## How to Add New Test Results

1. Run full test suite
2. Update this file with results
3. Create PR with version bump
