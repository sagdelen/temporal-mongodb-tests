"""Extended workflow tests - additional workflow scenarios."""

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
TASK_QUEUE = "e2e-workflow-extended"


@activity.defn
async def compute_activity(x: int, y: int, op: str) -> int:
    """Perform computation."""
    if op == "add":
        return x + y
    elif op == "mul":
        return x * y
    elif op == "sub":
        return x - y
    else:
        return x // y if y != 0 else 0


@activity.defn
async def string_activity(text: str, op: str) -> str:
    """String operations."""
    if op == "upper":
        return text.upper()
    elif op == "lower":
        return text.lower()
    elif op == "reverse":
        return text[::-1]
    else:
        return text


@activity.defn
async def list_activity(items: list, op: str) -> list:
    """List operations."""
    if op == "sort":
        return sorted(items)
    elif op == "reverse":
        return list(reversed(items))
    elif op == "double":
        return [x * 2 if isinstance(x, int) else x for x in items]
    else:
        return items


@workflow.defn
class ComputeWorkflow:
    @workflow.run
    async def run(self, x: int, y: int, op: str) -> int:
        return await workflow.execute_activity(
            compute_activity,
            args=[x, y, op],
            start_to_close_timeout=timedelta(seconds=30),
        )


@workflow.defn
class StringWorkflow:
    @workflow.run
    async def run(self, text: str, op: str) -> str:
        return await workflow.execute_activity(
            string_activity,
            args=[text, op],
            start_to_close_timeout=timedelta(seconds=30),
        )


@workflow.defn
class ListWorkflow:
    @workflow.run
    async def run(self, items: list, op: str) -> list:
        return await workflow.execute_activity(
            list_activity,
            args=[items, op],
            start_to_close_timeout=timedelta(seconds=30),
        )


@workflow.defn
class ChainedWorkflow:
    @workflow.run
    async def run(self, initial: int) -> int:
        result = await workflow.execute_activity(
            compute_activity,
            args=[initial, 2, "mul"],
            start_to_close_timeout=timedelta(seconds=30),
        )

        result = await workflow.execute_activity(
            compute_activity,
            args=[result, 5, "add"],
            start_to_close_timeout=timedelta(seconds=30),
        )

        return result


