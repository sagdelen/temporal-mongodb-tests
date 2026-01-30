"""Signal and Query tests."""

import os
import uuid
import asyncio
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-signal-query-queue"


@workflow.defn
class SignalWorkflow:
    def __init__(self):
        self._messages: list[str] = []
        self._done = False

    @workflow.run
    async def run(self) -> list[str]:
        await workflow.wait_condition(lambda: self._done)
        return self._messages

    @workflow.signal
    async def add_message(self, message: str) -> None:
        self._messages.append(message)

    @workflow.signal
    async def complete(self) -> None:
        self._done = True

    @workflow.query
    def get_messages(self) -> list[str]:
        return self._messages

    @workflow.query
    def get_count(self) -> int:
        return len(self._messages)


@pytest.mark.asyncio
async def test_workflow_signal_single():
    """Test sending a single signal to workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[SignalWorkflow]):
        workflow_id = f"test-signal-single-{uuid.uuid4()}"
        handle = await client.start_workflow(
            SignalWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await handle.signal(SignalWorkflow.add_message, "hello")
        await handle.signal(SignalWorkflow.complete)

        result = await handle.result()
        assert result == ["hello"]


@pytest.mark.asyncio
async def test_workflow_signal_multiple():
    """Test sending multiple signals to workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[SignalWorkflow]):
        workflow_id = f"test-signal-multi-{uuid.uuid4()}"
        handle = await client.start_workflow(
            SignalWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        for i in range(5):
            await handle.signal(SignalWorkflow.add_message, f"msg-{i}")

        await handle.signal(SignalWorkflow.complete)
        result = await handle.result()
        assert result == ["msg-0", "msg-1", "msg-2", "msg-3", "msg-4"]


@pytest.mark.asyncio
async def test_workflow_query():
    """Test querying workflow state."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[SignalWorkflow]):
        workflow_id = f"test-query-{uuid.uuid4()}"
        handle = await client.start_workflow(
            SignalWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        # Query before any signals
        count = await handle.query(SignalWorkflow.get_count)
        assert count == 0

        # Add messages and query
        await handle.signal(SignalWorkflow.add_message, "first")
        await handle.signal(SignalWorkflow.add_message, "second")

        messages = await handle.query(SignalWorkflow.get_messages)
        assert messages == ["first", "second"]

        count = await handle.query(SignalWorkflow.get_count)
        assert count == 2

        await handle.signal(SignalWorkflow.complete)
        await handle.result()


@pytest.mark.asyncio
async def test_workflow_query_after_complete():
    """Test querying completed workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[SignalWorkflow]):
        workflow_id = f"test-query-complete-{uuid.uuid4()}"
        handle = await client.start_workflow(
            SignalWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await handle.signal(SignalWorkflow.add_message, "final")
        await handle.signal(SignalWorkflow.complete)
        await handle.result()

        # Query after completion
        messages = await handle.query(SignalWorkflow.get_messages)
        assert messages == ["final"]


@pytest.mark.asyncio
async def test_signal_with_start():
    """Test signal-with-start functionality."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[SignalWorkflow]):
        workflow_id = f"test-signal-start-{uuid.uuid4()}"

        # Start workflow with signal
        handle = await client.start_workflow(
            SignalWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
            start_signal="add_message",
            start_signal_args=["started-with-signal"],
        )

        messages = await handle.query(SignalWorkflow.get_messages)
        assert "started-with-signal" in messages

        await handle.signal(SignalWorkflow.complete)
        await handle.result()
