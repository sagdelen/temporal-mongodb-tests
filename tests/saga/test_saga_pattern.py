"""Saga pattern tests - successful compensating transaction scenarios."""

import os
import uuid
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity


TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-saga"


@activity.defn
async def reserve_inventory(item: str, quantity: int) -> dict:
    """Reserve inventory."""
    return {"item": item, "quantity": quantity, "reserved": True}


@activity.defn
async def charge_payment(amount: float) -> dict:
    """Charge payment."""
    return {"amount": amount, "charged": True}


@activity.defn
async def ship_order(order_id: str) -> dict:
    """Ship order."""
    return {"order_id": order_id, "shipped": True}


@workflow.defn
class SagaWorkflow:
    @workflow.run
    async def run(self, item: str, quantity: int, amount: float, order_id: str) -> dict:
        inventory = await workflow.execute_activity(
            reserve_inventory,
            args=[item, quantity],
            start_to_close_timeout=timedelta(seconds=30),
        )

        payment = await workflow.execute_activity(
            charge_payment,
            amount,
            start_to_close_timeout=timedelta(seconds=30),
        )

        shipment = await workflow.execute_activity(
            ship_order,
            order_id,
            start_to_close_timeout=timedelta(seconds=30),
        )

        return {
            "inventory": inventory,
            "payment": payment,
            "shipment": shipment,
        }


@pytest.mark.asyncio
async def test_saga_success():
    """Test successful saga."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SagaWorkflow],
        activities=[reserve_inventory, charge_payment, ship_order],
    ):
        result = await client.execute_workflow(
            SagaWorkflow.run,
            args=["laptop", 1, 999.99, "order-123"],
            id=f"saga-1-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["inventory"]["reserved"] is True
        assert result["payment"]["charged"] is True


@pytest.mark.asyncio
async def test_saga_zero_quantity():
    """Test saga with zero quantity."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SagaWorkflow],
        activities=[reserve_inventory, charge_payment, ship_order],
    ):
        result = await client.execute_workflow(
            SagaWorkflow.run,
            args=["item", 0, 10.0, "order-0"],
            id=f"saga-2-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["inventory"]["quantity"] == 0


@pytest.mark.asyncio
async def test_saga_zero_amount():
    """Test saga with zero amount."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SagaWorkflow],
        activities=[reserve_inventory, charge_payment, ship_order],
    ):
        result = await client.execute_workflow(
            SagaWorkflow.run,
            args=["free", 1, 0.0, "order-free"],
            id=f"saga-3-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["payment"]["amount"] == 0.0


@pytest.mark.asyncio
async def test_saga_large_quantity():
    """Test saga with large quantity."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SagaWorkflow],
        activities=[reserve_inventory, charge_payment, ship_order],
    ):
        result = await client.execute_workflow(
            SagaWorkflow.run,
            args=["bulk", 1000, 10.0, "order-bulk"],
            id=f"saga-4-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["inventory"]["quantity"] == 1000


@pytest.mark.asyncio
async def test_saga_unicode_item():
    """Test saga with unicode."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SagaWorkflow],
        activities=[reserve_inventory, charge_payment, ship_order],
    ):
        result = await client.execute_workflow(
            SagaWorkflow.run,
            args=["商品", 1, 99.0, "order-cn"],
            id=f"saga-5-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert "商品" in result["inventory"]["item"]
