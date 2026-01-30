"""Query edge cases and advanced scenarios tests."""

import os
import uuid
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow


TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-query-advanced-queue"


@workflow.defn
class MultiQueryWorkflow:
    """Workflow with multiple query handlers."""

    def __init__(self):
        self._name = "default"
        self._count = 0
        self._items: list[str] = []
        self._done = False

    @workflow.run
    async def run(self) -> str:
        await workflow.wait_condition(lambda: self._done)
        return "completed"

    @workflow.signal
    async def set_name(self, name: str):
        self._name = name

    @workflow.signal
    async def increment(self):
        self._count += 1

    @workflow.signal
    async def add_item(self, item: str):
        self._items.append(item)

    @workflow.signal
    async def complete(self):
        self._done = True

    @workflow.query
    def get_name(self) -> str:
        return self._name

    @workflow.query
    def get_count(self) -> int:
        return self._count

    @workflow.query
    def get_items(self) -> list[str]:
        return self._items

    @workflow.query
    def get_all(self) -> dict:
        return {
            "name": self._name,
            "count": self._count,
            "items": self._items,
        }


@workflow.defn
class ComputedQueryWorkflow:
    """Workflow with computed query results."""

    def __init__(self):
        self._values: list[int] = []
        self._done = False

    @workflow.run
    async def run(self) -> dict:
        await workflow.wait_condition(lambda: self._done)
        return self._get_stats()

    @workflow.signal
    async def add_value(self, value: int):
        self._values.append(value)

    @workflow.signal
    async def complete(self):
        self._done = True

    def _get_stats(self) -> dict:
        if not self._values:
            return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}
        return {
            "count": len(self._values),
            "sum": sum(self._values),
            "avg": sum(self._values) / len(self._values),
            "min": min(self._values),
            "max": max(self._values),
        }

    @workflow.query
    def get_stats(self) -> dict:
        return self._get_stats()


@pytest.mark.asyncio
async def test_multiple_query_handlers():
    """Test workflow with multiple query handlers."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[MultiQueryWorkflow]):
        workflow_id = f"test-multi-query-{uuid.uuid4()}"
        handle = await client.start_workflow(
            MultiQueryWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await handle.signal(MultiQueryWorkflow.set_name, "test")
        await handle.signal(MultiQueryWorkflow.increment)
        await handle.signal(MultiQueryWorkflow.increment)
        await handle.signal(MultiQueryWorkflow.add_item, "item1")

        name = await handle.query(MultiQueryWorkflow.get_name)
        assert name == "test"

        count = await handle.query(MultiQueryWorkflow.get_count)
        assert count == 2

        items = await handle.query(MultiQueryWorkflow.get_items)
        assert items == ["item1"]

        await handle.signal(MultiQueryWorkflow.complete)
        await handle.result()


@pytest.mark.asyncio
async def test_get_all_query():
    """Test query that returns all state."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[MultiQueryWorkflow]):
        workflow_id = f"test-all-query-{uuid.uuid4()}"
        handle = await client.start_workflow(
            MultiQueryWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await handle.signal(MultiQueryWorkflow.set_name, "myworkflow")
        await handle.signal(MultiQueryWorkflow.increment)
        await handle.signal(MultiQueryWorkflow.add_item, "a")
        await handle.signal(MultiQueryWorkflow.add_item, "b")

        all_state = await handle.query(MultiQueryWorkflow.get_all)
        assert all_state["name"] == "myworkflow"
        assert all_state["count"] == 1
        assert all_state["items"] == ["a", "b"]

        await handle.signal(MultiQueryWorkflow.complete)
        await handle.result()


@pytest.mark.asyncio
async def test_computed_query_empty():
    """Test computed query with empty state."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[ComputedQueryWorkflow]):
        workflow_id = f"test-computed-empty-{uuid.uuid4()}"
        handle = await client.start_workflow(
            ComputedQueryWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        stats = await handle.query(ComputedQueryWorkflow.get_stats)
        assert stats["count"] == 0
        assert stats["sum"] == 0

        await handle.signal(ComputedQueryWorkflow.complete)
        await handle.result()


@pytest.mark.asyncio
async def test_computed_query_with_data():
    """Test computed query with data."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[ComputedQueryWorkflow]):
        workflow_id = f"test-computed-data-{uuid.uuid4()}"
        handle = await client.start_workflow(
            ComputedQueryWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        for v in [10, 20, 30, 40, 50]:
            await handle.signal(ComputedQueryWorkflow.add_value, v)

        stats = await handle.query(ComputedQueryWorkflow.get_stats)
        assert stats["count"] == 5
        assert stats["sum"] == 150
        assert stats["avg"] == 30
        assert stats["min"] == 10
        assert stats["max"] == 50

        await handle.signal(ComputedQueryWorkflow.complete)
        await handle.result()


@pytest.mark.asyncio
async def test_query_on_completed_workflow():
    """Test querying a completed workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[MultiQueryWorkflow]):
        workflow_id = f"test-query-completed-{uuid.uuid4()}"
        handle = await client.start_workflow(
            MultiQueryWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await handle.signal(MultiQueryWorkflow.set_name, "finished")
        await handle.signal(MultiQueryWorkflow.complete)
        await handle.result()

        name = await handle.query(MultiQueryWorkflow.get_name)
        assert name == "finished"
