"""Task queue operations tests."""

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
TASK_QUEUE_1 = "e2e-taskqueue-1"
TASK_QUEUE_2 = "e2e-taskqueue-2"


@activity.defn
async def queue_activity() -> str:
    return "activity-done"


@workflow.defn
class TaskQueueWorkflow:
    @workflow.run
    async def run(self) -> dict:
        info = workflow.info()
        return {
            "task_queue": info.task_queue,
            "workflow_id": info.workflow_id,
        }


@workflow.defn
class ActivityQueueWorkflow:
    @workflow.run
    async def run(self, target_queue: str) -> str:
        result = await workflow.execute_activity(
            queue_activity,
            task_queue=target_queue,
            start_to_close_timeout=timedelta(seconds=30),
        )
        return result


@pytest.mark.asyncio
async def test_multiple_task_queues():
    """Test workflows on different task queues."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE_1, workflows=[TaskQueueWorkflow]):
        async with Worker(
            client, task_queue=TASK_QUEUE_2, workflows=[TaskQueueWorkflow]
        ):
            wf1_id = f"test-queue1-{uuid.uuid4()}"
            result1 = await client.execute_workflow(
                TaskQueueWorkflow.run,
                id=wf1_id,
                task_queue=TASK_QUEUE_1,
            )
            assert result1["task_queue"] == TASK_QUEUE_1

            wf2_id = f"test-queue2-{uuid.uuid4()}"
            result2 = await client.execute_workflow(
                TaskQueueWorkflow.run,
                id=wf2_id,
                task_queue=TASK_QUEUE_2,
            )
            assert result2["task_queue"] == TASK_QUEUE_2


@pytest.mark.asyncio
async def test_activity_task_queue_routing():
    """Test activity execution on specific task queue."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE_1,
        workflows=[ActivityQueueWorkflow],
        activities=[queue_activity],
    ):
        workflow_id = f"test-act-queue-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ActivityQueueWorkflow.run,
            TASK_QUEUE_1,
            id=workflow_id,
            task_queue=TASK_QUEUE_1,
        )
        assert result == "activity-done"


@pytest.mark.asyncio
async def test_task_queue_isolation():
    """Test task queue isolation."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE_1, workflows=[TaskQueueWorkflow]):
        workflow_id = f"test-isolation-{uuid.uuid4()}"
        result = await client.execute_workflow(
            TaskQueueWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE_1,
        )
        assert result["task_queue"] == TASK_QUEUE_1


@pytest.mark.asyncio
async def test_workflow_task_queue_info():
    """Test workflow has correct task queue info."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE_1, workflows=[TaskQueueWorkflow]):
        workflow_id = f"test-queue-info-{uuid.uuid4()}"
        result = await client.execute_workflow(
            TaskQueueWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE_1,
        )
        assert result["task_queue"] == TASK_QUEUE_1
        assert result["workflow_id"] == workflow_id


@pytest.mark.asyncio

@pytest.mark.asyncio
async def test_task_queue_name_validation():
    """Test task queue name is preserved."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    queue_name = f"custom-queue-{uuid.uuid4()}"
    async with Worker(client, task_queue=queue_name, workflows=[TaskQueueWorkflow]):
        workflow_id = f"test-name-{uuid.uuid4()}"
        result = await client.execute_workflow(
            TaskQueueWorkflow.run,
            id=workflow_id,
            task_queue=queue_name,
        )
        assert result["task_queue"] == queue_name
