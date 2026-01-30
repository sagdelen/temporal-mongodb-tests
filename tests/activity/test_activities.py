"""Activity tests - retries, heartbeat, timeouts."""

import os
import uuid
import asyncio
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-activity-queue"

# Track activity attempts for retry testing
activity_attempts: dict[str, int] = {}


@activity.defn
async def simple_activity(value: str) -> str:
    return f"processed-{value}"


@activity.defn
async def slow_activity(sleep_seconds: float) -> str:
    await asyncio.sleep(sleep_seconds)
    return "slow_done"


@activity.defn
async def heartbeat_activity(iterations: int, interval: float) -> int:
    for i in range(iterations):
        activity.heartbeat(f"iteration-{i}")
        await asyncio.sleep(interval)
    return iterations


@activity.defn
async def failing_activity(key: str, fail_times: int) -> str:
    global activity_attempts
    activity_attempts[key] = activity_attempts.get(key, 0) + 1
    if activity_attempts[key] <= fail_times:
        raise RuntimeError(f"Intentional failure {activity_attempts[key]}")
    return f"succeeded-after-{activity_attempts[key]}-attempts"


@activity.defn
async def multi_step_activity(steps: list[str]) -> list[str]:
    results = []
    for i, step in enumerate(steps):
        activity.heartbeat(f"step-{i}")
        results.append(f"completed-{step}")
        await asyncio.sleep(0.1)
    return results


@workflow.defn
class SimpleActivityWorkflow:
    @workflow.run
    async def run(self, value: str) -> str:
        return await workflow.execute_activity(
            simple_activity,
            value,
            start_to_close_timeout=timedelta(seconds=30),
        )


@workflow.defn
class MultipleActivitiesWorkflow:
    @workflow.run
    async def run(self, values: list[str]) -> list[str]:
        results = []
        for value in values:
            result = await workflow.execute_activity(
                simple_activity,
                value,
                start_to_close_timeout=timedelta(seconds=30),
            )
            results.append(result)
        return results


@workflow.defn
class HeartbeatWorkflow:
    @workflow.run
    async def run(self, iterations: int) -> int:
        return await workflow.execute_activity(
            heartbeat_activity,
            args=[iterations, 0.2],
            start_to_close_timeout=timedelta(seconds=60),
            heartbeat_timeout=timedelta(seconds=5),
        )


@workflow.defn
class RetryActivityWorkflow:
    @workflow.run
    async def run(self, key: str, fail_times: int) -> str:
        return await workflow.execute_activity(
            failing_activity,
            args=[key, fail_times],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(milliseconds=100),
                maximum_interval=timedelta(seconds=1),
                maximum_attempts=5,
            ),
        )


@workflow.defn
class ParallelActivitiesWorkflow:
    @workflow.run
    async def run(self, values: list[str]) -> list[str]:
        tasks = [
            workflow.execute_activity(
                simple_activity,
                value,
                start_to_close_timeout=timedelta(seconds=30),
            )
            for value in values
        ]
        return await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_single_activity():
    """Test single activity execution."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SimpleActivityWorkflow],
        activities=[simple_activity],
    ):
        workflow_id = f"test-activity-single-{uuid.uuid4()}"
        result = await client.execute_workflow(
            SimpleActivityWorkflow.run,
            "test-value",
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == "processed-test-value"


@pytest.mark.asyncio
async def test_multiple_sequential_activities():
    """Test multiple sequential activities."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MultipleActivitiesWorkflow],
        activities=[simple_activity],
    ):
        workflow_id = f"test-activity-multi-{uuid.uuid4()}"
        result = await client.execute_workflow(
            MultipleActivitiesWorkflow.run,
            ["a", "b", "c"],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == ["processed-a", "processed-b", "processed-c"]


@pytest.mark.asyncio
async def test_parallel_activities():
    """Test parallel activity execution."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ParallelActivitiesWorkflow],
        activities=[simple_activity],
    ):
        workflow_id = f"test-activity-parallel-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ParallelActivitiesWorkflow.run,
            ["x", "y", "z"],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert set(result) == {"processed-x", "processed-y", "processed-z"}


@pytest.mark.asyncio
async def test_activity_heartbeat():
    """Test activity heartbeat functionality."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[HeartbeatWorkflow],
        activities=[heartbeat_activity],
    ):
        workflow_id = f"test-activity-heartbeat-{uuid.uuid4()}"
        result = await client.execute_workflow(
            HeartbeatWorkflow.run,
            5,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == 5


@pytest.mark.asyncio
async def test_activity_retry_success():
    """Test activity retry that eventually succeeds."""
    global activity_attempts
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RetryActivityWorkflow],
        activities=[failing_activity],
    ):
        key = f"retry-{uuid.uuid4()}"
        activity_attempts[key] = 0
        workflow_id = f"test-activity-retry-{uuid.uuid4()}"
        result = await client.execute_workflow(
            RetryActivityWorkflow.run,
            args=[key, 2],  # Fail 2 times, succeed on 3rd
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert "succeeded-after-3-attempts" in result


@pytest.mark.asyncio
async def test_activity_retry_exhausted():
    """Test activity retry that exhausts all attempts."""
    global activity_attempts
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RetryActivityWorkflow],
        activities=[failing_activity],
    ):
        key = f"retry-exhaust-{uuid.uuid4()}"
        activity_attempts[key] = 0
        workflow_id = f"test-activity-retry-fail-{uuid.uuid4()}"
        with pytest.raises(Exception):
            await client.execute_workflow(
                RetryActivityWorkflow.run,
                args=[key, 10],  # Fail 10 times, max attempts is 5
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )
