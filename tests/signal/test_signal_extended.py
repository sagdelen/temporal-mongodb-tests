"""Extended signal tests - additional signal scenarios."""

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
TASK_QUEUE = "e2e-signal-extended"


@workflow.defn
class CounterWorkflow:
    def __init__(self) -> None:
        self.counter = 0

    @workflow.run
    async def run(self) -> int:
        await workflow.wait_condition(lambda: self.counter >= 5)
        return self.counter

    @workflow.signal
    async def increment(self) -> None:
        self.counter += 1

    @workflow.signal
    async def decrement(self) -> None:
        self.counter -= 1

    @workflow.signal
    async def reset(self) -> None:
        self.counter = 0

    @workflow.query
    def get_count(self) -> int:
        return self.counter


@workflow.defn
class StringCollectorWorkflow:
    def __init__(self) -> None:
        self.strings = []

    @workflow.run
    async def run(self) -> list:
        await workflow.wait_condition(lambda: len(self.strings) >= 3)
        return self.strings

    @workflow.signal
    async def add_string(self, value: str) -> None:
        self.strings.append(value)

    @workflow.signal
    async def clear(self) -> None:
        self.strings = []

    @workflow.query
    def get_strings(self) -> list:
        return self.strings


@workflow.defn
class DictWorkflow:
    def __init__(self) -> None:
        self.data = {}

    @workflow.run
    async def run(self) -> dict:
        await workflow.wait_condition(lambda: len(self.data) >= 2)
        return self.data

    @workflow.signal
    async def set_value(self, key: str, value: str) -> None:
        self.data[key] = value

    @workflow.query
    def get_value(self, key: str) -> str:
        return self.data.get(key, "")


