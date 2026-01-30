"""Minimal failing saga test to debug MongoDB retry behavior."""

import os
import uuid
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity
from temporalio.exceptions import ActivityError
from temporalio.common import RetryPolicy


TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-saga-debug"


@activity.defn
async def success_activity() -> str:
    return "ok"


@activity.defn
async def fail_once_activity() -> str:
    raise RuntimeError("Intentional failure")


@activity.defn
async def reserve_inventory(item_id: str, quantity: int) -> str:
    return f"Reserved {quantity} of {item_id}"


@activity.defn
async def charge_payment(amount: float) -> str:
    if amount <= 0:
        raise ValueError("Invalid amount")
    return f"Charged ${amount}"


@activity.defn
async def ship_order(order_id: str) -> str:
    return f"Shipped {order_id}"


@activity.defn
async def cancel_inventory(item_id: str) -> str:
    return f"Cancelled reservation for {item_id}"


@activity.defn
async def refund_payment(amount: float) -> str:
    return f"Refunded ${amount}"


@workflow.defn
class MinimalFailingSaga:
    @workflow.run
    async def run(self) -> str:
        try:
            await workflow.execute_activity(
                success_activity,
                start_to_close_timeout=timedelta(seconds=5),
            )

            # This should fail with NO retry
            await workflow.execute_activity(
                fail_once_activity,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )

            return "should-not-reach"

        except ActivityError as e:
            return f"caught-error-{type(e).__name__}"


@workflow.defn
class CompensationSaga:
    @workflow.run
    async def run(self, item_id: str, quantity: int, amount: float) -> str:
        try:
            # Step 1: Reserve inventory
            await workflow.execute_activity(
                reserve_inventory,
                args=[item_id, quantity],
                start_to_close_timeout=timedelta(seconds=5),
            )

            # Step 2: Charge payment (this will fail if amount <= 0)
            await workflow.execute_activity(
                charge_payment,
                args=[amount],
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )

            # Step 3: Ship order
            await workflow.execute_activity(
                ship_order,
                args=[f"order-{item_id}"],
                start_to_close_timeout=timedelta(seconds=5),
            )

            return "success"

        except ActivityError as e:
            # Compensation: rollback inventory reservation
            await workflow.execute_activity(
                cancel_inventory,
                args=[item_id],
                start_to_close_timeout=timedelta(seconds=5),
            )
            return f"compensated-after-{type(e).__name__}"


@workflow.defn
class MultipleFailuresSaga:
    @workflow.run
    async def run(self) -> str:
        failures = []

        # Try multiple activities, catch each failure
        for i in range(3):
            try:
                await workflow.execute_activity(
                    fail_once_activity,
                    start_to_close_timeout=timedelta(seconds=5),
                    retry_policy=RetryPolicy(maximum_attempts=1),
                )
            except ActivityError as e:
                failures.append(f"failure-{i}")

        return f"caught-{len(failures)}-errors"


@pytest.mark.asyncio
async def test_minimal_failing_saga():
    """Test minimal failing saga - should complete in <10 seconds."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MinimalFailingSaga],
        activities=[success_activity, fail_once_activity],
    ):
        result = await client.execute_workflow(
            MinimalFailingSaga.run,
            id=f"minimal-fail-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
            execution_timeout=timedelta(seconds=30),
        )

        print(f"Result: {result}")
        assert "caught-error" in result


@pytest.mark.asyncio
async def test_compensation_saga_with_failure():
    """Test saga with compensation logic when payment fails."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CompensationSaga],
        activities=[
            reserve_inventory,
            charge_payment,
            ship_order,
            cancel_inventory,
            refund_payment,
        ],
    ):
        # Test with invalid amount (will fail)
        result = await client.execute_workflow(
            CompensationSaga.run,
            args=["item-123", 5, -10.0],  # Negative amount causes failure
            id=f"compensation-fail-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
            execution_timeout=timedelta(seconds=30),
        )

        print(f"Compensation result: {result}")
        assert "compensated-after" in result


@pytest.mark.asyncio
async def test_compensation_saga_success():
    """Test saga with successful execution (no compensation needed)."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CompensationSaga],
        activities=[
            reserve_inventory,
            charge_payment,
            ship_order,
            cancel_inventory,
        ],
    ):
        # Test with valid amount (will succeed)
        result = await client.execute_workflow(
            CompensationSaga.run,
            args=["item-456", 3, 99.99],  # Valid amount
            id=f"compensation-success-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
            execution_timeout=timedelta(seconds=30),
        )

        print(f"Success result: {result}")
        assert result == "success"


@pytest.mark.asyncio
async def test_multiple_failures_saga():
    """Test saga that handles multiple consecutive failures."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MultipleFailuresSaga],
        activities=[fail_once_activity],
    ):
        result = await client.execute_workflow(
            MultipleFailuresSaga.run,
            id=f"multiple-fail-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
            execution_timeout=timedelta(seconds=30),
        )

        print(f"Multiple failures result: {result}")
        assert result == "caught-3-errors"
