"""Extended activity tests - additional activity scenarios."""

import os
import uuid
import pytest
import asyncio
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity
from temporalio.exceptions import ActivityError


TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-activity-extended"


@activity.defn
async def data_processing_activity(data: list) -> list:
    """Process list of data."""
    return [item.upper() if isinstance(item, str) else item for item in data]


@activity.defn
async def aggregation_activity(numbers: list) -> dict:
    """Aggregate numbers."""
    return {
        "sum": sum(numbers),
        "count": len(numbers),
        "avg": sum(numbers) / len(numbers) if numbers else 0,
    }


@activity.defn
async def conditional_activity(value: int, threshold: int) -> bool:
    """Check if value exceeds threshold."""
    return value > threshold


@activity.defn
async def multi_return_activity(input_val: str) -> dict:
    """Return multiple values."""
    return {
        "original": input_val,
        "upper": input_val.upper(),
        "lower": input_val.lower(),
        "length": len(input_val),
    }


@activity.defn
async def json_activity(data: dict) -> dict:
    """Process JSON-like data."""
    result = data.copy()
    result["processed"] = True
    return result


@workflow.defn
class DataProcessingWorkflow:
    @workflow.run
    async def run(self, data: list) -> list:
        return await workflow.execute_activity(
            data_processing_activity,
            data,
            start_to_close_timeout=timedelta(seconds=30),
        )


@workflow.defn
class AggregationWorkflow:
    @workflow.run
    async def run(self, numbers: list) -> dict:
        return await workflow.execute_activity(
            aggregation_activity,
            numbers,
            start_to_close_timeout=timedelta(seconds=30),
        )


@workflow.defn
class ConditionalWorkflow:
    @workflow.run
    async def run(self, value: int, threshold: int) -> bool:
        return await workflow.execute_activity(
            conditional_activity,
            args=[value, threshold],
            start_to_close_timeout=timedelta(seconds=30),
        )


@workflow.defn
class MultiReturnWorkflow:
    @workflow.run
    async def run(self, input_val: str) -> dict:
        return await workflow.execute_activity(
            multi_return_activity,
            input_val,
            start_to_close_timeout=timedelta(seconds=30),
        )


@workflow.defn
class JsonWorkflow:
    @workflow.run
    async def run(self, data: dict) -> dict:
        return await workflow.execute_activity(
            json_activity,
            data,
            start_to_close_timeout=timedelta(seconds=30),
        )