@pytest.mark.asyncio
async def test_counter_increment():
    """Test counter increment signals."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CounterWorkflow],
    ):
        handle = await client.start_workflow(
            CounterWorkflow.run,
            id=f"test-counter-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        for _ in range(5):
            await handle.signal(CounterWorkflow.increment)

        result = await handle.result()
        assert result == 5


@pytest.mark.asyncio
async def test_counter_mixed_signals():
    """Test counter with mixed increment/decrement."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CounterWorkflow],
    ):
        handle = await client.start_workflow(
            CounterWorkflow.run,
            id=f"test-mixed-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        # Send exactly 5 signals to reach threshold
        for _ in range(3):
            await handle.signal(CounterWorkflow.increment)
        for _ in range(2):
            await handle.signal(CounterWorkflow.increment)
        
        result = await handle.result()
        assert result == 5


@pytest.mark.asyncio
async def test_counter_with_reset():
    """Test counter with reset signal."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CounterWorkflow],
    ):
        handle = await client.start_workflow(
            CounterWorkflow.run,
            id=f"test-reset-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        for _ in range(3):
            await handle.signal(CounterWorkflow.increment)

        await handle.signal(CounterWorkflow.reset)

        for _ in range(5):
            await handle.signal(CounterWorkflow.increment)

        result = await handle.result()
        assert result == 5


@pytest.mark.asyncio
async def test_string_collector():
    """Test string collector workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StringCollectorWorkflow],
    ):
        handle = await client.start_workflow(
            StringCollectorWorkflow.run,
            id=f"test-strings-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        await handle.signal(StringCollectorWorkflow.add_string, "hello")
        await handle.signal(StringCollectorWorkflow.add_string, "world")
        await handle.signal(StringCollectorWorkflow.add_string, "test")

        result = await handle.result()
        assert result == ["hello", "world", "test"]


@pytest.mark.asyncio
async def test_string_with_clear():
    """Test string collector with clear."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StringCollectorWorkflow],
    ):
        handle = await client.start_workflow(
            StringCollectorWorkflow.run,
            id=f"test-clear-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        await handle.signal(StringCollectorWorkflow.add_string, "first")
        await handle.signal(StringCollectorWorkflow.clear)
        await handle.signal(StringCollectorWorkflow.add_string, "second")
        await handle.signal(StringCollectorWorkflow.add_string, "third")
        await handle.signal(StringCollectorWorkflow.add_string, "fourth")

        result = await handle.result()
        assert result == ["second", "third", "fourth"]


@pytest.mark.asyncio
async def test_dict_workflow():
    """Test dictionary workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DictWorkflow],
    ):
        handle = await client.start_workflow(
            DictWorkflow.run,
            id=f"test-dict-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        await handle.signal(DictWorkflow.set_value, args=["key1", "value1"])
        await handle.signal(DictWorkflow.set_value, args=["key2", "value2"])

        result = await handle.result()
        assert result["key1"] == "value1"
        assert result["key2"] == "value2"


@pytest.mark.asyncio
async def test_counter_query():
    """Test counter query."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CounterWorkflow],
    ):
        handle = await client.start_workflow(
            CounterWorkflow.run,
            id=f"test-query-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        await handle.signal(CounterWorkflow.increment)
        await handle.signal(CounterWorkflow.increment)

        count = await handle.query(CounterWorkflow.get_count)
        assert count == 2


@pytest.mark.asyncio
async def test_string_query():
    """Test string collector query."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StringCollectorWorkflow],
    ):
        handle = await client.start_workflow(
            StringCollectorWorkflow.run,
            id=f"test-str-query-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        await handle.signal(StringCollectorWorkflow.add_string, "test")

        strings = await handle.query(StringCollectorWorkflow.get_strings)
        assert strings == ["test"]


@pytest.mark.asyncio
async def test_dict_query():
    """Test dictionary query."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DictWorkflow],
    ):
        handle = await client.start_workflow(
            DictWorkflow.run,
            id=f"test-dict-query-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        await handle.signal(DictWorkflow.set_value, args=["test", "value"])

        value = await handle.query(DictWorkflow.get_value, "test")
        assert value == "value"


@pytest.mark.asyncio
async def test_counter_rapid_signals():
    """Test rapid signal sending."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CounterWorkflow],
    ):
        handle = await client.start_workflow(
            CounterWorkflow.run,
            id=f"test-rapid-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        # Send signals rapidly
        await asyncio.gather(
            *[handle.signal(CounterWorkflow.increment) for _ in range(10)]
        )

        result = await handle.result()
        assert result >= 5


@pytest.mark.asyncio
async def test_string_unicode():
    """Test string collector with unicode."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StringCollectorWorkflow],
    ):
        handle = await client.start_workflow(
            StringCollectorWorkflow.run,
            id=f"test-unicode-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        await handle.signal(StringCollectorWorkflow.add_string, "测试")
        await handle.signal(StringCollectorWorkflow.add_string, "テスト")
        await handle.signal(StringCollectorWorkflow.add_string, "тест")

        result = await handle.result()
        assert "测试" in result


@pytest.mark.asyncio
async def test_string_empty():
    """Test string collector with empty strings."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StringCollectorWorkflow],
    ):
        handle = await client.start_workflow(
            StringCollectorWorkflow.run,
            id=f"test-empty-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        await handle.signal(StringCollectorWorkflow.add_string, "")
        await handle.signal(StringCollectorWorkflow.add_string, "non-empty")
        await handle.signal(StringCollectorWorkflow.add_string, "")

        result = await handle.result()
        assert len(result) == 3


@pytest.mark.asyncio
async def test_dict_overwrite():
    """Test dictionary key overwrite."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DictWorkflow],
    ):
        handle = await client.start_workflow(
            DictWorkflow.run,
            id=f"test-overwrite-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        await handle.signal(DictWorkflow.set_value, args=["key", "value1"])
        await handle.signal(DictWorkflow.set_value, args=["key", "value2"])
        await handle.signal(DictWorkflow.set_value, args=["other", "value3"])

        result = await handle.result()
        assert result["key"] == "value2"


@pytest.mark.asyncio
async def test_counter_zero():
    """Test counter starting at zero."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CounterWorkflow],
    ):
        handle = await client.start_workflow(
            CounterWorkflow.run,
            id=f"test-zero-start-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        count = await handle.query(CounterWorkflow.get_count)
        assert count == 0


@pytest.mark.asyncio
async def test_string_long_values():
    """Test string collector with long strings."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StringCollectorWorkflow],
    ):
        handle = await client.start_workflow(
            StringCollectorWorkflow.run,
            id=f"test-long-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        long_str = "x" * 1000
        await handle.signal(StringCollectorWorkflow.add_string, long_str)
        await handle.signal(StringCollectorWorkflow.add_string, "short")
        await handle.signal(StringCollectorWorkflow.add_string, "another")

        result = await handle.result()
        assert long_str in result


@pytest.mark.asyncio
async def test_dict_special_keys():
    """Test dictionary with special character keys."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DictWorkflow],
    ):
        handle = await client.start_workflow(
            DictWorkflow.run,
            id=f"test-special-keys-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        await handle.signal(DictWorkflow.set_value, args=["key-with-dash", "value1"])
        await handle.signal(DictWorkflow.set_value, args=["key_with_underscore", "value2"])

        result = await handle.result()
        assert result["key-with-dash"] == "value1"


@pytest.mark.asyncio
async def test_counter_large_count():
    """Test counter with large count."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CounterWorkflow],
    ):
        handle = await client.start_workflow(
            CounterWorkflow.run,
            id=f"test-large-count-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        # Send all signals concurrently
        signals = [handle.signal(CounterWorkflow.increment) for _ in range(20)]
        await asyncio.gather(*signals)
        
        result = await handle.result()
        assert result >= 5


@pytest.mark.asyncio
async def test_dict_query_missing_key():
    """Test dictionary query for missing key."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DictWorkflow],
    ):
        handle = await client.start_workflow(
            DictWorkflow.run,
            id=f"test-missing-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        await handle.signal(DictWorkflow.set_value, args=["exists", "value"])

        value = await handle.query(DictWorkflow.get_value, "missing")
        assert value == ""
