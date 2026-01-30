"""Child workflow tests."""

import os
import uuid
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity
from temporalio.common import RetryPolicy

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-child-queue"


@workflow.defn
class ChildWorkflow:
    @workflow.run
    async def run(self, value: int) -> int:
        return value * 2


@workflow.defn
class ParentWorkflow:
    @workflow.run
    async def run(self, value: int) -> int:
        child_result = await workflow.execute_child_workflow(
            ChildWorkflow.run,
            value,
            id=f"{workflow.info().workflow_id}-child",
        )
        return child_result + 1


@workflow.defn
class MultiChildWorkflow:
    @workflow.run
    async def run(self, values: list[int]) -> list[int]:
        results = []
        for i, value in enumerate(values):
            result = await workflow.execute_child_workflow(
                ChildWorkflow.run,
                value,
                id=f"{workflow.info().workflow_id}-child-{i}",
            )
            results.append(result)
        return results


@workflow.defn
class NestedChildWorkflow:
    @workflow.run
    async def run(self, depth: int, value: int) -> int:
        if depth <= 0:
            return value
        child_result = await workflow.execute_child_workflow(
            NestedChildWorkflow.run,
            args=[depth - 1, value * 2],
            id=f"{workflow.info().workflow_id}-nested-{depth}",
        )
        return child_result


@pytest.mark.asyncio
async def test_simple_child_workflow():
    """Test basic child workflow execution."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ParentWorkflow, ChildWorkflow],
    ):
        workflow_id = f"test-child-simple-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ParentWorkflow.run,
            5,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        # child: 5 * 2 = 10, parent: 10 + 1 = 11
        assert result == 11


@pytest.mark.asyncio
async def test_multiple_child_workflows():
    """Test multiple sequential child workflows."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MultiChildWorkflow, ChildWorkflow],
    ):
        workflow_id = f"test-child-multi-{uuid.uuid4()}"
        result = await client.execute_workflow(
            MultiChildWorkflow.run,
            [1, 2, 3, 4, 5],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == [2, 4, 6, 8, 10]


@pytest.mark.asyncio
async def test_nested_child_workflows():
    """Test nested child workflows (child calling child)."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[NestedChildWorkflow],
    ):
        workflow_id = f"test-child-nested-{uuid.uuid4()}"
        # depth=3, value=1: 1 -> 2 -> 4 -> 8
        result = await client.execute_workflow(
            NestedChildWorkflow.run,
            args=[3, 1],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == 8


@pytest.mark.asyncio
async def test_child_workflow_history():
    """Test that child workflow history is recorded."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ParentWorkflow, ChildWorkflow],
    ):
        workflow_id = f"test-child-history-{uuid.uuid4()}"
        await client.execute_workflow(
            ParentWorkflow.run,
            10,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        # Check parent workflow
        handle = client.get_workflow_handle(workflow_id)
        desc = await handle.describe()
        assert desc.status.name == "COMPLETED"

        # Check child workflow
        child_handle = client.get_workflow_handle(f"{workflow_id}-child")
        child_desc = await child_handle.describe()
        assert child_desc.status.name == "COMPLETED"



# Additional child workflow tests for MongoDB validation

import asyncio


@workflow.defn
class ParallelChildrenWorkflow:
    @workflow.run
    async def run(self, values: list[int]) -> list[int]:
        tasks = []
        for i, value in enumerate(values):
            tasks.append(
                workflow.execute_child_workflow(
                    ChildWorkflow.run,
                    value,
                    id=f"{workflow.info().workflow_id}-parallel-{i}",
                )
            )
        return list(await asyncio.gather(*tasks))


@pytest.mark.asyncio
async def test_parallel_children():
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)
    async with Worker(client, task_queue=TASK_QUEUE, workflows=[ParallelChildrenWorkflow, ChildWorkflow]):
        result = await client.execute_workflow(
            ParallelChildrenWorkflow.run, [1, 2, 3, 4, 5],
            id=f"test-parallel-{uuid.uuid4()}", task_queue=TASK_QUEUE
        )
        assert sorted(result) == [2, 4, 6, 8, 10]


@workflow.defn
class GrandparentWorkflow:
    @workflow.run
    async def run(self, value: int) -> int:
        return await workflow.execute_child_workflow(
            ParentWorkflow.run, value,
            id=f"{workflow.info().workflow_id}-parent"
        )


@pytest.mark.asyncio
async def test_grandparent_chain():
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)
    async with Worker(client, task_queue=TASK_QUEUE, workflows=[GrandparentWorkflow, ParentWorkflow, ChildWorkflow]):
        result = await client.execute_workflow(
            GrandparentWorkflow.run, 5,
            id=f"test-grandparent-{uuid.uuid4()}", task_queue=TASK_QUEUE
        )
        assert result == 11


@pytest.mark.asyncio
async def test_parallel_10_children():
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)
    async with Worker(client, task_queue=TASK_QUEUE, workflows=[ParallelChildrenWorkflow, ChildWorkflow]):
        result = await client.execute_workflow(
            ParallelChildrenWorkflow.run, list(range(10)),
            id=f"test-par10-{uuid.uuid4()}", task_queue=TASK_QUEUE
        )
        assert sorted(result) == [i*2 for i in range(10)]


@pytest.mark.asyncio
async def test_deep_nesting_5():
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)
    async with Worker(client, task_queue=TASK_QUEUE, workflows=[NestedChildWorkflow]):
        result = await client.execute_workflow(
            NestedChildWorkflow.run, args=[5, 1],
            id=f"test-deep5-{uuid.uuid4()}", task_queue=TASK_QUEUE
        )
        assert result == 32


@pytest.mark.asyncio
async def test_child_zero():
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)
    async with Worker(client, task_queue=TASK_QUEUE, workflows=[ParentWorkflow, ChildWorkflow]):
        result = await client.execute_workflow(
            ParentWorkflow.run, 0,
            id=f"test-zero-{uuid.uuid4()}", task_queue=TASK_QUEUE
        )
        assert result == 1


@pytest.mark.asyncio
async def test_child_negative():
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)
    async with Worker(client, task_queue=TASK_QUEUE, workflows=[ParentWorkflow, ChildWorkflow]):
        result = await client.execute_workflow(
            ParentWorkflow.run, -5,
            id=f"test-neg-{uuid.uuid4()}", task_queue=TASK_QUEUE
        )
        assert result == -9
