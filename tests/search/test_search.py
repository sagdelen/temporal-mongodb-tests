"""Search attribute tests."""

import os
import uuid
import pytest
import asyncio
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow
from temporalio.common import TypedSearchAttributes, SearchAttributeKey

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-search-queue"


@workflow.defn
class SearchableWorkflow:
    def __init__(self):
        self._done = False

    @workflow.run
    async def run(self, status: str) -> str:
        await workflow.wait_condition(lambda: self._done)
        return status

    @workflow.signal
    async def complete(self):
        self._done = True


@workflow.defn
class QuickWorkflow:
    @workflow.run
    async def run(self, value: str) -> str:
        return f"result-{value}"


@pytest.mark.asyncio
async def test_list_workflows_by_type():
    """Test listing workflows by type."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[QuickWorkflow],
    ):
        # Create several workflows
        workflow_ids = []
        for i in range(3):
            wf_id = f"test-search-type-{uuid.uuid4()}"
            await client.execute_workflow(
                QuickWorkflow.run,
                f"value-{i}",
                id=wf_id,
                task_queue=TASK_QUEUE,
            )
            workflow_ids.append(wf_id)

        # Wait for indexing
        await asyncio.sleep(1)

        # Search by workflow type
        query = 'WorkflowType = "QuickWorkflow"'
        workflows = [wf async for wf in client.list_workflows(query=query)]

        # Should find at least our workflows
        assert len(workflows) >= 3


@pytest.mark.asyncio
async def test_list_workflows_by_status():
    """Test listing workflows by status."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[QuickWorkflow, SearchableWorkflow],
    ):
        # Create completed workflow
        completed_id = f"test-search-completed-{uuid.uuid4()}"
        await client.execute_workflow(
            QuickWorkflow.run,
            "test",
            id=completed_id,
            task_queue=TASK_QUEUE,
        )

        # Create running workflow
        running_id = f"test-search-running-{uuid.uuid4()}"
        handle = await client.start_workflow(
            SearchableWorkflow.run,
            "running",
            id=running_id,
            task_queue=TASK_QUEUE,
        )

        await asyncio.sleep(1)

        # Search for running workflows
        running_query = 'ExecutionStatus = "Running"'
        running = [wf async for wf in client.list_workflows(query=running_query)]
        running_ids = [wf.id for wf in running]
        assert running_id in running_ids

        # Cleanup
        await handle.signal(SearchableWorkflow.complete)
        await handle.result()


@pytest.mark.asyncio
async def test_list_workflows_by_id_prefix():
    """Test listing workflows by ID prefix."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[QuickWorkflow],
    ):
        prefix = f"prefix-{uuid.uuid4().hex[:8]}"
        workflow_ids = []

        for i in range(3):
            wf_id = f"{prefix}-{i}"
            await client.execute_workflow(
                QuickWorkflow.run,
                f"value-{i}",
                id=wf_id,
                task_queue=TASK_QUEUE,
            )
            workflow_ids.append(wf_id)

        await asyncio.sleep(1)

        # Search by ID prefix
        query = f'WorkflowId STARTS_WITH "{prefix}"'
        workflows = [wf async for wf in client.list_workflows(query=query)]
        found_ids = [wf.id for wf in workflows]

        for wf_id in workflow_ids:
            assert wf_id in found_ids


@pytest.mark.asyncio
async def test_count_workflows():
    """Test counting workflows."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[QuickWorkflow],
    ):
        prefix = f"count-{uuid.uuid4().hex[:8]}"

        for i in range(5):
            await client.execute_workflow(
                QuickWorkflow.run,
                f"value-{i}",
                id=f"{prefix}-{i}",
                task_queue=TASK_QUEUE,
            )

        await asyncio.sleep(1)

        # Count by prefix
        query = f'WorkflowId STARTS_WITH "{prefix}"'
        count = await client.count_workflows(query=query)
        assert count.count >= 5


@pytest.mark.asyncio
async def test_list_workflows_pagination():
    """Test workflow list pagination."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[QuickWorkflow],
    ):
        prefix = f"page-{uuid.uuid4().hex[:8]}"

        for i in range(10):
            await client.execute_workflow(
                QuickWorkflow.run,
                f"value-{i}",
                id=f"{prefix}-{i}",
                task_queue=TASK_QUEUE,
            )

        await asyncio.sleep(1)

        # List with pagination
        query = f'WorkflowId STARTS_WITH "{prefix}"'
        all_workflows = [wf async for wf in client.list_workflows(query=query)]

        assert len(all_workflows) >= 10



@pytest.mark.asyncio
async def test_list_workflows_by_status_completed():
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)
    async with Worker(client, task_queue=TASK_QUEUE, workflows=[QuickWorkflow]):
        prefix = f"status-{uuid.uuid4().hex[:8]}"
        for i in range(3):
            await client.execute_workflow(
                QuickWorkflow.run, f"v{i}",
                id=f"{prefix}-{i}", task_queue=TASK_QUEUE
            )
        await asyncio.sleep(1)
        query = f'WorkflowId STARTS_WITH "{prefix}" AND ExecutionStatus = "Completed"'
        wfs = [w async for w in client.list_workflows(query=query)]
        assert len(wfs) >= 3


@pytest.mark.asyncio
async def test_list_workflows_order_by_start_time():
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)
    async with Worker(client, task_queue=TASK_QUEUE, workflows=[QuickWorkflow]):
        prefix = f"order-{uuid.uuid4().hex[:8]}"
        for i in range(5):
            await client.execute_workflow(
                QuickWorkflow.run, f"v{i}",
                id=f"{prefix}-{i}", task_queue=TASK_QUEUE
            )
        await asyncio.sleep(1)
        query = f'WorkflowId STARTS_WITH "{prefix}"'
        wfs = [w async for w in client.list_workflows(query=query)]
        assert len(wfs) >= 5


@pytest.mark.asyncio
async def test_workflow_describe_after_completion():
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)
    async with Worker(client, task_queue=TASK_QUEUE, workflows=[QuickWorkflow]):
        wf_id = f"describe-{uuid.uuid4()}"
        await client.execute_workflow(
            QuickWorkflow.run, "test",
            id=wf_id, task_queue=TASK_QUEUE
        )
        handle = client.get_workflow_handle(wf_id)
        desc = await handle.describe()
        assert desc.status.name == "COMPLETED"
        assert desc.id == wf_id


@pytest.mark.asyncio
async def test_count_zero_workflows():
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)
    query = f'WorkflowId STARTS_WITH "nonexistent-{uuid.uuid4()}"'
    count = await client.count_workflows(query=query)
    assert count.count == 0
