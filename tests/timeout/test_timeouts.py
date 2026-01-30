"""Timeout tests for workflows and activities."""

import os
import uuid
import asyncio
import pytest
from datetime import timedelta
from temporalio.client import Client, WorkflowFailureError
from temporalio.worker import Worker
from temporalio import workflow, activity
from temporalio.common import RetryPolicy
from temporalio.exceptions import TimeoutError

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-timeout-queue"


@activity.defn
async def slow_activity(seconds: float) -> str:
    await asyncio.sleep(seconds)
    return "done"


@activity.defn
async def fast_activity() -> str:
    return "fast"


@activity.defn
async def heartbeat_slow_activity(seconds: float) -> str:
    for i in range(int(seconds * 10)):
        activity.heartbeat(f"tick-{i}")
        await asyncio.sleep(0.1)
    return "done"


@workflow.defn
class ActivityTimeoutWorkflow:
    @workflow.run
    async def run(self, activity_seconds: float, timeout_seconds: float) -> str:
        return await workflow.execute_activity(
            slow_activity,
            activity_seconds,
            start_to_close_timeout=timedelta(seconds=timeout_seconds),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )


@workflow.defn
class ScheduleToStartTimeoutWorkflow:
    @workflow.run
    async def run(self) -> str:
        return await workflow.execute_activity(
            fast_activity,
            schedule_to_start_timeout=timedelta(seconds=30),
            start_to_close_timeout=timedelta(seconds=30),
        )


@workflow.defn
class HeartbeatTimeoutWorkflow:
    @workflow.run
    async def run(self, activity_seconds: float) -> str:
        return await workflow.execute_activity(
            heartbeat_slow_activity,
            activity_seconds,
            start_to_close_timeout=timedelta(seconds=60),
            heartbeat_timeout=timedelta(seconds=2),
        )


@workflow.defn
class WorkflowWithTimeout:
    def __init__(self):
        self._done = False

    @workflow.run
    async def run(self) -> str:
        await workflow.wait_condition(lambda: self._done)
        return "completed"

    @workflow.signal
    async def complete(self):
        self._done = True


@pytest.mark.asyncio
async def test_activity_completes_before_timeout():
    """Test activity completes within timeout."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ActivityTimeoutWorkflow],
        activities=[slow_activity],
    ):
        workflow_id = f"test-timeout-ok-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ActivityTimeoutWorkflow.run,
            args=[0.5, 5.0],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == "done"


@pytest.mark.asyncio
async def test_activity_exceeds_timeout():
    """Test activity times out."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ActivityTimeoutWorkflow],
        activities=[slow_activity],
    ):
        workflow_id = f"test-timeout-fail-{uuid.uuid4()}"
        with pytest.raises(WorkflowFailureError):
            await client.execute_workflow(
                ActivityTimeoutWorkflow.run,
                args=[10.0, 1.0],
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )


@pytest.mark.asyncio
async def test_schedule_to_start_timeout():
    """Test schedule to start timeout."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ScheduleToStartTimeoutWorkflow],
        activities=[fast_activity],
    ):
        workflow_id = f"test-s2s-timeout-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ScheduleToStartTimeoutWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == "fast"


@pytest.mark.asyncio
async def test_heartbeat_keeps_activity_alive():
    """Test heartbeat prevents timeout."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[HeartbeatTimeoutWorkflow],
        activities=[heartbeat_slow_activity],
    ):
        workflow_id = f"test-heartbeat-alive-{uuid.uuid4()}"
        result = await client.execute_workflow(
            HeartbeatTimeoutWorkflow.run,
            1.0,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == "done"


@pytest.mark.asyncio
async def test_workflow_execution_timeout():
    """Test workflow execution timeout is respected."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ActivityTimeoutWorkflow],
        activities=[slow_activity],
    ):
        workflow_id = f"test-exec-timeout-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ActivityTimeoutWorkflow.run,
            args=[0.5, 5.0],
            id=workflow_id,
            task_queue=TASK_QUEUE,
            execution_timeout=timedelta(minutes=1),
        )
        assert result == "done"


@pytest.mark.asyncio
async def test_workflow_run_timeout():
    """Test workflow run timeout configuration."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ActivityTimeoutWorkflow],
        activities=[slow_activity],
    ):
        workflow_id = f"test-run-timeout-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ActivityTimeoutWorkflow.run,
            args=[0.5, 5.0],
            id=workflow_id,
            task_queue=TASK_QUEUE,
            run_timeout=timedelta(minutes=1),
        )
        assert result == "done"
