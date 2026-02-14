import pytest
import time
import asyncio
import json
from maker.core.events import (
    TaskSubmitted,
    PlanCreated,
    ValidationPassed,
    ValidationFailed,
    StepStarted,
    AgentSampleCompleted,
    AgentSampleRedFlagged,
    VoteCompleted,
    StepCompleted,
    StepFailed,
    TaskCompleted,
    TaskFailed,
    EventBus,
    event_to_dict,
)
from maker.core.models import TaskConfig, Plan, PlanStep, VotingSummary


class TestEventCreation:
    def test_task_submitted(self):
        config = TaskConfig(instruction="test")
        event = TaskSubmitted(
            timestamp=1000.0, instruction="test", config=config
        )
        assert event.type == "task_submitted"
        assert event.instruction == "test"

    def test_plan_created(self):
        plan = Plan(reasoning="r", steps=[])
        event = PlanCreated(timestamp=1000.0, plan=plan)
        assert event.type == "plan_created"
        assert event.plan.reasoning == "r"

    def test_validation_passed(self):
        event = ValidationPassed(timestamp=1000.0, checks_passed=12)
        assert event.type == "validation_passed"

    def test_validation_failed(self):
        errors = [{"check": "valid_yaml", "message": "bad yaml"}]
        event = ValidationFailed(timestamp=1000.0, errors=errors)
        assert event.type == "validation_failed"
        assert len(event.errors) == 1

    def test_step_started(self):
        event = StepStarted(timestamp=1000.0, step=0, title="fetch_data")
        assert event.type == "step_started"
        assert event.step == 0

    def test_agent_sample_completed(self):
        event = AgentSampleCompleted(
            timestamp=1000.0, step=0, sample_index=0,
            output={"key": "val"}, cost_usd=0.001, duration_ms=500,
        )
        assert event.type == "agent_sample_completed"

    def test_agent_sample_red_flagged(self):
        event = AgentSampleRedFlagged(
            timestamp=1000.0, step=0, sample_index=1, reason="not a dict"
        )
        assert event.type == "agent_sample_red_flagged"

    def test_vote_completed(self):
        event = VoteCompleted(
            timestamp=1000.0, step=0, winner={"a": 1},
            total_samples=3, red_flagged=0,
        )
        assert event.type == "vote_completed"

    def test_step_completed(self):
        summary = VotingSummary(strategy="none", total_samples=1, red_flagged=0, winning_votes=1)
        event = StepCompleted(
            timestamp=1000.0, step=0, title="fetch_data",
            output={"data": "x"}, voting_summary=summary,
            cost_usd=0.001, duration_ms=500,
        )
        assert event.type == "step_completed"
        assert event.output == {"data": "x"}

    def test_step_failed(self):
        event = StepFailed(
            timestamp=1000.0, step=2, title="broken",
            error="all samples red-flagged",
        )
        assert event.type == "step_failed"

    def test_task_completed(self):
        event = TaskCompleted(
            timestamp=1000.0,
            result={"status": "completed", "steps": []},
            total_cost_usd=0.05,
            total_duration_ms=15000,
        )
        assert event.type == "task_completed"

    def test_task_failed(self):
        event = TaskFailed(
            timestamp=1000.0, error="step 2 failed", step=2,
        )
        assert event.type == "task_failed"


class TestEventSerialization:
    def test_event_to_dict(self):
        event = StepStarted(timestamp=1000.0, step=0, title="fetch")
        d = event_to_dict(event)
        assert d["type"] == "step_started"
        assert d["step"] == 0
        assert d["title"] == "fetch"
        assert d["timestamp"] == 1000.0

    def test_event_to_json(self):
        event = StepStarted(timestamp=1000.0, step=0, title="fetch")
        d = event_to_dict(event)
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["type"] == "step_started"

    def test_nested_event_to_dict(self):
        """Events with nested dataclasses should serialize fully."""
        summary = VotingSummary(strategy="majority", total_samples=3, red_flagged=0, winning_votes=2)
        event = StepCompleted(
            timestamp=1000.0, step=0, title="t",
            output={"k": "v"}, voting_summary=summary,
            cost_usd=0.01, duration_ms=100,
        )
        d = event_to_dict(event)
        assert d["voting_summary"]["strategy"] == "majority"


class TestEventBus:
    async def test_emit_and_subscribe(self):
        bus = EventBus()
        event = StepStarted(timestamp=1000.0, step=0, title="fetch")

        received = []

        async def consumer():
            async for e in bus.subscribe():
                received.append(e)
                break  # stop after first event

        task = asyncio.create_task(consumer())
        await bus.emit(event)
        await asyncio.wait_for(task, timeout=1.0)
        assert len(received) == 1
        assert received[0].step == 0

    async def test_multiple_subscribers(self):
        bus = EventBus()
        event = StepStarted(timestamp=1000.0, step=0, title="fetch")

        received_1 = []
        received_2 = []

        async def consumer(target_list):
            async for e in bus.subscribe():
                target_list.append(e)
                break

        t1 = asyncio.create_task(consumer(received_1))
        t2 = asyncio.create_task(consumer(received_2))
        await bus.emit(event)
        await asyncio.wait_for(asyncio.gather(t1, t2), timeout=1.0)
        assert len(received_1) == 1
        assert len(received_2) == 1

    async def test_multiple_events(self):
        bus = EventBus()
        events = [
            StepStarted(timestamp=1000.0, step=0, title="a"),
            StepStarted(timestamp=1001.0, step=1, title="b"),
        ]

        received = []

        async def consumer():
            async for e in bus.subscribe():
                received.append(e)
                if len(received) == 2:
                    break

        task = asyncio.create_task(consumer())
        for e in events:
            await bus.emit(e)
        await asyncio.wait_for(task, timeout=1.0)
        assert len(received) == 2
        assert received[0].title == "a"
        assert received[1].title == "b"

    async def test_shutdown(self):
        """After shutdown, subscribers should stop iterating."""
        bus = EventBus()
        received = []

        async def consumer():
            async for e in bus.subscribe():
                received.append(e)

        task = asyncio.create_task(consumer())
        await bus.emit(StepStarted(timestamp=1000.0, step=0, title="x"))
        await asyncio.sleep(0.05)
        await bus.shutdown()
        await asyncio.wait_for(task, timeout=1.0)
        assert len(received) == 1
