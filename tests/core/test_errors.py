"""Workflow error handling tests."""

import os
import uuid
import pytest
from datetime import timedelta
from temporalio.client import Client, WorkflowFailureError
from temporalio.worker import Worker
from temporalio import workflow, activity
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-error-queue"


class CustomError(Exception):
    pass


@activity.defn
async def failing_activity_error() -> str:
    raise ApplicationError("Activity failed intentionally", type="CustomActivityError")


@activity.defn
async def successful_activity() -> str:
    return "success"


@workflow.defn
class FailingWorkflow:
    @workflow.run
    async def run(self, should_fail: bool) -> str:
        if should_fail:
            raise ApplicationError(
                "Workflow failed intentionally", type="CustomWorkflowError"
            )
        return "success"


@workflow.defn
class ActivityErrorWorkflow:
    @workflow.run
    async def run(self) -> str:
        return await workflow.execute_activity(
            failing_activity_error,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )


@workflow.defn
class CatchActivityErrorWorkflow:
    @workflow.run
    async def run(self) -> str:
        try:
            await workflow.execute_activity(
                failing_activity_error,
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            return "activity_succeeded"
        except Exception as e:
            return f"caught_error: {type(e).__name__}"


@workflow.defn
class ConditionalErrorWorkflow:
    @workflow.run
    async def run(self, error_type: str) -> str:
        if error_type == "application":
            raise ApplicationError("Application error", type="AppError")
        elif error_type == "value":
            raise ValueError("Value error")
        elif error_type == "none":
            return "no_error"
        return "unknown"


@pytest.mark.asyncio
async def test_workflow_application_error():
    """Test workflow raising ApplicationError."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[FailingWorkflow]):
        workflow_id = f"test-error-app-{uuid.uuid4()}"
        with pytest.raises(WorkflowFailureError):
            await client.execute_workflow(
                FailingWorkflow.run,
                True,
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )


@pytest.mark.asyncio
async def test_workflow_success_path():
    """Test workflow success path."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[FailingWorkflow]):
        workflow_id = f"test-error-success-{uuid.uuid4()}"
        result = await client.execute_workflow(
            FailingWorkflow.run,
            False,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == "success"


@pytest.mark.asyncio
async def test_activity_error_propagation():
    """Test that activity errors propagate to workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ActivityErrorWorkflow],
        activities=[failing_activity_error],
    ):
        workflow_id = f"test-error-activity-{uuid.uuid4()}"
        with pytest.raises(WorkflowFailureError):
            await client.execute_workflow(
                ActivityErrorWorkflow.run,
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )


@pytest.mark.asyncio
async def test_catch_activity_error():
    """Test workflow catching activity error."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CatchActivityErrorWorkflow],
        activities=[failing_activity_error],
    ):
        workflow_id = f"test-error-catch-{uuid.uuid4()}"
        result = await client.execute_workflow(
            CatchActivityErrorWorkflow.run,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert "caught_error" in result


@pytest.mark.asyncio
async def test_failed_workflow_status():
    """Test that failed workflow has correct status."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[FailingWorkflow]):
        workflow_id = f"test-error-status-{uuid.uuid4()}"
        handle = await client.start_workflow(
            FailingWorkflow.run,
            True,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        with pytest.raises(WorkflowFailureError):
            await handle.result()

        desc = await handle.describe()
        assert desc.status.name == "FAILED"
