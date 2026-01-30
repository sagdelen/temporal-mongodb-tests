"""Long-running workflow tests - workflows with extended duration."""

import os
import uuid
import pytest
import asyncio
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity


TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-longrunning"


@activity.defn
async def checkpoint_activity(step: int) -> str:
    """Record checkpoint."""
    await asyncio.sleep(0.1)
    return f"checkpoint-{step}"


@activity.defn
async def process_batch_activity(batch_id: int) -> dict:
    """Process a batch."""
    await asyncio.sleep(0.1)
    return {"batch_id": batch_id, "processed": True}


@workflow.defn
class MultiStepWorkflow:
    @workflow.run
    async def run(self, steps: int) -> list:
        results = []
        for step in range(steps):
            result = await workflow.execute_activity(
                checkpoint_activity,
                step,
                start_to_close_timeout=timedelta(seconds=30),
            )
            results.append(result)
            # Short sleep between steps
            await asyncio.sleep(0.1)
        return results


@workflow.defn
class BatchProcessingWorkflow:
    @workflow.run
    async def run(self, num_batches: int) -> list:
        results = []
        for batch_id in range(num_batches):
            result = await workflow.execute_activity(
                process_batch_activity,
                batch_id,
                start_to_close_timeout=timedelta(seconds=30),
            )
            results.append(result)
        return results


@workflow.defn
class TimerBasedWorkflow:
    @workflow.run
    async def run(self, delays: list) -> int:
        count = 0
        for delay_ms in delays:
            await asyncio.sleep(delay_ms / 1000.0)
            count += 1
        return count


@workflow.defn
class CheckpointWorkflow:
    @workflow.run
    async def run(self, checkpoint_count: int) -> dict:
        checkpoints = []
        for i in range(checkpoint_count):
            cp = await workflow.execute_activity(
                checkpoint_activity,
                i,
                start_to_close_timeout=timedelta(seconds=30),
            )
            checkpoints.append(cp)

        return {
            "total": checkpoint_count,
            "checkpoints": checkpoints,
        }


