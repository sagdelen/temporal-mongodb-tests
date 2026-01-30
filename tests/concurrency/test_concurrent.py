"""Concurrent workflow execution tests."""

import os
import uuid
import asyncio
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-concurrent-queue"


@activity.defn
async def compute_activity(value: int) -> int:
    await asyncio.sleep(0.1)
    return value * 2


@workflow.defn
class SimpleComputeWorkflow:
    @workflow.run
    async def run(self, value: int) -> int:
        return await workflow.execute_activity(
            compute_activity,
            value,
            start_to_close_timeout=timedelta(seconds=30),
        )


@workflow.defn
class ConcurrentActivitiesWorkflow:
    @workflow.run
    async def run(self, values: list[int]) -> list[int]:
        tasks = [
            workflow.execute_activity(
                compute_activity,
                v,
                start_to_close_timeout=timedelta(seconds=30),
            )
            for v in values
        ]
        return list(await asyncio.gather(*tasks))


@workflow.defn
class StatefulWorkflow:
    def __init__(self):
        self._value = 0
        self._done = False

    @workflow.run
    async def run(self) -> int:
        await workflow.wait_condition(lambda: self._done)
        return self._value

    @workflow.signal
    async def add(self, amount: int):
        self._value += amount

    @workflow.signal
    async def complete(self):
        self._done = True

    @workflow.query
    def get_value(self) -> int:
        return self._value


@pytest.mark.asyncio
async def test_multiple_concurrent_workflows():
    """Test running multiple workflows concurrently."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SimpleComputeWorkflow],
        activities=[compute_activity],
    ):
        tasks = []
        for i in range(10):
            workflow_id = f"test-concurrent-{uuid.uuid4()}"
            task = client.execute_workflow(
                SimpleComputeWorkflow.run,
                i,
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        assert results == [i * 2 for i in range(10)]


@pytest.mark.asyncio
async def test_concurrent_activities_in_workflow():
    """Test concurrent activities within single workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ConcurrentActivitiesWorkflow],
        activities=[compute_activity],
    ):
        workflow_id = f"test-concurrent-activities-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ConcurrentActivitiesWorkflow.run,
            [1, 2, 3, 4, 5],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == [2, 4, 6, 8, 10]


@pytest.mark.asyncio
async def test_concurrent_signals():
    """Test sending concurrent signals to workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StatefulWorkflow],
    ):
        workflow_id = f"test-concurrent-signals-{uuid.uuid4()}"
        handle = await client.start_workflow(
            StatefulWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        # Send multiple signals concurrently
        await asyncio.gather(
            *[handle.signal(StatefulWorkflow.add, i) for i in range(1, 11)]
        )

        # Complete and get result
        await handle.signal(StatefulWorkflow.complete)
        result = await handle.result()
        assert result == sum(range(1, 11))  # 55


@pytest.mark.asyncio
async def test_concurrent_queries():
    """Test concurrent queries to workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StatefulWorkflow],
    ):
        workflow_id = f"test-concurrent-queries-{uuid.uuid4()}"
        handle = await client.start_workflow(
            StatefulWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await handle.signal(StatefulWorkflow.add, 100)

        # Query concurrently
        queries = [handle.query(StatefulWorkflow.get_value) for _ in range(5)]
        results = await asyncio.gather(*queries)
        assert all(r == 100 for r in results)

        await handle.signal(StatefulWorkflow.complete)
        await handle.result()


@pytest.mark.asyncio
async def test_many_workflows_same_task_queue():
    """Test many workflows on same task queue."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SimpleComputeWorkflow],
        activities=[compute_activity],
    ):
        # Start 20 workflows
        handles = []
        for i in range(20):
            workflow_id = f"test-many-{uuid.uuid4()}"
            handle = await client.start_workflow(
                SimpleComputeWorkflow.run,
                i,
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )
            handles.append((handle, i))

        # Wait for all to complete
        for handle, expected_input in handles:
            result = await handle.result()
            assert result == expected_input * 2


@pytest.mark.asyncio
async def test_workflow_isolation():
    """Test that concurrent workflows are isolated."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StatefulWorkflow],
    ):
        # Start two workflows
        handle1 = await client.start_workflow(
            StatefulWorkflow.run,
            id=f"test-isolation-1-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        handle2 = await client.start_workflow(
            StatefulWorkflow.run,
            id=f"test-isolation-2-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        # Send different signals
        await handle1.signal(StatefulWorkflow.add, 10)
        await handle2.signal(StatefulWorkflow.add, 100)

        # Query both
        value1 = await handle1.query(StatefulWorkflow.get_value)
        value2 = await handle2.query(StatefulWorkflow.get_value)

        assert value1 == 10
        assert value2 == 100

        # Cleanup
        await handle1.signal(StatefulWorkflow.complete)
        await handle2.signal(StatefulWorkflow.complete)
        await handle1.result()
        await handle2.result()
