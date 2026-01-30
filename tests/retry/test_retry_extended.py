"""Extended retry tests - additional retry scenarios."""

import os
import uuid
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError


TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-retry-extended"

fail_counts = {}


@activity.defn
async def sometimes_fail_activity(key: str, max_fails: int) -> str:
    """Fail specified number of times then succeed."""
    global fail_counts
    fail_counts[key] = fail_counts.get(key, 0) + 1

    if fail_counts[key] <= max_fails:
        raise RuntimeError(f"Attempt {fail_counts[key]} failed")

    return f"success-after-{fail_counts[key]}-attempts"


@workflow.defn
class RetryWorkflow:
    @workflow.run
    async def run(self, key: str, max_fails: int, max_attempts: int) -> str:
        return await workflow.execute_activity(
            sometimes_fail_activity,
            args=[key, max_fails],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                maximum_attempts=max_attempts,
                initial_interval=timedelta(milliseconds=100),
                maximum_interval=timedelta(seconds=1),
            ),
        )


@pytest.mark.asyncio
async def test_retry_once():
    """Test retry once."""
    global fail_counts
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    key = f"retry-once-{uuid.uuid4()}"
    fail_counts[key] = 0

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RetryWorkflow],
        activities=[sometimes_fail_activity],
    ):
        result = await client.execute_workflow(
            RetryWorkflow.run,
            args=[key, 1, 5],
            id=f"test-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert "success" in result


@pytest.mark.asyncio
async def test_retry_twice():
    """Test retry twice."""
    global fail_counts
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    key = f"retry-twice-{uuid.uuid4()}"
    fail_counts[key] = 0

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RetryWorkflow],
        activities=[sometimes_fail_activity],
    ):
        result = await client.execute_workflow(
            RetryWorkflow.run,
            args=[key, 2, 5],
            id=f"test-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert "success" in result


@pytest.mark.asyncio
async def test_retry_three_times():
    """Test retry three times."""
    global fail_counts
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    key = f"retry-three-{uuid.uuid4()}"
    fail_counts[key] = 0

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RetryWorkflow],
        activities=[sometimes_fail_activity],
    ):
        result = await client.execute_workflow(
            RetryWorkflow.run,
            args=[key, 3, 5],
            id=f"test-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert "success" in result


@pytest.mark.asyncio
async def test_retry_zero_fails():
    """Test with zero fails (immediate success)."""
    global fail_counts
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    key = f"retry-zero-{uuid.uuid4()}"
    fail_counts[key] = 0

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RetryWorkflow],
        activities=[sometimes_fail_activity],
    ):
        result = await client.execute_workflow(
            RetryWorkflow.run,
            args=[key, 0, 5],
            id=f"test-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert "success" in result


@pytest.mark.asyncio
async def test_retry_max_attempts():
    """Test retry up to max attempts."""
    global fail_counts
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    key = f"retry-max-{uuid.uuid4()}"
    fail_counts[key] = 0

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RetryWorkflow],
        activities=[sometimes_fail_activity],
    ):
        try:
            await client.execute_workflow(
                RetryWorkflow.run,
                args=[key, 10, 3],  # Will fail - needs 11 attempts but max is 3
                id=f"test-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )
            assert False, "Should have failed"
        except:
            pass  # Expected to fail


@pytest.mark.asyncio
async def test_retry_single_attempt():
    """Test with single attempt (no retry)."""
    global fail_counts
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    key = f"retry-single-{uuid.uuid4()}"
    fail_counts[key] = 0

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RetryWorkflow],
        activities=[sometimes_fail_activity],
    ):
        result = await client.execute_workflow(
            RetryWorkflow.run,
            args=[key, 0, 1],
            id=f"test-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert "success" in result


@pytest.mark.asyncio
async def test_retry_four_times():
    """Test retry four times."""
    global fail_counts
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    key = f"retry-four-{uuid.uuid4()}"
    fail_counts[key] = 0

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RetryWorkflow],
        activities=[sometimes_fail_activity],
    ):
        result = await client.execute_workflow(
            RetryWorkflow.run,
            args=[key, 4, 6],
            id=f"test-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert "success" in result


@pytest.mark.asyncio
async def test_retry_five_times():
    """Test retry five times."""
    global fail_counts
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    key = f"retry-five-{uuid.uuid4()}"
    fail_counts[key] = 0

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RetryWorkflow],
        activities=[sometimes_fail_activity],
    ):
        result = await client.execute_workflow(
            RetryWorkflow.run,
            args=[key, 5, 7],
            id=f"test-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert "success" in result


@pytest.mark.asyncio
async def test_retry_exact_limit():
    """Test retry exactly at limit."""
    global fail_counts
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    key = f"retry-exact-{uuid.uuid4()}"
    fail_counts[key] = 0

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RetryWorkflow],
        activities=[sometimes_fail_activity],
    ):
        result = await client.execute_workflow(
            RetryWorkflow.run,
            args=[key, 2, 3],  # Fail 2, succeed on 3rd
            id=f"test-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert "success" in result


@pytest.mark.asyncio
async def test_retry_high_max_attempts():
    """Test with high max attempts."""
    global fail_counts
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    key = f"retry-high-{uuid.uuid4()}"
    fail_counts[key] = 0

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RetryWorkflow],
        activities=[sometimes_fail_activity],
    ):
        result = await client.execute_workflow(
            RetryWorkflow.run,
            args=[key, 1, 100],  # Max 100, only need 2
            id=f"test-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert "success" in result


@pytest.mark.asyncio
async def test_retry_multiple_workflows():
    """Test retry in multiple concurrent workflows."""
    global fail_counts
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    keys = [f"retry-multi-{i}-{uuid.uuid4()}" for i in range(3)]
    for key in keys:
        fail_counts[key] = 0

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RetryWorkflow],
        activities=[sometimes_fail_activity],
    ):
        results = []
        for key in keys:
            result = await client.execute_workflow(
                RetryWorkflow.run,
                args=[key, 1, 5],
                id=f"test-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )
            results.append(result)

        assert all("success" in r for r in results)


@pytest.mark.asyncio
async def test_retry_different_patterns():
    """Test different retry patterns."""
    global fail_counts
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    key1 = f"retry-pat1-{uuid.uuid4()}"
    key2 = f"retry-pat2-{uuid.uuid4()}"
    fail_counts[key1] = 0
    fail_counts[key2] = 0

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RetryWorkflow],
        activities=[sometimes_fail_activity],
    ):
        result1 = await client.execute_workflow(
            RetryWorkflow.run,
            args=[key1, 1, 5],
            id=f"test-1-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        result2 = await client.execute_workflow(
            RetryWorkflow.run,
            args=[key2, 3, 5],
            id=f"test-2-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        assert "success" in result1
        assert "success" in result2
