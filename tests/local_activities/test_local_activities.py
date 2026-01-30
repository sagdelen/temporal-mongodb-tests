"""Local activity tests - activities that execute in same process as workflow."""

import os
import uuid
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity


TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-local-activity"


@activity.defn
async def local_cache_lookup(key: str) -> str:
    """Simulates fast local cache lookup."""
    return f"cached-{key}"


@activity.defn
async def local_validation(data: dict) -> bool:
    """Fast local validation."""
    return "value" in data and data["value"] > 0


@activity.defn
async def local_transform(text: str) -> str:
    """Quick data transformation."""
    return text.upper()


@activity.defn
async def local_counter() -> int:
    """Simple counter."""
    return 1


@workflow.defn
class LocalActivityWorkflow:
    @workflow.run
    async def run(self, key: str) -> str:
        result = await workflow.execute_local_activity(
            local_cache_lookup,
            key,
            start_to_close_timeout=timedelta(seconds=5),
        )
        return result


@workflow.defn
class LocalValidationWorkflow:
    @workflow.run
    async def run(self, data: dict) -> bool:
        valid = await workflow.execute_local_activity(
            local_validation,
            data,
            start_to_close_timeout=timedelta(seconds=5),
        )
        return valid


@workflow.defn
class LocalTransformWorkflow:
    @workflow.run
    async def run(self, texts: list) -> list:
        results = []
        for text in texts:
            result = await workflow.execute_local_activity(
                local_transform,
                text,
                start_to_close_timeout=timedelta(seconds=5),
            )
            results.append(result)
        return results


@workflow.defn
class LocalCounterWorkflow:
    @workflow.run
    async def run(self, count: int) -> int:
        total = 0
        for _ in range(count):
            result = await workflow.execute_local_activity(
                local_counter,
                start_to_close_timeout=timedelta(seconds=5),
            )
            total += result
        return total


@workflow.defn
class MixedActivityWorkflow:
    @workflow.run
    async def run(self, key: str) -> dict:
        # Local activity - fast
        local_result = await workflow.execute_local_activity(
            local_cache_lookup,
            key,
            start_to_close_timeout=timedelta(seconds=5),
        )

        # Regular activity - can be slower
        transform_result = await workflow.execute_activity(
            local_transform,
            local_result,
            start_to_close_timeout=timedelta(seconds=30),
        )

        return {
            "local": local_result,
            "activity": transform_result,
        }


