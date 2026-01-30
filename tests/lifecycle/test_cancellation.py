"""Cancellation and termination tests."""

import os
import uuid
import asyncio
import pytest
from datetime import timedelta
from temporalio.client import Client, WorkflowFailureError
from temporalio.worker import Worker
from temporalio import workflow, activity
from temporalio.exceptions import CancelledError

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-cancel-queue"


@activity.defn
async def cancellable_activity(sleep_seconds: float) -> str:
    try:
        await asyncio.sleep(sleep_seconds)
        return "completed"
    except asyncio.CancelledError:
        return "activity_cancelled"


@workflow.defn
class CancellableWorkflow:
    def __init__(self):
        self._cancelled = False

    @workflow.run
    async def run(self, sleep_seconds: float) -> str:
        try:
            await workflow.sleep(timedelta(seconds=sleep_seconds))
            return "completed"
        except CancelledError:
            self._cancelled = True
            return "workflow_cancelled"

    @workflow.query
    def is_cancelled(self) -> bool:
        return self._cancelled


@workflow.defn
class CancellableActivityWorkflow:
    @workflow.run
    async def run(self, sleep_seconds: float) -> str:
        try:
            result = await workflow.execute_activity(
                cancellable_activity,
                sleep_seconds,
                start_to_close_timeout=timedelta(seconds=60),
                cancellation_type=workflow.ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
            )
            return result
        except CancelledError:
            return "workflow_cancelled_during_activity"


@workflow.defn
class TerminatableWorkflow:
    def __init__(self):
        self._state = "running"

    @workflow.run
    async def run(self) -> str:
        while True:
            await workflow.sleep(timedelta(seconds=1))

    @workflow.query
    def get_state(self) -> str:
        return self._state


@workflow.defn
class CleanupOnCancelWorkflow:
    def __init__(self):
        self._cleanup_done = False

    @workflow.run
    async def run(self) -> str:
        try:
            await workflow.sleep(timedelta(seconds=60))
            return "completed"
        except CancelledError:
            # Perform cleanup
            self._cleanup_done = True
            return "cancelled_with_cleanup"

    @workflow.query
    def cleanup_done(self) -> bool:
        return self._cleanup_done


@pytest.mark.asyncio
async def test_workflow_cancel():
    """Test cancelling a running workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[CancellableWorkflow]):
        workflow_id = f"test-cancel-{uuid.uuid4()}"
        handle = await client.start_workflow(
            CancellableWorkflow.run,
            10.0,  # Long sleep
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        # Give it time to start
        await asyncio.sleep(0.5)

        # Cancel the workflow
        await handle.cancel()

        # Wait for cancellation to process
        await asyncio.sleep(1.0)

        # Verify workflow is cancelled
        desc = await handle.describe()
        assert desc.status.name in ("CANCELED", "CANCELLED")


@pytest.mark.asyncio
async def test_workflow_terminate():
    """Test terminating a running workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[TerminatableWorkflow]):
        workflow_id = f"test-terminate-{uuid.uuid4()}"
        handle = await client.start_workflow(
            TerminatableWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        # Give it time to start
        await asyncio.sleep(0.5)

        # Terminate the workflow
        await handle.terminate(reason="Test termination")

        # Verify workflow is terminated
        desc = await handle.describe()
        assert desc.status.name == "TERMINATED"


@pytest.mark.asyncio
async def test_workflow_cancel_with_cleanup():
    """Test that workflow can perform cleanup on cancellation."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client, task_queue=TASK_QUEUE, workflows=[CleanupOnCancelWorkflow]
    ):
        workflow_id = f"test-cancel-cleanup-{uuid.uuid4()}"
        handle = await client.start_workflow(
            CleanupOnCancelWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await asyncio.sleep(0.5)
        await handle.cancel()

        # Verify workflow is cancelled
        await asyncio.sleep(0.5)
        desc = await handle.describe()
        assert desc.status.name in ("CANCELED", "CANCELLED")


@pytest.mark.asyncio
async def test_cancel_before_start():
    """Test handling of workflow that completes quickly."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[CancellableWorkflow]):
        workflow_id = f"test-cancel-quick-{uuid.uuid4()}"
        result = await client.execute_workflow(
            CancellableWorkflow.run,
            0.1,  # Very short sleep
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == "completed"


@pytest.mark.asyncio
async def test_terminate_with_reason():
    """Test termination with a specific reason."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[TerminatableWorkflow]):
        workflow_id = f"test-terminate-reason-{uuid.uuid4()}"
        handle = await client.start_workflow(
            TerminatableWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await asyncio.sleep(0.5)
        await handle.terminate(reason="User requested termination")

        desc = await handle.describe()
        assert desc.status.name == "TERMINATED"