@pytest.mark.asyncio
async def test_add_operation():
    """Test addition operation."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ComputeWorkflow],
        activities=[compute_activity],
    ):
        result = await client.execute_workflow(
            ComputeWorkflow.run,
            args=[10, 5, "add"],
            id=f"test-add-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == 15


@pytest.mark.asyncio
async def test_multiply_operation():
    """Test multiplication operation."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ComputeWorkflow],
        activities=[compute_activity],
    ):
        result = await client.execute_workflow(
            ComputeWorkflow.run,
            args=[10, 5, "mul"],
            id=f"test-mul-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == 50


@pytest.mark.asyncio
async def test_subtract_operation():
    """Test subtraction operation."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ComputeWorkflow],
        activities=[compute_activity],
    ):
        result = await client.execute_workflow(
            ComputeWorkflow.run,
            args=[10, 5, "sub"],
            id=f"test-sub-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == 5


@pytest.mark.asyncio
async def test_divide_operation():
    """Test division operation."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ComputeWorkflow],
        activities=[compute_activity],
    ):
        result = await client.execute_workflow(
            ComputeWorkflow.run,
            args=[10, 2, "div"],
            id=f"test-div-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == 5


@pytest.mark.asyncio
async def test_string_upper():
    """Test string uppercase."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StringWorkflow],
        activities=[string_activity],
    ):
        result = await client.execute_workflow(
            StringWorkflow.run,
            args=["hello", "upper"],
            id=f"test-upper-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == "HELLO"


@pytest.mark.asyncio
async def test_string_lower():
    """Test string lowercase."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StringWorkflow],
        activities=[string_activity],
    ):
        result = await client.execute_workflow(
            StringWorkflow.run,
            args=["HELLO", "lower"],
            id=f"test-lower-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == "hello"


@pytest.mark.asyncio
async def test_string_reverse():
    """Test string reverse."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StringWorkflow],
        activities=[string_activity],
    ):
        result = await client.execute_workflow(
            StringWorkflow.run,
            args=["hello", "reverse"],
            id=f"test-reverse-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == "olleh"


@pytest.mark.asyncio
async def test_list_sort():
    """Test list sorting."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ListWorkflow],
        activities=[list_activity],
    ):
        result = await client.execute_workflow(
            ListWorkflow.run,
            args=[[3, 1, 2], "sort"],
            id=f"test-sort-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == [1, 2, 3]


@pytest.mark.asyncio
async def test_list_reverse():
    """Test list reverse."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ListWorkflow],
        activities=[list_activity],
    ):
        result = await client.execute_workflow(
            ListWorkflow.run,
            args=[[1, 2, 3], "reverse"],
            id=f"test-list-rev-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == [3, 2, 1]


@pytest.mark.asyncio
async def test_list_double():
    """Test list doubling."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ListWorkflow],
        activities=[list_activity],
    ):
        result = await client.execute_workflow(
            ListWorkflow.run,
            args=[[1, 2, 3], "double"],
            id=f"test-double-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == [2, 4, 6]


@pytest.mark.asyncio
async def test_chained_workflow():
    """Test chained operations."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ChainedWorkflow],
        activities=[compute_activity],
    ):
        result = await client.execute_workflow(
            ChainedWorkflow.run,
            10,
            id=f"test-chain-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        # 10 * 2 = 20, 20 + 5 = 25
        assert result == 25


@pytest.mark.asyncio
async def test_compute_with_zero():
    """Test computation with zero."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ComputeWorkflow],
        activities=[compute_activity],
    ):
        result = await client.execute_workflow(
            ComputeWorkflow.run,
            args=[0, 5, "add"],
            id=f"test-zero-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == 5


@pytest.mark.asyncio
async def test_compute_negative():
    """Test computation with negatives."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ComputeWorkflow],
        activities=[compute_activity],
    ):
        result = await client.execute_workflow(
            ComputeWorkflow.run,
            args=[-5, 3, "add"],
            id=f"test-negative-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == -2


@pytest.mark.asyncio
async def test_string_empty():
    """Test string operation on empty string."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StringWorkflow],
        activities=[string_activity],
    ):
        result = await client.execute_workflow(
            StringWorkflow.run,
            args=["", "upper"],
            id=f"test-empty-str-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == ""


@pytest.mark.asyncio
async def test_list_empty():
    """Test list operation on empty list."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ListWorkflow],
        activities=[list_activity],
    ):
        result = await client.execute_workflow(
            ListWorkflow.run,
            args=[[], "sort"],
            id=f"test-empty-list-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == []


@pytest.mark.asyncio
async def test_list_single():
    """Test list operation on single element."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ListWorkflow],
        activities=[list_activity],
    ):
        result = await client.execute_workflow(
            ListWorkflow.run,
            args=[[42], "sort"],
            id=f"test-single-list-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == [42]


@pytest.mark.asyncio
async def test_chained_zero():
    """Test chained operations starting with zero."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ChainedWorkflow],
        activities=[compute_activity],
    ):
        result = await client.execute_workflow(
            ChainedWorkflow.run,
            0,
            id=f"test-chain-zero-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        # 0 * 2 = 0, 0 + 5 = 5
        assert result == 5


@pytest.mark.asyncio
async def test_string_unicode():
    """Test string operation on unicode."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StringWorkflow],
        activities=[string_activity],
    ):
        result = await client.execute_workflow(
            StringWorkflow.run,
            args=["测试", "reverse"],
            id=f"test-unicode-str-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == "试测"


@pytest.mark.asyncio
async def test_large_numbers():
    """Test computation with large numbers."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ComputeWorkflow],
        activities=[compute_activity],
    ):
        result = await client.execute_workflow(
            ComputeWorkflow.run,
            args=[1000000, 1000000, "add"],
            id=f"test-large-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == 2000000
