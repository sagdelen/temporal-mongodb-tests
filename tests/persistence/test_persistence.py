"""Data persistence and durability tests."""

import os
import uuid
import pytest
from datetime import timedelta
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.worker import Worker
from temporalio import workflow, activity

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-persistence-queue"


@activity.defn
async def store_data_activity(data: dict) -> dict:
    return {"stored": True, **data}


@workflow.defn
class DataWorkflow:
    @workflow.run
    async def run(self, data: dict) -> dict:
        result = await workflow.execute_activity(
            store_data_activity,
            data,
            start_to_close_timeout=timedelta(seconds=30),
        )
        return result


@workflow.defn
class LargePayloadWorkflow:
    @workflow.run
    async def run(self, size: int) -> int:
        data = "x" * size
        return len(data)


@workflow.defn
class ComplexDataWorkflow:
    @workflow.run
    async def run(self, data: dict) -> dict:
        return {
            "input": data,
            "workflow_id": workflow.info().workflow_id,
            "processed": True,
        }


@workflow.defn
class WaitingWorkflow:
    def __init__(self):
        self._data = None
        self._done = False

    @workflow.run
    async def run(self) -> dict:
        await workflow.wait_condition(lambda: self._done)
        return self._data or {}

    @workflow.signal
    async def set_data(self, data: dict):
        self._data = data

    @workflow.signal
    async def complete(self):
        self._done = True

    @workflow.query
    def get_data(self) -> dict:
        return self._data or {}


@pytest.mark.asyncio
async def test_workflow_data_persistence():
    """Test workflow data is persisted."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DataWorkflow],
        activities=[store_data_activity],
    ):
        workflow_id = f"test-persist-{uuid.uuid4()}"
        test_data = {"key": "value", "number": 42}

        result = await client.execute_workflow(
            DataWorkflow.run,
            test_data,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        assert result["stored"] is True
        assert result["key"] == "value"
        assert result["number"] == 42


@pytest.mark.asyncio
async def test_workflow_history_persisted():
    """Test workflow history is persisted after completion."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DataWorkflow],
        activities=[store_data_activity],
    ):
        workflow_id = f"test-history-persist-{uuid.uuid4()}"
        await client.execute_workflow(
            DataWorkflow.run,
            {"test": "data"},
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        # Verify history is accessible after completion
        handle = client.get_workflow_handle(workflow_id)
        desc = await handle.describe()
        assert desc.status == WorkflowExecutionStatus.COMPLETED

        # Verify history events exist
        events = [e async for e in handle.fetch_history_events()]
        assert len(events) > 0


@pytest.mark.asyncio
async def test_large_payload():
    """Test large payloads are handled."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[LargePayloadWorkflow],
    ):
        workflow_id = f"test-large-{uuid.uuid4()}"
        size = 10000
        result = await client.execute_workflow(
            LargePayloadWorkflow.run,
            size,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == size


@pytest.mark.asyncio
async def test_complex_data_structures():
    """Test complex nested data structures."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ComplexDataWorkflow],
    ):
        workflow_id = f"test-complex-{uuid.uuid4()}"
        complex_data = {
            "string": "hello",
            "number": 123,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3],
            "nested": {"a": {"b": {"c": "deep"}}},
        }

        result = await client.execute_workflow(
            ComplexDataWorkflow.run,
            complex_data,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        assert result["input"] == complex_data
        assert result["processed"] is True


@pytest.mark.asyncio
async def test_signal_data_persistence():
    """Test signal data is persisted."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[WaitingWorkflow],
    ):
        workflow_id = f"test-signal-persist-{uuid.uuid4()}"
        handle = await client.start_workflow(
            WaitingWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        test_data = {"signal": "data", "value": 999}
        await handle.signal(WaitingWorkflow.set_data, test_data)

        # Query to verify data was received
        queried = await handle.query(WaitingWorkflow.get_data)
        assert queried == test_data

        await handle.signal(WaitingWorkflow.complete)
        result = await handle.result()
        assert result == test_data


@pytest.mark.asyncio
async def test_workflow_result_retrievable():
    """Test workflow result can be retrieved after completion."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ComplexDataWorkflow],
    ):
        workflow_id = f"test-result-retrieve-{uuid.uuid4()}"
        test_data = {"key": "value"}

        await client.execute_workflow(
            ComplexDataWorkflow.run,
            test_data,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        # Get handle and retrieve result again
        handle = client.get_workflow_handle(workflow_id)
        result = await handle.result()
        assert result["input"] == test_data


@pytest.mark.asyncio
async def test_multiple_workflows_data_isolation():
    """Test data isolation between workflows."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[WaitingWorkflow],
    ):
        # Start two workflows
        handle1 = await client.start_workflow(
            WaitingWorkflow.run,
            id=f"test-isolation-a-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        handle2 = await client.start_workflow(
            WaitingWorkflow.run,
            id=f"test-isolation-b-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        # Set different data
        await handle1.signal(WaitingWorkflow.set_data, {"workflow": "one"})
        await handle2.signal(WaitingWorkflow.set_data, {"workflow": "two"})

        # Verify isolation
        data1 = await handle1.query(WaitingWorkflow.get_data)
        data2 = await handle2.query(WaitingWorkflow.get_data)

        assert data1["workflow"] == "one"
        assert data2["workflow"] == "two"

        # Cleanup
        await handle1.signal(WaitingWorkflow.complete)
        await handle2.signal(WaitingWorkflow.complete)
        await handle1.result()
        await handle2.result()
