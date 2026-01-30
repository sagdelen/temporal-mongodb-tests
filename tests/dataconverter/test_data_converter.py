"""Data converter and payload encoding tests."""

import os
import uuid
import json
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow
from temporalio.converter import DataConverter, EncodingPayloadConverter
from temporalio.api.common.v1 import Payload


TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-dataconverter-queue"


@workflow.defn
class DataWorkflow:
    @workflow.run
    async def run(self, data: dict) -> dict:
        return {"received": data, "processed": True}


@workflow.defn
class ComplexDataWorkflow:
    @workflow.run
    async def run(self, items: list) -> int:
        return len(items)


@workflow.defn
class BinaryDataWorkflow:
    @workflow.run
    async def run(self, data: bytes) -> int:
        return len(data)


@pytest.mark.asyncio
async def test_json_data_converter():
    """Test default JSON data converter."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[DataWorkflow]):
        workflow_id = f"test-json-{uuid.uuid4()}"
        data = {"key": "value", "number": 42}
        result = await client.execute_workflow(
            DataWorkflow.run,
            data,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result["received"] == data
        assert result["processed"] is True


@pytest.mark.asyncio
async def test_complex_data_structures():
    """Test complex nested data structures."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[ComplexDataWorkflow]):
        workflow_id = f"test-complex-{uuid.uuid4()}"
        items = [
            {"id": 1, "name": "item1"},
            {"id": 2, "name": "item2"},
            {"id": 3, "name": "item3"},
        ]
        result = await client.execute_workflow(
            ComplexDataWorkflow.run,
            items,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == 3


@pytest.mark.asyncio
async def test_binary_data():
    """Test binary data handling."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[BinaryDataWorkflow]):
        workflow_id = f"test-binary-{uuid.uuid4()}"
        data = b"binary data content"
        result = await client.execute_workflow(
            BinaryDataWorkflow.run,
            data,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == len(data)


@pytest.mark.asyncio
async def test_large_payload():
    """Test handling large payloads."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[DataWorkflow]):
        workflow_id = f"test-large-{uuid.uuid4()}"
        data = {"items": [f"item-{i}" for i in range(100)]}
        result = await client.execute_workflow(
            DataWorkflow.run,
            data,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert len(result["received"]["items"]) == 100


@pytest.mark.asyncio
async def test_unicode_data():
    """Test unicode string handling."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[DataWorkflow]):
        workflow_id = f"test-unicode-{uuid.uuid4()}"
        data = {"text": "Hello 世界 🌍", "emoji": "🚀"}
        result = await client.execute_workflow(
            DataWorkflow.run,
            data,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result["received"]["text"] == "Hello 世界 🌍"
        assert result["received"]["emoji"] == "🚀"
