"""Timer and sleep tests."""

import os
import uuid
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-timer-queue"


@workflow.defn
class TimerWorkflow:
    @workflow.run
    async def run(self, sleep_seconds: float) -> str:
        await workflow.sleep(timedelta(seconds=sleep_seconds))
        return "timer_completed"


@workflow.defn
class MultiTimerWorkflow:
    @workflow.run
    async def run(self, intervals: list[float]) -> list[str]:
        results = []
        for i, interval in enumerate(intervals):
            await workflow.sleep(timedelta(seconds=interval))
            results.append(f"timer_{i}_done")
        return results


@workflow.defn
class TimerWithSignalWorkflow:
    def __init__(self):
        self._cancelled = False

    @workflow.run
    async def run(self, sleep_seconds: float) -> str:
        try:
            await workflow.sleep(timedelta(seconds=sleep_seconds))
            return "timer_completed"
        except workflow.CancelledError:
            return "timer_cancelled"

    @workflow.signal
    async def cancel_timer(self) -> None:
        self._cancelled = True


@pytest.mark.asyncio
async def test_short_timer():
    """Test short duration timer."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[TimerWorkflow]):
        workflow_id = f"test-timer-short-{uuid.uuid4()}"
        result = await client.execute_workflow(
            TimerWorkflow.run,
            0.5,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == "timer_completed"


@pytest.mark.asyncio
async def test_multiple_sequential_timers():
    """Test multiple sequential timers."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[MultiTimerWorkflow]):
        workflow_id = f"test-timer-multi-{uuid.uuid4()}"
        result = await client.execute_workflow(
            MultiTimerWorkflow.run,
            [0.2, 0.2, 0.2],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == ["timer_0_done", "timer_1_done", "timer_2_done"]


@pytest.mark.asyncio
async def test_timer_persistence():
    """Test that timer state is persisted correctly."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[TimerWorkflow]):
        workflow_id = f"test-timer-persist-{uuid.uuid4()}"
        handle = await client.start_workflow(
            TimerWorkflow.run,
            1.0,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        # Check workflow is running
        desc = await handle.describe()
        assert desc.status.name == "RUNNING"

        # Wait for completion
        result = await handle.result()
        assert result == "timer_completed"

        # Verify final state
        desc = await handle.describe()
        assert desc.status.name == "COMPLETED"


@pytest.mark.asyncio
async def test_zero_timer():
    """Test zero duration timer (should complete immediately)."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[TimerWorkflow]):
        workflow_id = f"test-timer-zero-{uuid.uuid4()}"
        result = await client.execute_workflow(
            TimerWorkflow.run,
            0,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == "timer_completed"
