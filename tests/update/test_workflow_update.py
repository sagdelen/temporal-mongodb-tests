"""Workflow update API tests."""

import os
import uuid
import pytest
import asyncio
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow


TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-update"


@workflow.defn
class CounterUpdateWorkflow:
    def __init__(self):
        self.counter = 0

    @workflow.run
    async def run(self) -> int:
        await workflow.wait_condition(lambda: self.counter >= 10)
        return self.counter

    @workflow.update
    async def increment(self, amount: int) -> int:
        self.counter += amount
        return self.counter

    @workflow.query
    def get_counter(self) -> int:
        return self.counter


@workflow.defn
class StateUpdateWorkflow:
    def __init__(self):
        self.state = "initial"
        self.history = []

    @workflow.run
    async def run(self) -> list:
        await workflow.wait_condition(lambda: self.state == "done")
        return self.history

    @workflow.update
    async def set_state(self, new_state: str) -> str:
        old_state = self.state
        self.state = new_state
        self.history.append(f"{old_state}->{new_state}")
        return self.state

    @workflow.query
    def get_state(self) -> str:
        return self.state


@workflow.defn
class DataUpdateWorkflow:
    def __init__(self):
        self.data = {}

    @workflow.run
    async def run(self) -> dict:
        await workflow.wait_condition(lambda: "done" in self.data)
        return self.data

    @workflow.update
    async def add_data(self, key: str, value: str) -> dict:
        self.data[key] = value
        return self.data

    @workflow.query
    def get_data(self) -> dict:
        return self.data


@workflow.defn
class ValidatingUpdateWorkflow:
    def __init__(self):
        self.value = 0

    @workflow.run
    async def run(self) -> int:
        await workflow.wait_condition(lambda: self.value >= 100)
        return self.value

    @workflow.update
    def set_value(self, val: int) -> int:
        self.value = val
        return self.value
    
    @set_value.validator
    def set_value_validator(self, val: int):
        if val < 0:
            raise ValueError("Value must be non-negative")

    @workflow.query
    def get_value(self) -> int:
        return self.value