@pytest.mark.asyncio
async def test_multi_step_workflow():
    """Test workflow with multiple steps."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MultiStepWorkflow],
        activities=[checkpoint_activity],
    ):
        result = await client.execute_workflow(
            MultiStepWorkflow.run,
            5,
            id=f"test-multistep-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert len(result) == 5
        assert result[0] == "checkpoint-0"
        assert result[4] == "checkpoint-4"


@pytest.mark.asyncio
async def test_batch_processing():
    """Test batch processing workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[BatchProcessingWorkflow],
        activities=[process_batch_activity],
    ):
        result = await client.execute_workflow(
            BatchProcessingWorkflow.run,
            3,
            id=f"test-batch-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert len(result) == 3
        assert all(r["processed"] for r in result)


@pytest.mark.asyncio
async def test_timer_based_workflow():
    """Test workflow with multiple timers."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[TimerBasedWorkflow],
    ):
        result = await client.execute_workflow(
            TimerBasedWorkflow.run,
            [100, 100, 100],  # 3 x 100ms delays
            id=f"test-timer-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == 3


@pytest.mark.asyncio
async def test_checkpoint_workflow():
    """Test workflow with checkpoints."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CheckpointWorkflow],
        activities=[checkpoint_activity],
    ):
        result = await client.execute_workflow(
            CheckpointWorkflow.run,
            4,
            id=f"test-checkpoint-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["total"] == 4
        assert len(result["checkpoints"]) == 4


@pytest.mark.asyncio
async def test_single_step():
    """Test workflow with single step."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MultiStepWorkflow],
        activities=[checkpoint_activity],
    ):
        result = await client.execute_workflow(
            MultiStepWorkflow.run,
            1,
            id=f"test-single-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert len(result) == 1


@pytest.mark.asyncio
async def test_zero_steps():
    """Test workflow with zero steps."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MultiStepWorkflow],
        activities=[checkpoint_activity],
    ):
        result = await client.execute_workflow(
            MultiStepWorkflow.run,
            0,
            id=f"test-zero-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert len(result) == 0


@pytest.mark.asyncio
async def test_many_steps():
    """Test workflow with many steps."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MultiStepWorkflow],
        activities=[checkpoint_activity],
    ):
        result = await client.execute_workflow(
            MultiStepWorkflow.run,
            20,
            id=f"test-many-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert len(result) == 20


@pytest.mark.asyncio
async def test_single_batch():
    """Test processing single batch."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[BatchProcessingWorkflow],
        activities=[process_batch_activity],
    ):
        result = await client.execute_workflow(
            BatchProcessingWorkflow.run,
            1,
            id=f"test-single-batch-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert len(result) == 1
        assert result[0]["batch_id"] == 0


@pytest.mark.asyncio
async def test_zero_batches():
    """Test processing zero batches."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[BatchProcessingWorkflow],
        activities=[process_batch_activity],
    ):
        result = await client.execute_workflow(
            BatchProcessingWorkflow.run,
            0,
            id=f"test-zero-batch-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert len(result) == 0


@pytest.mark.asyncio
async def test_many_batches():
    """Test processing many batches."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[BatchProcessingWorkflow],
        activities=[process_batch_activity],
    ):
        result = await client.execute_workflow(
            BatchProcessingWorkflow.run,
            15,
            id=f"test-many-batch-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert len(result) == 15


@pytest.mark.asyncio
async def test_single_timer():
    """Test workflow with single timer."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[TimerBasedWorkflow],
    ):
        result = await client.execute_workflow(
            TimerBasedWorkflow.run,
            [100],
            id=f"test-single-timer-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == 1


@pytest.mark.asyncio
async def test_zero_timers():
    """Test workflow with no timers."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[TimerBasedWorkflow],
    ):
        result = await client.execute_workflow(
            TimerBasedWorkflow.run,
            [],
            id=f"test-zero-timer-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == 0


@pytest.mark.asyncio
async def test_many_timers():
    """Test workflow with many timers."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[TimerBasedWorkflow],
    ):
        delays = [50] * 10  # 10 x 50ms delays
        result = await client.execute_workflow(
            TimerBasedWorkflow.run,
            delays,
            id=f"test-many-timer-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == 10


@pytest.mark.asyncio
async def test_variable_delays():
    """Test workflow with variable delays."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[TimerBasedWorkflow],
    ):
        result = await client.execute_workflow(
            TimerBasedWorkflow.run,
            [50, 100, 150],
            id=f"test-variable-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == 3


@pytest.mark.asyncio
async def test_checkpoint_single():
    """Test workflow with single checkpoint."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CheckpointWorkflow],
        activities=[checkpoint_activity],
    ):
        result = await client.execute_workflow(
            CheckpointWorkflow.run,
            1,
            id=f"test-cp-single-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["total"] == 1


@pytest.mark.asyncio
async def test_checkpoint_zero():
    """Test workflow with zero checkpoints."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CheckpointWorkflow],
        activities=[checkpoint_activity],
    ):
        result = await client.execute_workflow(
            CheckpointWorkflow.run,
            0,
            id=f"test-cp-zero-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["total"] == 0


@pytest.mark.asyncio
async def test_checkpoint_many():
    """Test workflow with many checkpoints."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CheckpointWorkflow],
        activities=[checkpoint_activity],
    ):
        result = await client.execute_workflow(
            CheckpointWorkflow.run,
            25,
            id=f"test-cp-many-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["total"] == 25
        assert len(result["checkpoints"]) == 25



# History stress tests for MongoDB

@pytest.mark.asyncio
async def test_many_activities_50():
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)
    async with Worker(client, task_queue=TASK_QUEUE,
                      workflows=[MultiStepWorkflow], activities=[checkpoint_activity]):
        result = await client.execute_workflow(
            MultiStepWorkflow.run, 50,
            id=f"test-50steps-{uuid.uuid4()}", task_queue=TASK_QUEUE
        )
        assert len(result) == 50


@pytest.mark.asyncio
async def test_batch_processing_20():
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)
    async with Worker(client, task_queue=TASK_QUEUE,
                      workflows=[BatchProcessingWorkflow], activities=[process_batch_activity]):
        result = await client.execute_workflow(
            BatchProcessingWorkflow.run, 20,
            id=f"test-20batch-{uuid.uuid4()}", task_queue=TASK_QUEUE
        )
        assert len(result) == 20
        assert all(r["processed"] for r in result)


@pytest.mark.asyncio
async def test_checkpoint_50():
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)
    async with Worker(client, task_queue=TASK_QUEUE,
                      workflows=[CheckpointWorkflow], activities=[checkpoint_activity]):
        result = await client.execute_workflow(
            CheckpointWorkflow.run, 50,
            id=f"test-cp50-{uuid.uuid4()}", task_queue=TASK_QUEUE
        )
        assert result["total"] == 50


@pytest.mark.asyncio
async def test_history_query_after_many_events():
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)
    async with Worker(client, task_queue=TASK_QUEUE,
                      workflows=[MultiStepWorkflow], activities=[checkpoint_activity]):
        wf_id = f"test-history-{uuid.uuid4()}"
        await client.execute_workflow(
            MultiStepWorkflow.run, 30,
            id=wf_id, task_queue=TASK_QUEUE
        )
        handle = client.get_workflow_handle(wf_id)
        desc = await handle.describe()
        assert desc.status.name == "COMPLETED"


@pytest.mark.asyncio
async def test_concurrent_multi_step():
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)
    async with Worker(client, task_queue=TASK_QUEUE,
                      workflows=[MultiStepWorkflow], activities=[checkpoint_activity]):
        handles = []
        for i in range(5):
            h = await client.start_workflow(
                MultiStepWorkflow.run, 10,
                id=f"test-concurrent-{uuid.uuid4()}", task_queue=TASK_QUEUE
            )
            handles.append(h)
        results = [await h.result() for h in handles]
        assert all(len(r) == 10 for r in results)
