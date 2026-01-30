"""Workflow metadata tests - testing workflow.info() and metadata."""

import os
import uuid
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow


TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-metadata"


@workflow.defn
class MetadataWorkflow:
    @workflow.run
    async def run(self) -> dict:
        info = workflow.info()
        return {
            "workflow_id": info.workflow_id,
            "run_id": info.run_id,
            "task_queue": info.task_queue,
            "namespace": info.namespace,
            "workflow_type": info.workflow_type,
            "attempt": info.attempt,
        }


@workflow.defn
class WorkflowIDWorkflow:
    @workflow.run
    async def run(self) -> str:
        return workflow.info().workflow_id


@workflow.defn
class RunIDWorkflow:
    @workflow.run
    async def run(self) -> str:
        return workflow.info().run_id


@workflow.defn
class TaskQueueWorkflow:
    @workflow.run
    async def run(self) -> str:
        return workflow.info().task_queue


@workflow.defn
class NamespaceWorkflow:
    @workflow.run
    async def run(self) -> str:
        return workflow.info().namespace


@workflow.defn
class WorkflowTypeWorkflow:
    @workflow.run
    async def run(self) -> str:
        return workflow.info().workflow_type


@workflow.defn
class AttemptWorkflow:
    @workflow.run
    async def run(self) -> int:
        return workflow.info().attempt


@pytest.mark.asyncio
async def test_workflow_metadata():
    """Test accessing workflow metadata."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MetadataWorkflow],
    ):
        workflow_id = f"test-metadata-{uuid.uuid4()}"
        result = await client.execute_workflow(
            MetadataWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        assert result["workflow_id"] == workflow_id
        assert result["task_queue"] == TASK_QUEUE
        assert result["namespace"] == TEST_NAMESPACE
        assert "run_id" in result
        assert result["attempt"] == 1


@pytest.mark.asyncio
async def test_workflow_id():
    """Test workflow ID access."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[WorkflowIDWorkflow],
    ):
        workflow_id = f"test-id-{uuid.uuid4()}"
        result = await client.execute_workflow(
            WorkflowIDWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == workflow_id


@pytest.mark.asyncio
async def test_run_id():
    """Test run ID is present."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RunIDWorkflow],
    ):
        workflow_id = f"test-runid-{uuid.uuid4()}"
        result = await client.execute_workflow(
            RunIDWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result is not None
        assert len(result) > 0


@pytest.mark.asyncio
async def test_task_queue_name():
    """Test task queue name access."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[TaskQueueWorkflow],
    ):
        workflow_id = f"test-tq-{uuid.uuid4()}"
        result = await client.execute_workflow(
            TaskQueueWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == TASK_QUEUE


@pytest.mark.asyncio
async def test_namespace_name():
    """Test namespace access."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[NamespaceWorkflow],
    ):
        workflow_id = f"test-ns-{uuid.uuid4()}"
        result = await client.execute_workflow(
            NamespaceWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == TEST_NAMESPACE


@pytest.mark.asyncio
async def test_workflow_type_name():
    """Test workflow type name."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[WorkflowTypeWorkflow],
    ):
        workflow_id = f"test-type-{uuid.uuid4()}"
        result = await client.execute_workflow(
            WorkflowTypeWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert "WorkflowTypeWorkflow" in result


@pytest.mark.asyncio
async def test_workflow_attempt():
    """Test workflow attempt number."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AttemptWorkflow],
    ):
        workflow_id = f"test-attempt-{uuid.uuid4()}"
        result = await client.execute_workflow(
            AttemptWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == 1


@pytest.mark.asyncio
async def test_metadata_custom_task_queue():
    """Test metadata with custom task queue."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    custom_queue = f"custom-{uuid.uuid4()}"
    async with Worker(
        client,
        task_queue=custom_queue,
        workflows=[TaskQueueWorkflow],
    ):
        workflow_id = f"test-custom-tq-{uuid.uuid4()}"
        result = await client.execute_workflow(
            TaskQueueWorkflow.run,
            id=workflow_id,
            task_queue=custom_queue,
        )
        assert result == custom_queue


@pytest.mark.asyncio
async def test_metadata_long_workflow_id():
    """Test metadata with long workflow ID."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[WorkflowIDWorkflow],
    ):
        workflow_id = "test-long-" + "x" * 100
        result = await client.execute_workflow(
            WorkflowIDWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == workflow_id


@pytest.mark.asyncio
async def test_metadata_unicode_workflow_id():
    """Test metadata with unicode workflow ID."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[WorkflowIDWorkflow],
    ):
        workflow_id = f"test-unicode-测试-{uuid.uuid4()}"
        result = await client.execute_workflow(
            WorkflowIDWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == workflow_id


@pytest.mark.asyncio
async def test_metadata_special_chars_workflow_id():
    """Test metadata with special characters in workflow ID."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[WorkflowIDWorkflow],
    ):
        workflow_id = f"test-special-!@#-{uuid.uuid4()}"
        result = await client.execute_workflow(
            WorkflowIDWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == workflow_id


@pytest.mark.asyncio
async def test_run_id_uniqueness():
    """Test run IDs are unique across executions."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RunIDWorkflow],
    ):
        run_id1 = await client.execute_workflow(
            RunIDWorkflow.run,
            id=f"test-unique-1-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        run_id2 = await client.execute_workflow(
            RunIDWorkflow.run,
            id=f"test-unique-2-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        assert run_id1 != run_id2


@pytest.mark.asyncio
async def test_metadata_persistence():
    """Test metadata is consistent throughout workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MetadataWorkflow],
    ):
        workflow_id = f"test-persist-{uuid.uuid4()}"
        result1 = await client.execute_workflow(
            MetadataWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        assert result1["workflow_id"] == workflow_id
        assert result1["namespace"] == TEST_NAMESPACE


@pytest.mark.asyncio
async def test_workflow_type_matches_class():
    """Test workflow type matches class name."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MetadataWorkflow],
    ):
        workflow_id = f"test-type-match-{uuid.uuid4()}"
        result = await client.execute_workflow(
            MetadataWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        assert "MetadataWorkflow" in result["workflow_type"]