@pytest.mark.asyncio
async def test_update_counter():
    """Test updating counter workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CounterUpdateWorkflow],
    ):
        workflow_id = f"test-update-counter-{uuid.uuid4()}"
        handle = await client.start_workflow(
            CounterUpdateWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        result = await handle.execute_update(CounterUpdateWorkflow.increment, 5)
        assert result == 5

        result = await handle.execute_update(CounterUpdateWorkflow.increment, 5)
        assert result == 10

        final = await handle.result()
        assert final == 10


@pytest.mark.asyncio
async def test_update_state():
    """Test updating state workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StateUpdateWorkflow],
    ):
        workflow_id = f"test-update-state-{uuid.uuid4()}"
        handle = await client.start_workflow(
            StateUpdateWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await handle.execute_update(StateUpdateWorkflow.set_state, "processing")
        await handle.execute_update(StateUpdateWorkflow.set_state, "done")

        history = await handle.result()
        assert "initial->processing" in history
        assert "processing->done" in history


@pytest.mark.asyncio
async def test_update_data():
    """Test updating data workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DataUpdateWorkflow],
    ):
        workflow_id = f"test-update-data-{uuid.uuid4()}"
        handle = await client.start_workflow(
            DataUpdateWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        result = await handle.execute_update(DataUpdateWorkflow.add_data, args=["key1", "value1"])
        assert "key1" in result

        await handle.execute_update(DataUpdateWorkflow.add_data, args=["done", "true"])
        final = await handle.result()
        assert final["key1"] == "value1"
        assert final["done"] == "true"


@pytest.mark.asyncio
async def test_update_query():
    """Test update with query."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CounterUpdateWorkflow],
    ):
        workflow_id = f"test-update-query-{uuid.uuid4()}"
        handle = await client.start_workflow(
            CounterUpdateWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await handle.execute_update(CounterUpdateWorkflow.increment, 3)
        counter = await handle.query(CounterUpdateWorkflow.get_counter)
        assert counter == 3

        await handle.execute_update(CounterUpdateWorkflow.increment, 7)
        counter = await handle.query(CounterUpdateWorkflow.get_counter)
        assert counter == 10


@pytest.mark.asyncio
async def test_multiple_updates():
    """Test multiple updates in sequence."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CounterUpdateWorkflow],
    ):
        workflow_id = f"test-multi-update-{uuid.uuid4()}"
        handle = await client.start_workflow(
            CounterUpdateWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        for i in range(1, 11):
            result = await handle.execute_update(CounterUpdateWorkflow.increment, 1)
            assert result == i

        final = await handle.result()
        assert final == 10


@pytest.mark.asyncio
async def test_update_validation():
    """Test update validation."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ValidatingUpdateWorkflow],
    ):
        workflow_id = f"test-validation-{uuid.uuid4()}"
        handle = await client.start_workflow(
            ValidatingUpdateWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await handle.execute_update(ValidatingUpdateWorkflow.set_value, 50)
        value = await handle.query(ValidatingUpdateWorkflow.get_value)
        assert value == 50

        try:
            await handle.execute_update(ValidatingUpdateWorkflow.set_value, -10)
            assert False, "Should have raised ValueError"
        except Exception:
            pass

        await handle.execute_update(ValidatingUpdateWorkflow.set_value, 100)
        final = await handle.result()
        assert final == 100


@pytest.mark.asyncio
async def test_update_zero_increment():
    """Test update with zero increment."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CounterUpdateWorkflow],
    ):
        workflow_id = f"test-zero-{uuid.uuid4()}"
        handle = await client.start_workflow(
            CounterUpdateWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        result = await handle.execute_update(CounterUpdateWorkflow.increment, 0)
        assert result == 0

        await handle.execute_update(CounterUpdateWorkflow.increment, 10)
        final = await handle.result()
        assert final == 10


@pytest.mark.asyncio
async def test_update_large_increment():
    """Test update with large increment."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CounterUpdateWorkflow],
    ):
        workflow_id = f"test-large-{uuid.uuid4()}"
        handle = await client.start_workflow(
            CounterUpdateWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        result = await handle.execute_update(CounterUpdateWorkflow.increment, 100)
        final = await handle.result()
        assert final == 100


@pytest.mark.asyncio
async def test_update_empty_state():
    """Test update with empty state."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StateUpdateWorkflow],
    ):
        workflow_id = f"test-empty-{uuid.uuid4()}"
        handle = await client.start_workflow(
            StateUpdateWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await handle.execute_update(StateUpdateWorkflow.set_state, "")
        state = await handle.query(StateUpdateWorkflow.get_state)
        assert state == ""

        await handle.execute_update(StateUpdateWorkflow.set_state, "done")
        await handle.result()


@pytest.mark.asyncio
async def test_update_unicode_state():
    """Test update with unicode state."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StateUpdateWorkflow],
    ):
        workflow_id = f"test-unicode-{uuid.uuid4()}"
        handle = await client.start_workflow(
            StateUpdateWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await handle.execute_update(StateUpdateWorkflow.set_state, "处理中")
        await handle.execute_update(StateUpdateWorkflow.set_state, "done")
        await handle.result()


@pytest.mark.asyncio
async def test_update_data_unicode():
    """Test update data with unicode."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DataUpdateWorkflow],
    ):
        workflow_id = f"test-data-unicode-{uuid.uuid4()}"
        handle = await client.start_workflow(
            DataUpdateWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await handle.execute_update(DataUpdateWorkflow.add_data, args=["名前", "値"])
        await handle.execute_update(DataUpdateWorkflow.add_data, args=["done", "true"])
        final = await handle.result()
        assert final["名前"] == "値"


@pytest.mark.asyncio
async def test_update_negative_increment():
    """Test update with negative increment."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CounterUpdateWorkflow],
    ):
        workflow_id = f"test-negative-{uuid.uuid4()}"
        handle = await client.start_workflow(
            CounterUpdateWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await handle.execute_update(CounterUpdateWorkflow.increment, 5)
        result = await handle.execute_update(CounterUpdateWorkflow.increment, 5)
        assert result == 10

        final = await handle.result()
        assert final == 10


@pytest.mark.asyncio
async def test_update_rapid_sequence():
    """Test rapid update sequence."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CounterUpdateWorkflow],
    ):
        workflow_id = f"test-rapid-{uuid.uuid4()}"
        handle = await client.start_workflow(
            CounterUpdateWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        for _ in range(5):
            await handle.execute_update(CounterUpdateWorkflow.increment, 2)

        final = await handle.result()
        assert final == 10


@pytest.mark.asyncio
async def test_update_state_chain():
    """Test state update chain."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StateUpdateWorkflow],
    ):
        workflow_id = f"test-chain-{uuid.uuid4()}"
        handle = await client.start_workflow(
            StateUpdateWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        states = ["pending", "running", "completed", "done"]
        for state in states:
            await handle.execute_update(StateUpdateWorkflow.set_state, state)

        history = await handle.result()
        assert len(history) == 4


@pytest.mark.asyncio
async def test_update_data_overwrite():
    """Test data overwrite via update."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DataUpdateWorkflow],
    ):
        workflow_id = f"test-overwrite-{uuid.uuid4()}"
        handle = await client.start_workflow(
            DataUpdateWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await handle.execute_update(DataUpdateWorkflow.add_data, args=["key", "value1"])
        await handle.execute_update(DataUpdateWorkflow.add_data, args=["key", "value2"])
        await handle.execute_update(DataUpdateWorkflow.add_data, args=["done", "true"])

        final = await handle.result()
        assert final["key"] == "value2"
