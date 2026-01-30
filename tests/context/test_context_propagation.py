"""Workflow context propagation tests."""

import os
import uuid
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity


TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-context"


@activity.defn
async def context_activity() -> dict:
    """Activity that accesses context."""
    info = activity.info()
    return {
        "activity_id": info.activity_id,
        "activity_type": info.activity_type,
        "attempt": info.attempt,
    }


@activity.defn
async def nested_activity(value: str) -> str:
    """Nested activity."""
    return f"nested-{value}"


@workflow.defn
class ContextWorkflow:
    @workflow.run
    async def run(self) -> dict:
        wf_info = workflow.info()

        act_result = await workflow.execute_activity(
            context_activity,
            start_to_close_timeout=timedelta(seconds=30),
        )

        return {
            "workflow_id": wf_info.workflow_id,
            "workflow_type": wf_info.workflow_type,
            "activity_info": act_result,
        }


@workflow.defn
class NestedContextWorkflow:
    @workflow.run
    async def run(self, value: str) -> dict:
        wf_info = workflow.info()

        result1 = await workflow.execute_activity(
            nested_activity,
            value,
            start_to_close_timeout=timedelta(seconds=30),
        )

        result2 = await workflow.execute_activity(
            nested_activity,
            result1,
            start_to_close_timeout=timedelta(seconds=30),
        )

        return {
            "workflow_id": wf_info.workflow_id,
            "result1": result1,
            "result2": result2,
        }


@workflow.defn
class SimpleContextWorkflow:
    @workflow.run
    async def run(self) -> str:
        return workflow.info().workflow_id


@pytest.mark.asyncio
async def test_context_propagation():
    """Test context propagation to activities."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ContextWorkflow],
        activities=[context_activity],
    ):
        workflow_id = f"test-context-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ContextWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        assert result["workflow_id"] == workflow_id
        assert "ContextWorkflow" in result["workflow_type"]
        assert "activity_id" in result["activity_info"]


@pytest.mark.asyncio
async def test_nested_context():
    """Test nested activity context."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[NestedContextWorkflow],
        activities=[nested_activity],
    ):
        workflow_id = f"test-nested-{uuid.uuid4()}"
        result = await client.execute_workflow(
            NestedContextWorkflow.run,
            "test",
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        assert result["workflow_id"] == workflow_id
        assert result["result1"] == "nested-test"
        assert result["result2"] == "nested-nested-test"


@pytest.mark.asyncio
async def test_simple_context():
    """Test simple context access."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SimpleContextWorkflow],
    ):
        workflow_id = f"test-simple-{uuid.uuid4()}"
        result = await client.execute_workflow(
            SimpleContextWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == workflow_id


@pytest.mark.asyncio
async def test_context_multiple_workflows():
    """Test context across multiple workflows."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SimpleContextWorkflow],
    ):
        wf1_id = f"test-multi-1-{uuid.uuid4()}"
        result1 = await client.execute_workflow(
            SimpleContextWorkflow.run,
            id=wf1_id,
            task_queue=TASK_QUEUE,
        )

        wf2_id = f"test-multi-2-{uuid.uuid4()}"
        result2 = await client.execute_workflow(
            SimpleContextWorkflow.run,
            id=wf2_id,
            task_queue=TASK_QUEUE,
        )

        assert result1 == wf1_id
        assert result2 == wf2_id
        assert result1 != result2


@pytest.mark.asyncio
async def test_context_activity_attempt():
    """Test activity attempt in context."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ContextWorkflow],
        activities=[context_activity],
    ):
        workflow_id = f"test-attempt-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ContextWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        assert result["activity_info"]["attempt"] == 1


@pytest.mark.asyncio
async def test_nested_empty_value():
    """Test nested context with empty value."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[NestedContextWorkflow],
        activities=[nested_activity],
    ):
        workflow_id = f"test-empty-{uuid.uuid4()}"
        result = await client.execute_workflow(
            NestedContextWorkflow.run,
            "",
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        assert result["result1"] == "nested-"
        assert result["result2"] == "nested-nested-"


@pytest.mark.asyncio
async def test_nested_unicode_value():
    """Test nested context with unicode."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[NestedContextWorkflow],
        activities=[nested_activity],
    ):
        workflow_id = f"test-unicode-{uuid.uuid4()}"
        result = await client.execute_workflow(
            NestedContextWorkflow.run,
            "测试",
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        assert result["result1"] == "nested-测试"
        assert "nested-nested-" in result["result2"]


@pytest.mark.asyncio
async def test_context_long_workflow_id():
    """Test context with long workflow ID."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SimpleContextWorkflow],
    ):
        workflow_id = "test-long-" + "x" * 100
        result = await client.execute_workflow(
            SimpleContextWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == workflow_id


@pytest.mark.asyncio
async def test_context_special_chars():
    """Test context with special characters in ID."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SimpleContextWorkflow],
    ):
        workflow_id = f"test-special-!@#-{uuid.uuid4()}"
        result = await client.execute_workflow(
            SimpleContextWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == workflow_id


@pytest.mark.asyncio
async def test_nested_long_value():
    """Test nested context with long value."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[NestedContextWorkflow],
        activities=[nested_activity],
    ):
        long_value = "x" * 100
        workflow_id = f"test-long-val-{uuid.uuid4()}"
        result = await client.execute_workflow(
            NestedContextWorkflow.run,
            long_value,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        assert result["result1"] == f"nested-{long_value}"
