"""Retry policy tests for workflows and activities."""

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
TASK_QUEUE = "e2e-retry-queue"

attempt_counts: dict[str, int] = {}


@activity.defn
async def counting_activity(key: str, fail_until: int) -> int:
    global attempt_counts
    attempt_counts[key] = attempt_counts.get(key, 0) + 1
    if attempt_counts[key] < fail_until:
        raise ApplicationError(f"Attempt {attempt_counts[key]} failed")
    return attempt_counts[key]


@activity.defn
async def always_fail_activity() -> str:
    raise ApplicationError("Always fails", non_retryable=True)


@activity.defn
async def retryable_error_activity(key: str) -> str:
    global attempt_counts
    attempt_counts[key] = attempt_counts.get(key, 0) + 1
    if attempt_counts[key] < 3:
        raise ApplicationError("Retryable error")
    return "success"


@activity.defn
async def non_retryable_error_activity() -> str:
    raise ApplicationError("Non-retryable", non_retryable=True)


@workflow.defn
class RetryWorkflow:
    @workflow.run
    async def run(self, key: str, fail_until: int, max_attempts: int) -> int:
        return await workflow.execute_activity(
            counting_activity,
            args=[key, fail_until],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(milliseconds=50),
                maximum_interval=timedelta(milliseconds=200),
                maximum_attempts=max_attempts,
            ),
        )


@workflow.defn
class NoRetryWorkflow:
    @workflow.run
    async def run(self) -> str:
        return await workflow.execute_activity(
            always_fail_activity,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )


@workflow.defn
class BackoffRetryWorkflow:
    @workflow.run
    async def run(self, key: str) -> str:
        return await workflow.execute_activity(
            retryable_error_activity,
            key,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(milliseconds=100),
                backoff_coefficient=2.0,
                maximum_interval=timedelta(seconds=1),
                maximum_attempts=5,
            ),
        )


@workflow.defn
class NonRetryableWorkflow:
    @workflow.run
    async def run(self) -> str:
        return await workflow.execute_activity(
            non_retryable_error_activity,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )


@pytest.mark.asyncio
async def test_retry_succeeds_after_failures():
    """Test activity succeeds after retries."""
    global attempt_counts
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RetryWorkflow],
        activities=[counting_activity],
    ):
        key = f"retry-success-{uuid.uuid4()}"
        attempt_counts[key] = 0
        workflow_id = f"test-retry-success-{uuid.uuid4()}"
        result = await client.execute_workflow(
            RetryWorkflow.run,
            args=[key, 3, 5],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == 3


@pytest.mark.asyncio
async def test_retry_exhausted():
    """Test activity fails after max attempts."""
    global attempt_counts
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RetryWorkflow],
        activities=[counting_activity],
    ):
        key = f"retry-exhaust-{uuid.uuid4()}"
        attempt_counts[key] = 0
        workflow_id = f"test-retry-exhaust-{uuid.uuid4()}"
        with pytest.raises(WorkflowFailureError):
            await client.execute_workflow(
                RetryWorkflow.run,
                args=[key, 10, 3],
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )


@pytest.mark.asyncio
async def test_no_retry_policy():
    """Test activity with no retries."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[NoRetryWorkflow],
        activities=[always_fail_activity],
    ):
        workflow_id = f"test-no-retry-{uuid.uuid4()}"
        with pytest.raises(WorkflowFailureError):
            await client.execute_workflow(
                NoRetryWorkflow.run,
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )


@pytest.mark.asyncio
async def test_backoff_retry():
    """Test exponential backoff retry."""
    global attempt_counts
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[BackoffRetryWorkflow],
        activities=[retryable_error_activity],
    ):
        key = f"backoff-{uuid.uuid4()}"
        attempt_counts[key] = 0
        workflow_id = f"test-backoff-{uuid.uuid4()}"
        result = await client.execute_workflow(
            BackoffRetryWorkflow.run,
            key,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == "success"


@pytest.mark.asyncio
async def test_non_retryable_error():
    """Test non-retryable error stops retries."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[NonRetryableWorkflow],
        activities=[non_retryable_error_activity],
    ):
        workflow_id = f"test-non-retryable-{uuid.uuid4()}"
        with pytest.raises(WorkflowFailureError):
            await client.execute_workflow(
                NonRetryableWorkflow.run,
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )


@pytest.mark.asyncio
async def test_retry_with_exact_attempts():
    """Test retry succeeds on exact max attempt."""
    global attempt_counts
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RetryWorkflow],
        activities=[counting_activity],
    ):
        key = f"exact-{uuid.uuid4()}"
        attempt_counts[key] = 0
        workflow_id = f"test-exact-{uuid.uuid4()}"
        result = await client.execute_workflow(
            RetryWorkflow.run,
            args=[key, 5, 5],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        assert result == 5
