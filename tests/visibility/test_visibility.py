"""Visibility and list workflows tests."""

import os
import uuid
import asyncio
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-visibility-queue"


@workflow.defn
class TaggedWorkflow:
    @workflow.run
    async def run(self, sleep_seconds: float = 0.1) -> str:
        await workflow.sleep(timedelta(seconds=sleep_seconds))
        return "tagged_complete"


@workflow.defn
class LongRunningWorkflow:
    def __init__(self):
        self._done = False

    @workflow.run
    async def run(self) -> str:
        await workflow.wait_condition(lambda: self._done)
        return "done"

    @workflow.signal
    async def complete(self) -> None:
        self._done = True


@pytest.mark.asyncio
async def test_list_workflows():
    """Test listing workflows."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[TaggedWorkflow]):
        # Create several workflows
        prefix = f"test-list-{uuid.uuid4().hex[:8]}"
        handles = []
        for i in range(3):
            handle = await client.start_workflow(
                TaggedWorkflow.run,
                0.1,
                id=f"{prefix}-{i}",
                task_queue=TASK_QUEUE,
            )
            handles.append(handle)

        # Wait for completion
        for handle in handles:
            await handle.result()

        # List workflows with query
        await asyncio.sleep(0.5)  # Allow visibility to update
        workflows = []
        async for wf in client.list_workflows(f'WorkflowId STARTS_WITH "{prefix}"'):
            workflows.append(wf)

        assert len(workflows) >= 3


@pytest.mark.asyncio
async def test_list_running_workflows():
    """Test listing only running workflows."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[LongRunningWorkflow]):
        prefix = f"test-running-{uuid.uuid4().hex[:8]}"

        # Start workflows
        handles = []
        for i in range(2):
            handle = await client.start_workflow(
                LongRunningWorkflow.run,
                id=f"{prefix}-{i}",
                task_queue=TASK_QUEUE,
            )
            handles.append(handle)

        await asyncio.sleep(0.5)

        # List running workflows
        running = []
        async for wf in client.list_workflows(
            f'WorkflowId STARTS_WITH "{prefix}" AND ExecutionStatus = "Running"'
        ):
            running.append(wf)

        assert len(running) == 2

        # Complete workflows
        for handle in handles:
            await handle.signal(LongRunningWorkflow.complete)
            await handle.result()


@pytest.mark.asyncio
async def test_list_completed_workflows():
    """Test listing completed workflows."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[TaggedWorkflow]):
        prefix = f"test-completed-{uuid.uuid4().hex[:8]}"

        # Create and complete workflows
        for i in range(2):
            await client.execute_workflow(
                TaggedWorkflow.run,
                0.1,
                id=f"{prefix}-{i}",
                task_queue=TASK_QUEUE,
            )

        await asyncio.sleep(0.5)

        # List completed workflows
        completed = []
        async for wf in client.list_workflows(
            f'WorkflowId STARTS_WITH "{prefix}" AND ExecutionStatus = "Completed"'
        ):
            completed.append(wf)

        assert len(completed) >= 2


@pytest.mark.asyncio
async def test_count_workflows():
    """Test counting workflows."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[TaggedWorkflow]):
        prefix = f"test-count-{uuid.uuid4().hex[:8]}"

        # Create workflows
        for i in range(4):
            await client.execute_workflow(
                TaggedWorkflow.run,
                0.1,
                id=f"{prefix}-{i}",
                task_queue=TASK_QUEUE,
            )

        await asyncio.sleep(0.5)

        # Count workflows
        count = await client.count_workflows(f'WorkflowId STARTS_WITH "{prefix}"')
        assert count.count >= 4


@pytest.mark.asyncio
async def test_describe_workflow():
    """Test describing a specific workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[TaggedWorkflow]):
        workflow_id = f"test-describe-{uuid.uuid4()}"
        await client.execute_workflow(
            TaggedWorkflow.run,
            0.1,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        handle = client.get_workflow_handle(workflow_id)
        desc = await handle.describe()

        assert desc.id == workflow_id
        assert desc.status.name == "COMPLETED"
        assert desc.workflow_type == "TaggedWorkflow"
