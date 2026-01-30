"""Signal edge cases and advanced scenarios tests."""

import os
import uuid
import pytest
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow


TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-signal-advanced-queue"


@workflow.defn
class BufferedSignalWorkflow:
    def __init__(self):
        self._signals: list[str] = []
        self._process = False

    @workflow.run
    async def run(self) -> list[str]:
        await workflow.wait_condition(lambda: self._process)
        return sorted(self._signals)

    @workflow.signal
    async def add_signal(self, value: str):
        self._signals.append(value)

    @workflow.signal
    async def process(self):
        self._process = True


@workflow.defn
class SignalCounterWorkflow:
    def __init__(self):
        self._count = 0
        self._done = False

    @workflow.run
    async def run(self) -> int:
        await workflow.wait_condition(lambda: self._done)
        return self._count

    @workflow.signal
    async def increment(self):
        self._count += 1

    @workflow.signal
    async def complete(self):
        self._done = True

    @workflow.query
    def get_count(self) -> int:
        return self._count


@workflow.defn
class SignalWithDataWorkflow:
    def __init__(self):
        self._data: dict = {}
        self._done = False

    @workflow.run
    async def run(self) -> dict:
        await workflow.wait_condition(lambda: self._done)
        return self._data

    @workflow.signal
    async def set_data(self, entry: dict):
        self._data[entry["key"]] = entry["value"]

    @workflow.signal
    async def complete(self):
        self._done = True


@workflow.defn
class SignalOrderWorkflow:
    def __init__(self):
        self._order: list[int] = []
        self._expected = 0

    @workflow.run
    async def run(self, count: int) -> list[int]:
        self._expected = count
        await workflow.wait_condition(lambda: len(self._order) >= self._expected)
        return self._order

    @workflow.signal
    async def add_number(self, num: int):
        self._order.append(num)


@pytest.mark.asyncio
async def test_buffered_signals():
    """Test multiple signals are buffered and processed."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client, task_queue=TASK_QUEUE, workflows=[BufferedSignalWorkflow]
    ):
        workflow_id = f"test-buffered-{uuid.uuid4()}"
        handle = await client.start_workflow(
            BufferedSignalWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await handle.signal(BufferedSignalWorkflow.add_signal, "c")
        await handle.signal(BufferedSignalWorkflow.add_signal, "a")
        await handle.signal(BufferedSignalWorkflow.add_signal, "b")
        await handle.signal(BufferedSignalWorkflow.process)

        result = await handle.result()
        assert result == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_rapid_signal_counting():
    """Test rapid signal counting."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[SignalCounterWorkflow]):
        workflow_id = f"test-rapid-{uuid.uuid4()}"
        handle = await client.start_workflow(
            SignalCounterWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        for _ in range(10):
            await handle.signal(SignalCounterWorkflow.increment)

        count = await handle.query(SignalCounterWorkflow.get_count)
        assert count == 10

        await handle.signal(SignalCounterWorkflow.complete)
        result = await handle.result()
        assert result == 10


@pytest.mark.asyncio
async def test_signal_with_dict_arg():
    """Test signals with dict argument."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client, task_queue=TASK_QUEUE, workflows=[SignalWithDataWorkflow]
    ):
        workflow_id = f"test-dictarg-{uuid.uuid4()}"
        handle = await client.start_workflow(
            SignalWithDataWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await handle.signal(
            SignalWithDataWorkflow.set_data, {"key": "key1", "value": "value1"}
        )
        await handle.signal(
            SignalWithDataWorkflow.set_data, {"key": "key2", "value": "value2"}
        )
        await handle.signal(SignalWithDataWorkflow.complete)

        result = await handle.result()
        assert result == {"key1": "value1", "key2": "value2"}


@pytest.mark.asyncio
async def test_signal_order_preserved():
    """Test signal order is preserved."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[SignalOrderWorkflow]):
        workflow_id = f"test-order-{uuid.uuid4()}"
        handle = await client.start_workflow(
            SignalOrderWorkflow.run,
            5,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        for i in range(5):
            await handle.signal(SignalOrderWorkflow.add_number, i)

        result = await handle.result()
        assert result == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_signal_before_workflow_starts():
    """Test signal sent immediately after start."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[SignalCounterWorkflow]):
        workflow_id = f"test-prestart-{uuid.uuid4()}"
        handle = await client.start_workflow(
            SignalCounterWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await handle.signal(SignalCounterWorkflow.increment)
        await handle.signal(SignalCounterWorkflow.complete)
        result = await handle.result()
        assert result == 1
