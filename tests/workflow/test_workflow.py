"""Workflow execution test."""

import os
import uuid
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-test-queue"


@activity.defn
async def greet(name: str) -> str:
    return f"Hello, {name}!"


@workflow.defn
class GreetingWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            greet,
            name,
            start_to_close_timeout=timedelta(seconds=10),
        )


@pytest.mark.asyncio
async def test_simple_workflow():
    """Test running a simple workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[GreetingWorkflow],
        activities=[greet],
    ):
        workflow_id = f"test-workflow-{uuid.uuid4()}"
        result = await client.execute_workflow(
            GreetingWorkflow.run,
            "World",
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == "Hello, World!"


@pytest.mark.asyncio
async def test_workflow_history():
    """Test that workflow history is persisted."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[GreetingWorkflow],
        activities=[greet],
    ):
        workflow_id = f"test-history-{uuid.uuid4()}"
        await client.execute_workflow(
            GreetingWorkflow.run,
            "Test",
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        # Verify history exists
        handle = client.get_workflow_handle(workflow_id)
        desc = await handle.describe()
        assert desc.status.name == "COMPLETED"
