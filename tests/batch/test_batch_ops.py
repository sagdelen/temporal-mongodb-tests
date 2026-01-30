"""Batch operations tests."""

import os
import uuid
import pytest
import asyncio
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow


TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-batch-queue"


@workflow.defn
class BatchWorkflow:
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
async def test_start_multiple_workflows():
    """Test starting multiple workflows."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[BatchWorkflow]):
        handles = []
        for i in range(5):
            workflow_id = f"test-batch-{i}-{uuid.uuid4()}"
            handle = await client.start_workflow(
                BatchWorkflow.run,
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )
            handles.append(handle)

        for handle in handles:
            await handle.signal(BatchWorkflow.complete)

        results = await asyncio.gather(*[h.result() for h in handles])
        assert all(r == "completed" for r in results)


@pytest.mark.asyncio
async def test_signal_multiple_workflows():
    """Test signaling multiple workflows."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[BatchWorkflow]):
        handles = []
        for i in range(3):
            workflow_id = f"test-multi-signal-{i}-{uuid.uuid4()}"
            handle = await client.start_workflow(
                BatchWorkflow.run,
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )
            handles.append(handle)

        for handle in handles:
            await handle.signal(BatchWorkflow.complete)

        results = await asyncio.gather(*[h.result() for h in handles])
        assert len(results) == 3


@pytest.mark.asyncio
async def test_terminate_multiple_workflows():
    """Test terminating multiple workflows."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[BatchWorkflow]):
        handles = []
        for i in range(3):
            workflow_id = f"test-multi-term-{i}-{uuid.uuid4()}"
            handle = await client.start_workflow(
                BatchWorkflow.run,
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )
            handles.append(handle)

        for handle in handles:
            await handle.terminate("batch-terminate")

        await asyncio.sleep(1)

        for handle in handles:
            desc = await handle.describe()
            from temporalio.client import WorkflowExecutionStatus

            assert desc.status == WorkflowExecutionStatus.TERMINATED


@pytest.mark.asyncio
async def test_cancel_multiple_workflows():
    """Test canceling multiple workflows."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[BatchWorkflow]):
        handles = []
        for i in range(3):
            workflow_id = f"test-multi-cancel-{i}-{uuid.uuid4()}"
            handle = await client.start_workflow(
                BatchWorkflow.run,
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )
            handles.append(handle)

        for handle in handles:
            await handle.cancel()

        await asyncio.sleep(1)


@pytest.mark.asyncio
async def test_concurrent_workflow_execution():
    """Test concurrent workflow execution."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[BatchWorkflow]):
        tasks = []
        for i in range(5):
            workflow_id = f"test-concurrent-{i}-{uuid.uuid4()}"
            task = client.start_workflow(
                BatchWorkflow.run,
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )
            tasks.append(task)

        handles = await asyncio.gather(*tasks)
        assert len(handles) == 5

        for handle in handles:
            await handle.signal(BatchWorkflow.complete)
            await handle.result()
