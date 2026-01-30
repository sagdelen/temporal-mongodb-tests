"""Eager workflow start tests."""

import os
import uuid
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity


TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-eager"


@activity.defn
async def quick_activity(value: str) -> str:
    """Fast activity for eager start."""
    return f"quick-{value}"


@workflow.defn
class SimpleEagerWorkflow:
    @workflow.run
    async def run(self, value: str) -> str:
        result = await workflow.execute_activity(
            quick_activity,
            value,
            start_to_close_timeout=timedelta(seconds=30),
        )
        return result


@workflow.defn
class NoActivityEagerWorkflow:
    @workflow.run
    async def run(self, value: int) -> int:
        return value * 2


@workflow.defn
class MultiActivityEagerWorkflow:
    @workflow.run
    async def run(self, values: list) -> list:
        results = []
        for val in values:
            result = await workflow.execute_activity(
                quick_activity,
                val,
                start_to_close_timeout=timedelta(seconds=30),
            )
            results.append(result)
        return results


@pytest.mark.asyncio
async def test_eager_workflow_start():
    """Test eager workflow start."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SimpleEagerWorkflow],
        activities=[quick_activity],
    ):
        handle = await client.start_workflow(
            SimpleEagerWorkflow.run,
            "test",
            id=f"test-eager-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        result = await handle.result()
        assert result == "quick-test"


@pytest.mark.asyncio
async def test_eager_workflow_no_activity():
    """Test eager start with no activities."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[NoActivityEagerWorkflow],
    ):
        handle = await client.start_workflow(
            NoActivityEagerWorkflow.run,
            42,
            id=f"test-eager-no-act-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        result = await handle.result()
        assert result == 84


@pytest.mark.asyncio
async def test_eager_workflow_multi_activity():
    """Test eager start with multiple activities."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MultiActivityEagerWorkflow],
        activities=[quick_activity],
    ):
        handle = await client.start_workflow(
            MultiActivityEagerWorkflow.run,
            ["a", "b", "c"],
            id=f"test-eager-multi-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        result = await handle.result()
        assert result == ["quick-a", "quick-b", "quick-c"]


@pytest.mark.asyncio
async def test_eager_workflow_zero():
    """Test eager workflow with zero value."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[NoActivityEagerWorkflow],
    ):
        handle = await client.start_workflow(
            NoActivityEagerWorkflow.run,
            0,
            id=f"test-eager-zero-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        result = await handle.result()
        assert result == 0


@pytest.mark.asyncio
async def test_eager_workflow_negative():
    """Test eager workflow with negative value."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[NoActivityEagerWorkflow],
    ):
        handle = await client.start_workflow(
            NoActivityEagerWorkflow.run,
            -5,
            id=f"test-eager-neg-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        result = await handle.result()
        assert result == -10


@pytest.mark.asyncio
async def test_eager_workflow_large_value():
    """Test eager workflow with large value."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[NoActivityEagerWorkflow],
    ):
        handle = await client.start_workflow(
            NoActivityEagerWorkflow.run,
            10000,
            id=f"test-eager-large-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        result = await handle.result()
        assert result == 20000


@pytest.mark.asyncio
async def test_eager_empty_string():
    """Test eager workflow with empty string."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SimpleEagerWorkflow],
        activities=[quick_activity],
    ):
        handle = await client.start_workflow(
            SimpleEagerWorkflow.run,
            "",
            id=f"test-eager-empty-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        result = await handle.result()
        assert result == "quick-"


@pytest.mark.asyncio
async def test_eager_unicode_string():
    """Test eager workflow with unicode."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SimpleEagerWorkflow],
        activities=[quick_activity],
    ):
        handle = await client.start_workflow(
            SimpleEagerWorkflow.run,
            "测试",
            id=f"test-eager-unicode-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        result = await handle.result()
        assert result == "quick-测试"


@pytest.mark.asyncio
async def test_eager_empty_list():
    """Test eager workflow with empty list."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MultiActivityEagerWorkflow],
        activities=[quick_activity],
    ):
        handle = await client.start_workflow(
            MultiActivityEagerWorkflow.run,
            [],
            id=f"test-eager-empty-list-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        result = await handle.result()
        assert result == []


@pytest.mark.asyncio
async def test_eager_single_item():
    """Test eager workflow with single item list."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MultiActivityEagerWorkflow],
        activities=[quick_activity],
    ):
        handle = await client.start_workflow(
            MultiActivityEagerWorkflow.run,
            ["single"],
            id=f"test-eager-single-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        result = await handle.result()
        assert result == ["quick-single"]
