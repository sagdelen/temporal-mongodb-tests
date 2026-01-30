"""Workflow memo and search attributes tests."""

import os
import uuid
import asyncio
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow
from temporalio.common import TypedSearchAttributes, SearchAttributeKey

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-memo-queue"


@workflow.defn
class MemoWorkflow:
    @workflow.run
    async def run(self) -> dict:
        return dict(workflow.memo())


@workflow.defn
class SearchAttrWorkflow:
    @workflow.run
    async def run(self) -> str:
        return "completed"


@pytest.mark.asyncio
async def test_workflow_with_memo():
    """Test workflow with memo data."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[MemoWorkflow]):
        workflow_id = f"test-memo-{uuid.uuid4()}"
        memo_data = {
            "user_id": "user-123",
            "request_id": "req-456",
            "priority": "high",
        }

        result = await client.execute_workflow(
            MemoWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
            memo=memo_data,
        )

        assert result["user_id"] == "user-123"
        assert result["request_id"] == "req-456"
        assert result["priority"] == "high"


@pytest.mark.asyncio
async def test_workflow_memo_in_describe():
    """Test that memo is visible in workflow description."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[MemoWorkflow]):
        workflow_id = f"test-memo-desc-{uuid.uuid4()}"
        memo_data = {"key": "value", "number": 42}

        handle = await client.start_workflow(
            MemoWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
            memo=memo_data,
        )

        desc = await handle.describe()
        assert desc.memo is not None

        await handle.result()


@pytest.mark.asyncio
async def test_workflow_empty_memo():
    """Test workflow without memo."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[MemoWorkflow]):
        workflow_id = f"test-memo-empty-{uuid.uuid4()}"

        result = await client.execute_workflow(
            MemoWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        assert result == {}


@pytest.mark.asyncio
async def test_workflow_complex_memo():
    """Test workflow with complex memo structure."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[MemoWorkflow]):
        workflow_id = f"test-memo-complex-{uuid.uuid4()}"
        memo_data = {
            "nested": {"level1": {"level2": "deep_value"}},
            "list": [1, 2, 3],
            "mixed": {"items": ["a", "b"], "count": 2},
        }

        result = await client.execute_workflow(
            MemoWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
            memo=memo_data,
        )

        assert result["nested"]["level1"]["level2"] == "deep_value"
        assert result["list"] == [1, 2, 3]