@pytest.mark.asyncio
async def test_local_activity_execution():
    """Test basic local activity execution."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[LocalActivityWorkflow],
        activities=[local_cache_lookup],
    ):
        workflow_id = f"test-local-{uuid.uuid4()}"
        result = await client.execute_workflow(
            LocalActivityWorkflow.run,
            "test-key",
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == "cached-test-key"


@pytest.mark.asyncio
async def test_local_activity_validation():
    """Test local activity for validation."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[LocalValidationWorkflow],
        activities=[local_validation],
    ):
        workflow_id = f"test-validation-{uuid.uuid4()}"
        result = await client.execute_workflow(
            LocalValidationWorkflow.run,
            {"value": 10},
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result is True


@pytest.mark.asyncio
async def test_local_activity_invalid_data():
    """Test local activity with invalid data."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[LocalValidationWorkflow],
        activities=[local_validation],
    ):
        workflow_id = f"test-invalid-{uuid.uuid4()}"
        result = await client.execute_workflow(
            LocalValidationWorkflow.run,
            {"other": 10},
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result is False


@pytest.mark.asyncio
async def test_local_activity_multiple_calls():
    """Test multiple local activity calls in sequence."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[LocalTransformWorkflow],
        activities=[local_transform],
    ):
        workflow_id = f"test-multiple-{uuid.uuid4()}"
        result = await client.execute_workflow(
            LocalTransformWorkflow.run,
            ["hello", "world", "test"],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == ["HELLO", "WORLD", "TEST"]


@pytest.mark.asyncio
async def test_local_activity_loop():
    """Test local activity in loop."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[LocalCounterWorkflow],
        activities=[local_counter],
    ):
        workflow_id = f"test-loop-{uuid.uuid4()}"
        result = await client.execute_workflow(
            LocalCounterWorkflow.run,
            10,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == 10


@pytest.mark.asyncio
async def test_local_activity_empty_list():
    """Test local activity with empty input."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[LocalTransformWorkflow],
        activities=[local_transform],
    ):
        workflow_id = f"test-empty-{uuid.uuid4()}"
        result = await client.execute_workflow(
            LocalTransformWorkflow.run,
            [],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == []


@pytest.mark.asyncio
async def test_local_activity_zero_count():
    """Test local activity with zero iterations."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[LocalCounterWorkflow],
        activities=[local_counter],
    ):
        workflow_id = f"test-zero-{uuid.uuid4()}"
        result = await client.execute_workflow(
            LocalCounterWorkflow.run,
            0,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == 0


@pytest.mark.asyncio
async def test_mixed_local_and_regular_activities():
    """Test workflow with both local and regular activities."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MixedActivityWorkflow],
        activities=[local_cache_lookup, local_transform],
    ):
        workflow_id = f"test-mixed-{uuid.uuid4()}"
        result = await client.execute_workflow(
            MixedActivityWorkflow.run,
            "test",
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result["local"] == "cached-test"
        assert result["activity"] == "CACHED-TEST"


@pytest.mark.asyncio
async def test_local_activity_large_batch():
    """Test local activity with large batch."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[LocalCounterWorkflow],
        activities=[local_counter],
    ):
        workflow_id = f"test-batch-{uuid.uuid4()}"
        result = await client.execute_workflow(
            LocalCounterWorkflow.run,
            50,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == 50


@pytest.mark.asyncio
async def test_local_activity_special_chars():
    """Test local activity with special characters."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[LocalActivityWorkflow],
        activities=[local_cache_lookup],
    ):
        workflow_id = f"test-special-{uuid.uuid4()}"
        result = await client.execute_workflow(
            LocalActivityWorkflow.run,
            "key-with-特殊字符",
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == "cached-key-with-特殊字符"


@pytest.mark.asyncio
async def test_local_activity_unicode():
    """Test local activity with unicode strings."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[LocalTransformWorkflow],
        activities=[local_transform],
    ):
        workflow_id = f"test-unicode-{uuid.uuid4()}"
        result = await client.execute_workflow(
            LocalTransformWorkflow.run,
            ["héllo", "wörld", "测试"],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == ["HÉLLO", "WÖRLD", "测试"]


@pytest.mark.asyncio
async def test_local_activity_long_string():
    """Test local activity with long string."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[LocalActivityWorkflow],
        activities=[local_cache_lookup],
    ):
        long_key = "x" * 1000
        workflow_id = f"test-long-{uuid.uuid4()}"
        result = await client.execute_workflow(
            LocalActivityWorkflow.run,
            long_key,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == f"cached-{long_key}"


@pytest.mark.asyncio
async def test_local_activity_negative_validation():
    """Test local activity validation with negative value."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[LocalValidationWorkflow],
        activities=[local_validation],
    ):
        workflow_id = f"test-negative-{uuid.uuid4()}"
        result = await client.execute_workflow(
            LocalValidationWorkflow.run,
            {"value": -5},
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result is False


@pytest.mark.asyncio
async def test_local_activity_zero_validation():
    """Test local activity validation with zero value."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[LocalValidationWorkflow],
        activities=[local_validation],
    ):
        workflow_id = f"test-zero-val-{uuid.uuid4()}"
        result = await client.execute_workflow(
            LocalValidationWorkflow.run,
            {"value": 0},
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result is False


@pytest.mark.asyncio
async def test_local_activity_single_transform():
    """Test local activity with single item."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[LocalTransformWorkflow],
        activities=[local_transform],
    ):
        workflow_id = f"test-single-{uuid.uuid4()}"
        result = await client.execute_workflow(
            LocalTransformWorkflow.run,
            ["single"],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == ["SINGLE"]
