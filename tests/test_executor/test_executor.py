import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from maker.executor.executor import ExecutorModule
from maker.core.events import (
    ValidationPassed, StepStarted, StepCompleted, StepFailed,
    TaskCompleted, TaskFailed, PlanCreated,
)
from maker.core.models import (
    Plan, PlanStep, TaskConfig, VoteResult, VotingSummary,
)
from maker.tools.registry import ToolRegistry
import time


def make_step(step_num, next_step=-1, task_type="action_step", **overrides):
    defaults = {
        "step": step_num,
        "task_type": task_type,
        "title": f"step_{step_num}",
        "task_description": f"Do step {step_num}",
        "primary_tools": ["Read"],
        "fallback_tools": [],
        "primary_tool_instructions": "",
        "fallback_tool_instructions": "",
        "input_variables": [f"step_{step_num-1}_output.data"] if step_num > 0 else [],
        "output_variable": f"step_{step_num}_output",
        "output_schema": "{data: string}",
        "next_step_sequence_number": next_step,
    }
    defaults.update(overrides)
    return PlanStep(**defaults)


def make_linear_plan(n_steps):
    steps = []
    for i in range(n_steps):
        next_step = i + 1 if i < n_steps - 1 else -1
        steps.append(make_step(i, next_step=next_step))
    return Plan(reasoning="test", steps=steps)


def make_vote_result(output=None):
    return VoteResult(
        winner=output or {"data": "result"},
        canonical_hash="abc",
        total_samples=1,
        red_flagged=0,
        vote_counts={"abc": 1},
    )


def make_config():
    return TaskConfig(instruction="test")


class TestExecutorModule:
    async def test_linear_plan_three_steps(self):
        """Execute a simple 3-step linear plan."""
        plan = make_linear_plan(3)
        config = make_config()

        executor = ExecutorModule(config=config, plan=plan)

        # Mock voter to always succeed
        mock_voter = AsyncMock()
        mock_voter.vote = AsyncMock(return_value=make_vote_result())
        executor._voter = mock_voter

        event = ValidationPassed(timestamp=time.time(), checks_passed=10)
        events = [e async for e in executor.process(event)]

        # Should emit: 3x (StepStarted + StepCompleted) + TaskCompleted
        step_started = [e for e in events if isinstance(e, StepStarted)]
        step_completed = [e for e in events if isinstance(e, StepCompleted)]
        task_completed = [e for e in events if isinstance(e, TaskCompleted)]

        assert len(step_started) == 3
        assert len(step_completed) == 3
        assert len(task_completed) == 1

    async def test_step_outputs_passed_to_next(self):
        """Each step should receive previous step outputs as context."""
        plan = make_linear_plan(2)
        config = make_config()

        executor = ExecutorModule(config=config, plan=plan)

        contexts_received = []

        async def mock_vote(step, context, config):
            contexts_received.append(context)
            return make_vote_result({"data": f"result_{step.step}"})

        mock_voter = AsyncMock()
        mock_voter.vote = mock_vote
        executor._voter = mock_voter

        event = ValidationPassed(timestamp=time.time(), checks_passed=10)
        _ = [e async for e in executor.process(event)]

        # Step 0: no context
        assert contexts_received[0] == ""
        # Step 1: should have step_0_output
        assert "step_0_output" in contexts_received[1]

    async def test_conditional_step_routing(self):
        """Conditional step should route to the step specified in output."""
        steps = [
            make_step(0, next_step=1),
            make_step(1, next_step=-2, task_type="conditional_step",
                     primary_tools=[], fallback_tools=[],
                     input_variables=["step_0_output.data"]),
            make_step(2, next_step=-1, title="branch_a", input_variables=["step_1_output.data"]),
            make_step(3, next_step=-1, title="branch_b", input_variables=["step_1_output.data"]),
        ]
        plan = Plan(reasoning="conditional", steps=steps)
        config = make_config()

        executor = ExecutorModule(config=config, plan=plan)

        call_count = 0

        async def mock_vote(step, context, config):
            nonlocal call_count
            call_count += 1
            if step.task_type == "conditional_step":
                return make_vote_result({"next_step": 3, "reason": "go to B"})
            return make_vote_result({"data": f"result_{step.step}"})

        mock_voter = AsyncMock()
        mock_voter.vote = mock_vote
        executor._voter = mock_voter

        event = ValidationPassed(timestamp=time.time(), checks_passed=10)
        events = [e async for e in executor.process(event)]

        completed_titles = [e.title for e in events if isinstance(e, StepCompleted)]
        # Should execute: step_0, step_1 (conditional), step_3 (branch_b)
        # Should NOT execute step_2 (branch_a)
        assert "branch_b" in completed_titles
        assert "branch_a" not in completed_titles

    async def test_step_failure_emits_task_failed(self):
        """If a step fails, TaskFailed should be emitted."""
        plan = make_linear_plan(2)
        config = make_config()

        executor = ExecutorModule(config=config, plan=plan)

        mock_voter = AsyncMock()
        mock_voter.vote = AsyncMock(side_effect=RuntimeError("all samples red-flagged"))
        executor._voter = mock_voter

        event = ValidationPassed(timestamp=time.time(), checks_passed=10)
        events = [e async for e in executor.process(event)]

        step_failed = [e for e in events if isinstance(e, StepFailed)]
        task_failed = [e for e in events if isinstance(e, TaskFailed)]

        assert len(step_failed) == 1
        assert len(task_failed) == 1
        assert step_failed[0].step == 0

    async def test_conditional_missing_next_step_fails(self):
        """Conditional step without next_step in output should fail."""
        steps = [
            make_step(0, next_step=1),
            make_step(1, next_step=-2, task_type="conditional_step",
                     primary_tools=[], fallback_tools=[]),
        ]
        plan = Plan(reasoning="test", steps=steps)
        config = make_config()

        executor = ExecutorModule(config=config, plan=plan)

        async def mock_vote(step, context, config):
            if step.task_type == "conditional_step":
                return make_vote_result({"reason": "missing next_step field"})
            return make_vote_result()

        mock_voter = AsyncMock()
        mock_voter.vote = mock_vote
        executor._voter = mock_voter

        event = ValidationPassed(timestamp=time.time(), checks_passed=10)
        events = [e async for e in executor.process(event)]

        step_failed = [e for e in events if isinstance(e, StepFailed)]
        assert len(step_failed) >= 1

    async def test_ignores_non_validation_passed_events(self):
        plan = make_linear_plan(1)
        config = make_config()
        executor = ExecutorModule(config=config, plan=plan)

        event = StepStarted(timestamp=time.time(), step=0, title="x")
        events = [e async for e in executor.process(event)]
        assert events == []

    async def test_task_completed_has_full_result(self):
        plan = make_linear_plan(1)
        config = make_config()

        executor = ExecutorModule(config=config, plan=plan)
        mock_voter = AsyncMock()
        mock_voter.vote = AsyncMock(return_value=make_vote_result({"answer": 42}))
        executor._voter = mock_voter

        event = ValidationPassed(timestamp=time.time(), checks_passed=10)
        events = [e async for e in executor.process(event)]

        task_completed = [e for e in events if isinstance(e, TaskCompleted)]
        assert len(task_completed) == 1
        assert task_completed[0].result["status"] == "completed"
        assert len(task_completed[0].result["steps"]) == 1
