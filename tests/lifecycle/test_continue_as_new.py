"""Continue-as-new tests."""

import os
import uuid
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-continue-queue"


@workflow.defn
class CountdownWorkflow:
    @workflow.run
    async def run(self, count: int) -> str:
        if count <= 0:
            return "done"
        # Continue as new with decremented count
        workflow.continue_as_new(count - 1)


@workflow.defn
class AccumulatorWorkflow:
    @workflow.run
    async def run(self, current: int, target: int) -> int:
        if current >= target:
            return current
        # Accumulate and continue
        workflow.continue_as_new(args=[current + 1, target])


@workflow.defn
class ContinueWithStateWorkflow:
    @workflow.run
    async def run(self, state: dict) -> dict:
        iteration = state.get("iteration", 0)
        max_iterations = state.get("max_iterations", 3)
        values = state.get("values", [])

        values.append(f"iter-{iteration}")

        if iteration >= max_iterations:
            return {"final_values": values, "iterations": iteration}

        workflow.continue_as_new(
            {
                "iteration": iteration + 1,
                "max_iterations": max_iterations,
                "values": values,
            }
        )


@pytest.mark.asyncio
async def test_simple_continue_as_new():
    """Test basic continue-as-new functionality."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[CountdownWorkflow]):
        workflow_id = f"test-continue-simple-{uuid.uuid4()}"
        result = await client.execute_workflow(
            CountdownWorkflow.run,
            3,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == "done"


@pytest.mark.asyncio
async def test_continue_as_new_accumulator():
    """Test continue-as-new with accumulating state."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[AccumulatorWorkflow]):
        workflow_id = f"test-continue-accum-{uuid.uuid4()}"
        result = await client.execute_workflow(
            AccumulatorWorkflow.run,
            args=[0, 5],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == 5


@pytest.mark.asyncio
async def test_continue_as_new_with_state():
    """Test continue-as-new preserving complex state."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client, task_queue=TASK_QUEUE, workflows=[ContinueWithStateWorkflow]
    ):
        workflow_id = f"test-continue-state-{uuid.uuid4()}"
        result = await client.execute_workflow(
            ContinueWithStateWorkflow.run,
            {"iteration": 0, "max_iterations": 3, "values": []},
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result["iterations"] == 3
        assert len(result["final_values"]) == 4  # 0, 1, 2, 3


@pytest.mark.asyncio
async def test_continue_as_new_history_check():
    """Test that continue-as-new creates new run."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[CountdownWorkflow]):
        workflow_id = f"test-continue-history-{uuid.uuid4()}"
        handle = await client.start_workflow(
            CountdownWorkflow.run,
            2,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        await handle.result()

        # Verify workflow completed
        desc = await handle.describe()
        assert desc.status.name == "COMPLETED"
