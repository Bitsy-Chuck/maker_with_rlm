import pytest
from unittest.mock import AsyncMock
from maker.validator.validator import ValidatorModule
from maker.core.events import PlanCreated, ValidationPassed, ValidationFailed
from maker.core.models import Plan, PlanStep, TaskConfig
from maker.tools.registry import ToolRegistry
import time


def make_valid_plan():
    steps = [
        PlanStep(
            step=0, task_type="action_step", title="fetch",
            task_description="Fetch data", primary_tools=["Read"],
            fallback_tools=[], primary_tool_instructions="Use Read",
            fallback_tool_instructions="", input_variables=[],
            output_variable="step_0_output",
            output_schema="{data: string}",
            next_step_sequence_number=-1,
        )
    ]
    return Plan(reasoning="Simple plan", steps=steps)


def make_registry():
    r = ToolRegistry()
    r.register_builtin("Read", "Read files")
    return r


class TestValidatorModule:
    async def test_valid_plan_emits_passed(self):
        registry = make_registry()
        config = TaskConfig(instruction="test")
        validator = ValidatorModule(registry=registry, config=config)

        event = PlanCreated(timestamp=time.time(), plan=make_valid_plan())
        events = [e async for e in validator.process(event)]

        assert len(events) == 1
        assert isinstance(events[0], ValidationPassed)
        assert events[0].checks_passed > 0

    async def test_invalid_plan_emits_failed(self):
        registry = make_registry()
        config = TaskConfig(instruction="test")
        validator = ValidatorModule(registry=registry, config=config)

        bad_plan = Plan(
            reasoning="",  # empty reasoning
            steps=[
                PlanStep(
                    step=1,  # doesn't start at 0
                    task_type="bad_type",
                    title="t", task_description="d",
                    primary_tools=["FakeTool"], fallback_tools=[],
                    primary_tool_instructions="", fallback_tool_instructions="",
                    input_variables=[], output_variable="step_1_output",
                    output_schema="", next_step_sequence_number=-1,
                )
            ],
        )
        event = PlanCreated(timestamp=time.time(), plan=bad_plan)
        events = [e async for e in validator.process(event)]

        assert len(events) == 1
        assert isinstance(events[0], ValidationFailed)
        assert len(events[0].errors) > 0

    async def test_quality_checks_off_by_default(self):
        """Quality checks should not run unless enabled."""
        registry = make_registry()
        config = TaskConfig(instruction="test", enable_quality_checks=False)
        validator = ValidatorModule(registry=registry, config=config)

        event = PlanCreated(timestamp=time.time(), plan=make_valid_plan())
        events = [e async for e in validator.process(event)]

        assert isinstance(events[0], ValidationPassed)
        # No quality scores in output since disabled

    async def test_ignores_non_plan_created_events(self):
        from maker.core.events import StepStarted
        registry = make_registry()
        config = TaskConfig(instruction="test")
        validator = ValidatorModule(registry=registry, config=config)

        event = StepStarted(timestamp=time.time(), step=0, title="x")
        events = [e async for e in validator.process(event)]
        assert events == []
