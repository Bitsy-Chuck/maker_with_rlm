import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time
from maker.core.orchestrator import Orchestrator
from maker.core.events import (
    TaskSubmitted, PlanCreated, ValidationPassed, ValidationFailed,
    StepStarted, StepCompleted, TaskCompleted, TaskFailed,
)
from maker.core.models import TaskConfig, Plan, PlanStep, VotingSummary
from maker.tools.registry import ToolRegistry


def make_valid_plan():
    steps = [
        PlanStep(
            step=0, task_type="action_step", title="fetch",
            task_description="Fetch data", primary_tools=["Read"],
            fallback_tools=[], primary_tool_instructions="",
            fallback_tool_instructions="", input_variables=[],
            output_variable="step_0_output",
            output_schema="{data: string}",
            next_step_sequence_number=-1,
        )
    ]
    return Plan(reasoning="test", steps=steps)


def make_config():
    return TaskConfig(instruction="test task", max_planner_retries=2)


class TestOrchestrator:
    async def test_full_pipeline_success(self):
        """Orchestrator should drive: plan → validate → execute → complete."""
        config = make_config()
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")

        orchestrator = Orchestrator(config=config, registry=registry)

        # Mock planner to return a valid plan
        plan = make_valid_plan()

        async def mock_planner_process(event):
            if isinstance(event, TaskSubmitted):
                yield PlanCreated(timestamp=time.time(), plan=plan)

        async def mock_validator_process(event):
            if isinstance(event, PlanCreated):
                yield ValidationPassed(timestamp=time.time(), checks_passed=10)

        async def mock_executor_process(event):
            if isinstance(event, ValidationPassed):
                summary = VotingSummary(strategy="none", total_samples=1, red_flagged=0, winning_votes=1)
                yield StepStarted(timestamp=time.time(), step=0, title="fetch")
                yield StepCompleted(
                    timestamp=time.time(), step=0, title="fetch",
                    output={"data": "result"}, voting_summary=summary,
                    cost_usd=0.01, duration_ms=500,
                )
                yield TaskCompleted(
                    timestamp=time.time(),
                    result={"status": "completed", "steps": []},
                    total_cost_usd=0.01, total_duration_ms=500,
                )

        orchestrator._planner.process = mock_planner_process
        orchestrator._validator.process = mock_validator_process
        orchestrator._executor.process = mock_executor_process

        events = []
        async for event in orchestrator.run():
            events.append(event)

        event_types = [type(e).__name__ for e in events]
        assert "TaskSubmitted" in event_types
        assert "PlanCreated" in event_types
        assert "ValidationPassed" in event_types
        assert "TaskCompleted" in event_types

    async def test_replanning_on_validation_failure(self):
        """If validation fails, orchestrator should retry planner."""
        config = make_config()
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")

        orchestrator = Orchestrator(config=config, registry=registry)

        planner_call_count = 0

        async def mock_planner_process(event):
            nonlocal planner_call_count
            if isinstance(event, TaskSubmitted):
                planner_call_count += 1
                yield PlanCreated(timestamp=time.time(), plan=make_valid_plan())

        validator_call_count = 0

        async def mock_validator_process(event):
            nonlocal validator_call_count
            if isinstance(event, PlanCreated):
                validator_call_count += 1
                if validator_call_count == 1:
                    yield ValidationFailed(
                        timestamp=time.time(),
                        errors=[{"check": "test", "message": "bad plan"}],
                    )
                else:
                    yield ValidationPassed(timestamp=time.time(), checks_passed=10)

        async def mock_executor_process(event):
            if isinstance(event, ValidationPassed):
                yield TaskCompleted(
                    timestamp=time.time(),
                    result={"status": "completed", "steps": []},
                    total_cost_usd=0.0, total_duration_ms=0,
                )

        orchestrator._planner.process = mock_planner_process
        orchestrator._validator.process = mock_validator_process
        orchestrator._executor.process = mock_executor_process

        events = [e async for e in orchestrator.run()]
        assert planner_call_count == 2
        assert validator_call_count == 2

    async def test_validation_errors_fed_back_to_planner(self):
        """Orchestrator should pass validation errors to planner for retry."""
        config = make_config()
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")

        orchestrator = Orchestrator(config=config, registry=registry)

        feedback_received = []

        original_set = orchestrator._planner.set_validation_feedback

        def tracking_set(errors):
            feedback_received.append(errors)
            original_set(errors)

        orchestrator._planner.set_validation_feedback = tracking_set

        async def mock_planner_process(event):
            if isinstance(event, TaskSubmitted):
                yield PlanCreated(timestamp=time.time(), plan=make_valid_plan())

        call_count = 0

        async def mock_validator_process(event):
            nonlocal call_count
            if isinstance(event, PlanCreated):
                call_count += 1
                if call_count == 1:
                    yield ValidationFailed(
                        timestamp=time.time(),
                        errors=[{"check": "reachability", "message": "Orphan steps: [4, 5]"}],
                    )
                else:
                    yield ValidationPassed(timestamp=time.time(), checks_passed=10)

        async def mock_executor_process(event):
            if isinstance(event, ValidationPassed):
                yield TaskCompleted(
                    timestamp=time.time(),
                    result={"status": "completed", "steps": []},
                    total_cost_usd=0.0, total_duration_ms=0,
                )

        orchestrator._planner.process = mock_planner_process
        orchestrator._validator.process = mock_validator_process
        orchestrator._executor.process = mock_executor_process

        _ = [e async for e in orchestrator.run()]

        assert len(feedback_received) == 1
        assert feedback_received[0][0]["message"] == "Orphan steps: [4, 5]"

    async def test_max_planner_retries_exceeded(self):
        """If planner fails max_planner_retries times, task should fail."""
        config = TaskConfig(instruction="test", max_planner_retries=2)
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")

        orchestrator = Orchestrator(config=config, registry=registry)

        async def mock_planner_process(event):
            if isinstance(event, TaskSubmitted):
                yield PlanCreated(timestamp=time.time(), plan=make_valid_plan())

        async def mock_validator_process(event):
            if isinstance(event, PlanCreated):
                yield ValidationFailed(
                    timestamp=time.time(),
                    errors=[{"check": "test", "message": "always fails"}],
                )

        orchestrator._planner.process = mock_planner_process
        orchestrator._validator.process = mock_validator_process

        events = [e async for e in orchestrator.run()]
        task_failed = [e for e in events if isinstance(e, TaskFailed)]
        assert len(task_failed) == 1

    async def test_all_events_emitted_to_bus(self):
        """Every event from every module should appear in the output stream."""
        config = make_config()
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")

        orchestrator = Orchestrator(config=config, registry=registry)

        async def mock_planner_process(event):
            if isinstance(event, TaskSubmitted):
                yield PlanCreated(timestamp=time.time(), plan=make_valid_plan())

        async def mock_validator_process(event):
            if isinstance(event, PlanCreated):
                yield ValidationPassed(timestamp=time.time(), checks_passed=10)

        async def mock_executor_process(event):
            if isinstance(event, ValidationPassed):
                yield TaskCompleted(
                    timestamp=time.time(),
                    result={"status": "completed", "steps": []},
                    total_cost_usd=0.0, total_duration_ms=0,
                )

        orchestrator._planner.process = mock_planner_process
        orchestrator._validator.process = mock_validator_process
        orchestrator._executor.process = mock_executor_process

        events = [e async for e in orchestrator.run()]
        # Should have at least: TaskSubmitted, PlanCreated, ValidationPassed, TaskCompleted
        assert len(events) >= 4
