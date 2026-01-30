"""Activity features and info tests."""

import os
import uuid
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity


TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-activity-features-queue"


@activity.defn
async def async_activity(value: str) -> str:
    return f"async-{value}"


@activity.defn
async def get_activity_info() -> dict:
    info = activity.info()
    return {
        "activity_id": info.activity_id,
        "activity_type": info.activity_type,
        "task_queue": info.task_queue,
        "workflow_id": info.workflow_id,
        "attempt": info.attempt,
    }


@workflow.defn
class AsyncActivityWorkflow:
    @workflow.run
    async def run(self, value: str) -> str:
        result = await workflow.execute_activity(
            async_activity,
            value,
            start_to_close_timeout=timedelta(seconds=30),
        )
        return result


@workflow.defn
class ActivityInfoWorkflow:
    @workflow.run
    async def run(self) -> dict:
        result = await workflow.execute_activity(
            get_activity_info,
            start_to_close_timeout=timedelta(seconds=30),
        )
        return result


@workflow.defn
class MultipleActivitiesWorkflow:
    @workflow.run
    async def run(self, value: str) -> list:
        result1 = await workflow.execute_activity(
            async_activity,
            value + "-1",
            start_to_close_timeout=timedelta(seconds=30),
        )
        result2 = await workflow.execute_activity(
            async_activity,
            value + "-2",
            start_to_close_timeout=timedelta(seconds=30),
        )
        return [result1, result2]


@pytest.mark.asyncio
async def test_async_activity():
    """Test asynchronous activity execution."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AsyncActivityWorkflow],
        activities=[async_activity],
    ):
        workflow_id = f"test-async-act-{uuid.uuid4()}"
        result = await client.execute_workflow(
            AsyncActivityWorkflow.run,
            "world",
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == "async-world"


@pytest.mark.asyncio
async def test_activity_info():
    """Test activity has access to its info."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ActivityInfoWorkflow],
        activities=[get_activity_info],
    ):
        workflow_id = f"test-act-info-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ActivityInfoWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result["workflow_id"] == workflow_id
        assert result["task_queue"] == TASK_QUEUE
        assert result["attempt"] >= 1
        assert result["activity_type"] == "get_activity_info"


@pytest.mark.asyncio
async def test_multiple_activities_sequential():
    """Test multiple activities executed sequentially."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MultipleActivitiesWorkflow],
        activities=[async_activity],
    ):
        workflow_id = f"test-multi-act-{uuid.uuid4()}"
        result = await client.execute_workflow(
            MultipleActivitiesWorkflow.run,
            "test",
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == ["async-test-1", "async-test-2"]
