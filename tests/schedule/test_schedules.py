"""Scheduled workflows tests."""

import os
import uuid
import pytest
import asyncio
from datetime import timedelta
from temporalio.client import (
    Client,
    Schedule,
    ScheduleSpec,
    ScheduleIntervalSpec,
    ScheduleActionStartWorkflow,
    ScheduleState,
)
from temporalio.worker import Worker
from temporalio import workflow


TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-schedule-queue"


@workflow.defn
class ScheduledWorkflow:
    @workflow.run
    async def run(self) -> str:
        return "scheduled-complete"


@pytest.mark.asyncio
async def test_schedule_create():
    """Test creating a schedule."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[ScheduledWorkflow]):
        schedule_id = f"test-schedule-{uuid.uuid4()}"

        handle = await client.create_schedule(
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    ScheduledWorkflow.run,
                    id=f"scheduled-wf-{uuid.uuid4()}",
                    task_queue=TASK_QUEUE,
                ),
                spec=ScheduleSpec(
                    intervals=[ScheduleIntervalSpec(every=timedelta(hours=1))],
                ),
                state=ScheduleState(paused=True),
            ),
        )

        desc = await handle.describe()
        assert desc.id == schedule_id

        await handle.delete()


@pytest.mark.asyncio
async def test_schedule_trigger():
    """Test manually triggering a schedule."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[ScheduledWorkflow]):
        schedule_id = f"test-trigger-{uuid.uuid4()}"

        handle = await client.create_schedule(
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    ScheduledWorkflow.run,
                    id=f"triggered-wf-{uuid.uuid4()}",
                    task_queue=TASK_QUEUE,
                ),
                spec=ScheduleSpec(
                    intervals=[ScheduleIntervalSpec(every=timedelta(hours=1))],
                ),
                state=ScheduleState(paused=True),
            ),
        )

        await handle.trigger()
        await asyncio.sleep(1)

        desc = await handle.describe()
        assert desc.info.num_actions >= 1

        await handle.delete()


@pytest.mark.asyncio
async def test_schedule_pause_unpause():
    """Test pausing and unpausing a schedule."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[ScheduledWorkflow]):
        schedule_id = f"test-pause-{uuid.uuid4()}"

        handle = await client.create_schedule(
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    ScheduledWorkflow.run,
                    id=f"paused-wf-{uuid.uuid4()}",
                    task_queue=TASK_QUEUE,
                ),
                spec=ScheduleSpec(
                    intervals=[ScheduleIntervalSpec(every=timedelta(hours=1))],
                ),
            ),
        )

        await handle.pause()
        desc = await handle.describe()
        assert desc.schedule.state.paused is True

        await handle.unpause()
        desc = await handle.describe()
        assert desc.schedule.state.paused is False

        await handle.delete()


@pytest.mark.asyncio
async def test_schedule_delete():
    """Test deleting a schedule."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(client, task_queue=TASK_QUEUE, workflows=[ScheduledWorkflow]):
        schedule_id = f"test-delete-{uuid.uuid4()}"

        handle = await client.create_schedule(
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    ScheduledWorkflow.run,
                    id=f"deleted-wf-{uuid.uuid4()}",
                    task_queue=TASK_QUEUE,
                ),
                spec=ScheduleSpec(
                    intervals=[ScheduleIntervalSpec(every=timedelta(hours=1))],
                ),
                state=ScheduleState(paused=True),
            ),
        )

        await handle.delete()

        with pytest.raises(Exception):
            await handle.describe()
