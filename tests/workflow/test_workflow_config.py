"""Workflow execution configuration tests."""

import os
import uuid
import pytest
from datetime import timedelta
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.worker import Worker
from temporalio import workflow

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-workflow-config-queue"


@workflow.defn
class SimpleWorkflow:
    @workflow.run
    async def run(self, value: str) -> str:
        return f"result-{value}"


@workflow.defn
class WorkflowWithInfo:
    @workflow.run
    async def run(self) -> dict:
        info = workflow.info()
        return {
            "workflow_id": info.workflow_id,
            "run_id": info.run_id,
            "task_queue": info.task_queue,
            "namespace": info.namespace,
            "workflow_type": info.workflow_type,
        }


@workflow.defn
class LongRunningWorkflow:
    def __init__(self):
        self._done = False

    @workflow.run
    async def run(self) -> str:
        await workflow.wait_condition(lambda: self._done)
        return "completed"

    @workflow.signal
    async def complete(self):
        self._done = True


@pytest.mark.asyncio
async def test_workflow_with_run_id():
    """Test workflow run ID is generated."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[WorkflowWithInfo]):
        workflow_id = f"test-runid-{uuid.uuid4()}"
        result = await client.execute_workflow(
            WorkflowWithInfo.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result["workflow_id"] == workflow_id
        assert result["run_id"] is not None
        assert len(result["run_id"]) > 0


@pytest.mark.asyncio
async def test_workflow_info():
    """Test workflow info contains expected fields."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[WorkflowWithInfo]):
        workflow_id = f"test-info-{uuid.uuid4()}"
        result = await client.execute_workflow(
            WorkflowWithInfo.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result["task_queue"] == TASK_QUEUE
        assert result["namespace"] == TEST_NAMESPACE
        assert result["workflow_type"] == "WorkflowWithInfo"


@pytest.mark.asyncio
async def test_workflow_duplicate_id_reject():
    """Test starting workflow with existing ID is rejected."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[LongRunningWorkflow]):
        workflow_id = f"test-duplicate-{uuid.uuid4()}"

        handle1 = await client.start_workflow(
            LongRunningWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        with pytest.raises(Exception) as exc_info:
            await client.start_workflow(
                LongRunningWorkflow.run,
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )
        assert "already started" in str(exc_info.value).lower()

        await handle1.signal(LongRunningWorkflow.complete)
        await handle1.result()


@pytest.mark.asyncio
async def test_get_workflow_handle():
    """Test getting workflow handle by ID."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[SimpleWorkflow]):
        workflow_id = f"test-handle-{uuid.uuid4()}"
        await client.execute_workflow(
            SimpleWorkflow.run,
            "test",
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        handle = client.get_workflow_handle(workflow_id)
        desc = await handle.describe()
        assert desc.status == WorkflowExecutionStatus.COMPLETED


@pytest.mark.asyncio
async def test_workflow_execution_timeout_config():
    """Test workflow execution timeout configuration."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[SimpleWorkflow]):
        workflow_id = f"test-timeout-{uuid.uuid4()}"
        result = await client.execute_workflow(
            SimpleWorkflow.run,
            "test",
            id=workflow_id,
            task_queue=TASK_QUEUE,
            execution_timeout=timedelta(minutes=5),
        )
        assert result == "result-test"
