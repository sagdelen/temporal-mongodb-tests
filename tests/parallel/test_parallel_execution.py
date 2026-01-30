"""Parallel workflow execution tests."""

import os
import uuid
import pytest
import asyncio
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity


TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-parallel"


@activity.defn
async def compute_task(value: int) -> int:
    """Simulates computation."""
    await asyncio.sleep(0.1)
    return value * 2


@activity.defn
async def aggregate_results(results: list) -> int:
    """Aggregate results."""
    return sum(results)


@workflow.defn
class ParallelActivityWorkflow:
    @workflow.run
    async def run(self, values: list) -> list:
        # Execute activities in parallel
        tasks = []
        for value in values:
            task = workflow.execute_activity(
                compute_task,
                value,
                start_to_close_timeout=timedelta(seconds=30),
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        return list(results)


@workflow.defn
class SimpleWorkflow:
    @workflow.run
    async def run(self, value: int) -> int:
        result = await workflow.execute_activity(
            compute_task,
            value,
            start_to_close_timeout=timedelta(seconds=30),
        )
        return result


@workflow.defn
class AggregateWorkflow:
    @workflow.run
    async def run(self, values: list) -> int:
        # Compute in parallel
        tasks = []
        for value in values:
            task = workflow.execute_activity(
                compute_task,
                value,
                start_to_close_timeout=timedelta(seconds=30),
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Aggregate
        total = await workflow.execute_activity(
            aggregate_results,
            list(results),
            start_to_close_timeout=timedelta(seconds=30),
        )
        return total


@pytest.mark.asyncio
async def test_parallel_activities():
    """Test parallel activity execution within single workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ParallelActivityWorkflow],
        activities=[compute_task],
    ):
        workflow_id = f"test-parallel-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ParallelActivityWorkflow.run,
            [1, 2, 3, 4, 5],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == [2, 4, 6, 8, 10]


@pytest.mark.asyncio
async def test_parallel_workflows():
    """Test multiple workflows running in parallel."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SimpleWorkflow],
        activities=[compute_task],
    ):
        # Start multiple workflows
        handles = []
        for i in range(5):
            handle = await client.start_workflow(
                SimpleWorkflow.run,
                i,
                id=f"test-parallel-wf-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )
            handles.append(handle)

        # Wait for all to complete
        results = await asyncio.gather(*[h.result() for h in handles])
        assert results == [0, 2, 4, 6, 8]


@pytest.mark.asyncio
async def test_parallel_activities_with_aggregation():
    """Test parallel activities followed by aggregation."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AggregateWorkflow],
        activities=[compute_task, aggregate_results],
    ):
        workflow_id = f"test-aggregate-{uuid.uuid4()}"
        result = await client.execute_workflow(
            AggregateWorkflow.run,
            [1, 2, 3, 4, 5],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        # Sum of [2, 4, 6, 8, 10] = 30
        assert result == 30


@pytest.mark.asyncio
async def test_parallel_single_activity():
    """Test parallel execution with single activity."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ParallelActivityWorkflow],
        activities=[compute_task],
    ):
        workflow_id = f"test-single-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ParallelActivityWorkflow.run,
            [10],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == [20]


@pytest.mark.asyncio
async def test_parallel_empty_list():
    """Test parallel execution with empty list."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ParallelActivityWorkflow],
        activities=[compute_task],
    ):
        workflow_id = f"test-empty-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ParallelActivityWorkflow.run,
            [],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == []


@pytest.mark.asyncio
async def test_parallel_large_batch():
    """Test parallel execution with large batch."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ParallelActivityWorkflow],
        activities=[compute_task],
    ):
        values = list(range(20))
        workflow_id = f"test-batch-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ParallelActivityWorkflow.run,
            values,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        expected = [v * 2 for v in values]
        assert result == expected


@pytest.mark.asyncio
async def test_parallel_workflows_different_inputs():
    """Test parallel workflows with different inputs."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SimpleWorkflow],
        activities=[compute_task],
    ):
        values = [1, 5, 10, 15, 20]
        handles = []

        for val in values:
            handle = await client.start_workflow(
                SimpleWorkflow.run,
                val,
                id=f"test-diff-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )
            handles.append(handle)

        results = await asyncio.gather(*[h.result() for h in handles])
        assert results == [2, 10, 20, 30, 40]


@pytest.mark.asyncio
async def test_parallel_zero_values():
    """Test parallel execution with zero values."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ParallelActivityWorkflow],
        activities=[compute_task],
    ):
        workflow_id = f"test-zeros-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ParallelActivityWorkflow.run,
            [0, 0, 0],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == [0, 0, 0]


@pytest.mark.asyncio
async def test_parallel_negative_values():
    """Test parallel execution with negative values."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ParallelActivityWorkflow],
        activities=[compute_task],
    ):
        workflow_id = f"test-negative-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ParallelActivityWorkflow.run,
            [-1, -2, -3],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == [-2, -4, -6]


@pytest.mark.asyncio
async def test_parallel_mixed_values():
    """Test parallel execution with mixed positive/negative values."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ParallelActivityWorkflow],
        activities=[compute_task],
    ):
        workflow_id = f"test-mixed-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ParallelActivityWorkflow.run,
            [-5, 0, 5, 10],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == [-10, 0, 10, 20]


@pytest.mark.asyncio
async def test_aggregate_empty_list():
    """Test aggregation with empty list."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AggregateWorkflow],
        activities=[compute_task, aggregate_results],
    ):
        workflow_id = f"test-agg-empty-{uuid.uuid4()}"
        result = await client.execute_workflow(
            AggregateWorkflow.run,
            [],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == 0


@pytest.mark.asyncio
async def test_aggregate_single_value():
    """Test aggregation with single value."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AggregateWorkflow],
        activities=[compute_task, aggregate_results],
    ):
        workflow_id = f"test-agg-single-{uuid.uuid4()}"
        result = await client.execute_workflow(
            AggregateWorkflow.run,
            [10],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == 20


@pytest.mark.asyncio
async def test_aggregate_large_batch():
    """Test aggregation with large batch."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AggregateWorkflow],
        activities=[compute_task, aggregate_results],
    ):
        values = list(range(1, 11))  # 1 to 10
        workflow_id = f"test-agg-batch-{uuid.uuid4()}"
        result = await client.execute_workflow(
            AggregateWorkflow.run,
            values,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        # Sum of 1-10 is 55, doubled is 110
        assert result == 110


@pytest.mark.asyncio
async def test_parallel_workflows_single():
    """Test single workflow in parallel pattern."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SimpleWorkflow],
        activities=[compute_task],
    ):
        handle = await client.start_workflow(
            SimpleWorkflow.run,
            100,
            id=f"test-single-wf-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        result = await handle.result()
        assert result == 200
