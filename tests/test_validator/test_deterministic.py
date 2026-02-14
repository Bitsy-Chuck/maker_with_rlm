import pytest
from maker.validator.deterministic import (
    check_required_fields,
    check_step_numbering,
    check_task_type_valid,
    check_reasoning_present,
    check_tools_mutually_exclusive,
    check_tools_are_valid,
    check_conditional_step_no_tools,
    check_conditional_step_no_instructions,
    check_next_step_valid,
    check_conditional_returns_minus_2,
    check_final_step_returns_minus_1,
    check_no_orphan_steps,
    check_output_schema_exists,
    run_all_deterministic_checks,
    CheckResult,
)
from maker.core.models import Plan, PlanStep
from maker.tools.registry import ToolRegistry


def make_step(**overrides):
    """Create a valid action step with overrides."""
    defaults = {
        "step": 0,
        "task_type": "action_step",
        "title": "test_step",
        "task_description": "Do something",
        "primary_tools": ["Read"],
        "fallback_tools": [],
        "primary_tool_instructions": "Use Read",
        "fallback_tool_instructions": "",
        "input_variables": [],
        "output_variable": "step_0_output",
        "output_schema": "{result: string}",
        "next_step_sequence_number": -1,
    }
    defaults.update(overrides)
    return PlanStep(**defaults)


def make_plan(steps=None, reasoning="test reasoning"):
    if steps is None:
        steps = [make_step()]
    return Plan(reasoning=reasoning, steps=steps)


def make_registry():
    registry = ToolRegistry()
    registry.register_builtin("Read", "Read files")
    registry.register_builtin("Write", "Write files")
    registry.register_builtin("Bash", "Run commands")
    return registry


class TestRequiredFields:
    def test_valid_step_passes(self):
        plan = make_plan()
        result = check_required_fields(plan)
        assert result.passed

    def test_missing_output_schema(self):
        step = make_step(output_schema="")
        # output_schema exists but is empty — check_output_schema_exists handles this
        # check_required_fields only checks field presence on the dataclass
        plan = make_plan([step])
        result = check_required_fields(plan)
        assert result.passed  # field exists, just empty


class TestStepNumbering:
    def test_sequential_steps_pass(self):
        steps = [make_step(step=0, next_step_sequence_number=1),
                 make_step(step=1, next_step_sequence_number=-1)]
        result = check_step_numbering(make_plan(steps))
        assert result.passed

    def test_gap_in_numbering_fails(self):
        steps = [make_step(step=0, next_step_sequence_number=2),
                 make_step(step=2, next_step_sequence_number=-1)]
        result = check_step_numbering(make_plan(steps))
        assert not result.passed
        assert "gap" in result.message.lower() or "sequential" in result.message.lower()

    def test_not_starting_at_zero_fails(self):
        steps = [make_step(step=1, next_step_sequence_number=-1)]
        result = check_step_numbering(make_plan(steps))
        assert not result.passed

    def test_single_step_passes(self):
        result = check_step_numbering(make_plan())
        assert result.passed


class TestTaskTypeValid:
    def test_action_step_passes(self):
        result = check_task_type_valid(make_plan())
        assert result.passed

    def test_conditional_step_passes(self):
        step = make_step(task_type="conditional_step", primary_tools=[],
                        fallback_tools=[], primary_tool_instructions="",
                        fallback_tool_instructions="", next_step_sequence_number=-2)
        result = check_task_type_valid(make_plan([step]))
        assert result.passed

    def test_invalid_type_fails(self):
        step = make_step(task_type="invalid_type")
        result = check_task_type_valid(make_plan([step]))
        assert not result.passed


class TestReasoningPresent:
    def test_reasoning_present(self):
        result = check_reasoning_present(make_plan())
        assert result.passed

    def test_empty_reasoning_fails(self):
        result = check_reasoning_present(make_plan(reasoning=""))
        assert not result.passed

    def test_whitespace_reasoning_fails(self):
        result = check_reasoning_present(make_plan(reasoning="   "))
        assert not result.passed


class TestToolsMutuallyExclusive:
    def test_no_overlap_passes(self):
        step = make_step(primary_tools=["Read"], fallback_tools=["Write"])
        result = check_tools_mutually_exclusive(make_plan([step]))
        assert result.passed

    def test_overlap_fails(self):
        step = make_step(primary_tools=["Read", "Write"], fallback_tools=["Read"])
        result = check_tools_mutually_exclusive(make_plan([step]))
        assert not result.passed

    def test_both_empty_passes(self):
        step = make_step(primary_tools=[], fallback_tools=[])
        result = check_tools_mutually_exclusive(make_plan([step]))
        assert result.passed


class TestToolsAreValid:
    def test_valid_tools_pass(self):
        registry = make_registry()
        step = make_step(primary_tools=["Read"], fallback_tools=["Write"])
        result = check_tools_are_valid(make_plan([step]), registry)
        assert result.passed

    def test_invalid_tool_fails(self):
        registry = make_registry()
        step = make_step(primary_tools=["FakeTool"])
        result = check_tools_are_valid(make_plan([step]), registry)
        assert not result.passed
        assert "FakeTool" in result.message

    def test_empty_tools_pass(self):
        registry = make_registry()
        step = make_step(primary_tools=[], fallback_tools=[])
        result = check_tools_are_valid(make_plan([step]), registry)
        assert result.passed