@pytest.mark.asyncio
async def test_data_processing():
    """Test data processing activity."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DataProcessingWorkflow],
        activities=[data_processing_activity],
    ):
        result = await client.execute_workflow(
            DataProcessingWorkflow.run,
            ["hello", "world"],
            id=f"test-data-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == ["HELLO", "WORLD"]


@pytest.mark.asyncio
async def test_aggregation():
    """Test aggregation activity."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AggregationWorkflow],
        activities=[aggregation_activity],
    ):
        result = await client.execute_workflow(
            AggregationWorkflow.run,
            [1, 2, 3, 4, 5],
            id=f"test-agg-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["sum"] == 15
        assert result["count"] == 5
        assert result["avg"] == 3.0


@pytest.mark.asyncio
async def test_conditional_true():
    """Test conditional activity returning true."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ConditionalWorkflow],
        activities=[conditional_activity],
    ):
        result = await client.execute_workflow(
            ConditionalWorkflow.run,
            args=[10, 5],
            id=f"test-cond-true-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result is True


@pytest.mark.asyncio
async def test_conditional_false():
    """Test conditional activity returning false."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ConditionalWorkflow],
        activities=[conditional_activity],
    ):
        result = await client.execute_workflow(
            ConditionalWorkflow.run,
            args=[5, 10],
            id=f"test-cond-false-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result is False


@pytest.mark.asyncio
async def test_conditional_equal():
    """Test conditional activity with equal values."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ConditionalWorkflow],
        activities=[conditional_activity],
    ):
        result = await client.execute_workflow(
            ConditionalWorkflow.run,
            args=[5, 5],
            id=f"test-cond-eq-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result is False


@pytest.mark.asyncio
async def test_multi_return():
    """Test activity returning multiple values."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MultiReturnWorkflow],
        activities=[multi_return_activity],
    ):
        result = await client.execute_workflow(
            MultiReturnWorkflow.run,
            "TeSt",
            id=f"test-multi-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["original"] == "TeSt"
        assert result["upper"] == "TEST"
        assert result["lower"] == "test"
        assert result["length"] == 4


@pytest.mark.asyncio
async def test_json_processing():
    """Test JSON data processing."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[JsonWorkflow],
        activities=[json_activity],
    ):
        result = await client.execute_workflow(
            JsonWorkflow.run,
            {"key": "value", "number": 42},
            id=f"test-json-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["key"] == "value"
        assert result["number"] == 42
        assert result["processed"] is True


@pytest.mark.asyncio
async def test_data_processing_empty():
    """Test data processing with empty list."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DataProcessingWorkflow],
        activities=[data_processing_activity],
    ):
        result = await client.execute_workflow(
            DataProcessingWorkflow.run,
            [],
            id=f"test-empty-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == []


@pytest.mark.asyncio
async def test_aggregation_single():
    """Test aggregation with single value."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AggregationWorkflow],
        activities=[aggregation_activity],
    ):
        result = await client.execute_workflow(
            AggregationWorkflow.run,
            [42],
            id=f"test-single-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["sum"] == 42
        assert result["count"] == 1
        assert result["avg"] == 42.0


@pytest.mark.asyncio
async def test_aggregation_zeros():
    """Test aggregation with zeros."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AggregationWorkflow],
        activities=[aggregation_activity],
    ):
        result = await client.execute_workflow(
            AggregationWorkflow.run,
            [0, 0, 0],
            id=f"test-zeros-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["sum"] == 0
        assert result["count"] == 3
        assert result["avg"] == 0.0


@pytest.mark.asyncio
async def test_aggregation_negatives():
    """Test aggregation with negative numbers."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AggregationWorkflow],
        activities=[aggregation_activity],
    ):
        result = await client.execute_workflow(
            AggregationWorkflow.run,
            [-1, -2, -3],
            id=f"test-neg-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["sum"] == -6
        assert result["count"] == 3
        assert result["avg"] == -2.0


@pytest.mark.asyncio
async def test_data_processing_mixed():
    """Test data processing with mixed types."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DataProcessingWorkflow],
        activities=[data_processing_activity],
    ):
        result = await client.execute_workflow(
            DataProcessingWorkflow.run,
            ["hello", 123, "world"],
            id=f"test-mixed-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == ["HELLO", 123, "WORLD"]


@pytest.mark.asyncio
async def test_data_processing_unicode():
    """Test data processing with unicode."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DataProcessingWorkflow],
        activities=[data_processing_activity],
    ):
        result = await client.execute_workflow(
            DataProcessingWorkflow.run,
            ["hello", "世界"],
            id=f"test-unicode-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == ["HELLO", "世界"]


@pytest.mark.asyncio
async def test_json_empty():
    """Test JSON processing with empty dict."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[JsonWorkflow],
        activities=[json_activity],
    ):
        result = await client.execute_workflow(
            JsonWorkflow.run,
            {},
            id=f"test-json-empty-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["processed"] is True


@pytest.mark.asyncio
async def test_json_nested():
    """Test JSON processing with nested structure."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[JsonWorkflow],
        activities=[json_activity],
    ):
        result = await client.execute_workflow(
            JsonWorkflow.run,
            {"nested": {"key": "value"}},
            id=f"test-json-nested-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["nested"]["key"] == "value"
        assert result["processed"] is True


@pytest.mark.asyncio
async def test_multi_return_empty():
    """Test multi return with empty string."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MultiReturnWorkflow],
        activities=[multi_return_activity],
    ):
        result = await client.execute_workflow(
            MultiReturnWorkflow.run,
            "",
            id=f"test-multi-empty-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["original"] == ""
        assert result["length"] == 0


@pytest.mark.asyncio
async def test_aggregation_large():
    """Test aggregation with large numbers."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AggregationWorkflow],
        activities=[aggregation_activity],
    ):
        numbers = list(range(1, 101))  # 1 to 100
        result = await client.execute_workflow(
            AggregationWorkflow.run,
            numbers,
            id=f"test-large-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["sum"] == 5050
        assert result["count"] == 100
        assert result["avg"] == 50.5


@pytest.mark.asyncio
async def test_conditional_negative():
    """Test conditional with negative threshold."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ConditionalWorkflow],
        activities=[conditional_activity],
    ):
        result = await client.execute_workflow(
            ConditionalWorkflow.run,
            args=[0, -5],
            id=f"test-cond-neg-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result is True