class TestConditionalStepNoTools:
    def test_conditional_with_empty_tools_passes(self):
        step = make_step(task_type="conditional_step", primary_tools=[],
                        fallback_tools=[], primary_tool_instructions="",
                        fallback_tool_instructions="", next_step_sequence_number=-2)
        result = check_conditional_step_no_tools(make_plan([step]))
        assert result.passed

    def test_conditional_with_primary_tools_fails(self):
        step = make_step(task_type="conditional_step", primary_tools=["Read"],
                        fallback_tools=[], primary_tool_instructions="",
                        fallback_tool_instructions="", next_step_sequence_number=-2)
        result = check_conditional_step_no_tools(make_plan([step]))
        assert not result.passed

    def test_action_step_with_tools_passes(self):
        """Action steps CAN have tools — this check only applies to conditional."""
        step = make_step(primary_tools=["Read"])
        result = check_conditional_step_no_tools(make_plan([step]))
        assert result.passed


class TestConditionalStepNoInstructions:
    def test_conditional_with_empty_instructions_passes(self):
        step = make_step(task_type="conditional_step", primary_tools=[],
                        fallback_tools=[], primary_tool_instructions="",
                        fallback_tool_instructions="", next_step_sequence_number=-2)
        result = check_conditional_step_no_instructions(make_plan([step]))
        assert result.passed

    def test_conditional_with_instructions_fails(self):
        step = make_step(task_type="conditional_step", primary_tools=[],
                        fallback_tools=[],
                        primary_tool_instructions="Use something",
                        fallback_tool_instructions="",
                        next_step_sequence_number=-2)
        result = check_conditional_step_no_instructions(make_plan([step]))
        assert not result.passed


class TestNextStepValid:
    def test_valid_next_step(self):
        steps = [make_step(step=0, next_step_sequence_number=1),
                 make_step(step=1, next_step_sequence_number=-1)]
        result = check_next_step_valid(make_plan(steps))
        assert result.passed

    def test_minus_1_is_valid(self):
        result = check_next_step_valid(make_plan())
        assert result.passed

    def test_minus_2_is_valid(self):
        step = make_step(next_step_sequence_number=-2, task_type="conditional_step",
                        primary_tools=[], fallback_tools=[],
                        primary_tool_instructions="", fallback_tool_instructions="")
        result = check_next_step_valid(make_plan([step]))
        assert result.passed

    def test_nonexistent_step_fails(self):
        step = make_step(next_step_sequence_number=5)
        result = check_next_step_valid(make_plan([step]))
        assert not result.passed


class TestConditionalReturnsMinus2:
    def test_conditional_with_minus_2_passes(self):
        step = make_step(task_type="conditional_step", primary_tools=[],
                        fallback_tools=[], primary_tool_instructions="",
                        fallback_tool_instructions="", next_step_sequence_number=-2)
        result = check_conditional_returns_minus_2(make_plan([step]))
        assert result.passed

    def test_conditional_with_other_value_fails(self):
        step = make_step(task_type="conditional_step", primary_tools=[],
                        fallback_tools=[], primary_tool_instructions="",
                        fallback_tool_instructions="", next_step_sequence_number=1)
        result = check_conditional_returns_minus_2(make_plan([step]))
        assert not result.passed


class TestFinalStepReturnsMinus1:
    def test_final_step_with_minus_1_passes(self):
        result = check_final_step_returns_minus_1(make_plan())
        assert result.passed

    def test_final_step_without_minus_1_fails(self):
        step = make_step(next_step_sequence_number=1)
        result = check_final_step_returns_minus_1(make_plan([step]))
        assert not result.passed

    def test_conditional_final_step_ok(self):
        """A conditional step can be the last step (routes dynamically)."""
        steps = [
            make_step(step=0, next_step_sequence_number=1),
            make_step(step=1, task_type="conditional_step", primary_tools=[],
                     fallback_tools=[], primary_tool_instructions="",
                     fallback_tool_instructions="", next_step_sequence_number=-2),
        ]
        result = check_final_step_returns_minus_1(make_plan(steps))
        assert result.passed  # conditional steps exempt


class TestNoOrphanSteps:
    def test_all_reachable_passes(self):
        steps = [make_step(step=0, next_step_sequence_number=1),
                 make_step(step=1, next_step_sequence_number=-1)]
        result = check_no_orphan_steps(make_plan(steps))
        assert result.passed

    def test_orphan_step_fails(self):
        steps = [
            make_step(step=0, next_step_sequence_number=-1),  # ends here
            make_step(step=1, next_step_sequence_number=-1),  # orphan
        ]
        result = check_no_orphan_steps(make_plan(steps))
        assert not result.passed

    def test_single_step_passes(self):
        result = check_no_orphan_steps(make_plan())
        assert result.passed


class TestOutputSchemaExists:
    def test_non_empty_schema_passes(self):
        result = check_output_schema_exists(make_plan())
        assert result.passed

    def test_empty_schema_fails(self):
        step = make_step(output_schema="")
        result = check_output_schema_exists(make_plan([step]))
        assert not result.passed

    def test_whitespace_schema_fails(self):
        step = make_step(output_schema="   ")
        result = check_output_schema_exists(make_plan([step]))
        assert not result.passed


class TestRunAllChecks:
    def test_valid_plan_passes_all(self):
        registry = make_registry()
        plan = make_plan()
        results = run_all_deterministic_checks(plan, registry)
        assert all(r.passed for r in results)

    def test_invalid_plan_has_failures(self):
        registry = make_registry()
        step = make_step(primary_tools=["FakeTool"], task_type="invalid")
        plan = make_plan([step])
        results = run_all_deterministic_checks(plan, registry)
        failed = [r for r in results if not r.passed]
        assert len(failed) >= 2  # at least task_type and tools_are_valid


class TestCheckResult:
    def test_passed_result(self):
        result = CheckResult(name="test", passed=True, message="OK")
        assert result.passed
        assert result.name == "test"

    def test_failed_result(self):
        result = CheckResult(name="test", passed=False, message="Bad")
        assert not result.passed
