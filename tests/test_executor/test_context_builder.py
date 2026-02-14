import pytest
import yaml
from maker.executor.context_builder import ContextBuilder
from maker.core.models import PlanStep


def make_step(**overrides):
    defaults = {
        "step": 1, "task_type": "action_step", "title": "test",
        "task_description": "Do something with step_0_output.field",
        "primary_tools": ["Read"], "fallback_tools": [],
        "primary_tool_instructions": "", "fallback_tool_instructions": "",
        "input_variables": ["step_0_output.field"],
        "output_variable": "step_1_output",
        "output_schema": "{result: string}",
        "next_step_sequence_number": -1,
    }
    defaults.update(overrides)
    return PlanStep(**defaults)


class TestContextBuilder:
    def test_builds_context_from_step_outputs(self):
        builder = ContextBuilder()
        step_outputs = {
            "step_0_output": {"field": "value", "other": "data"},
        }
        step = make_step(input_variables=["step_0_output.field"])

        context = builder.build(step, step_outputs)
        assert "step_0_output" in context
        assert "field: value" in context
        assert "other: data" in context  # whole output is included

    def test_multiple_step_references(self):
        builder = ContextBuilder()
        step_outputs = {
            "step_0_output": {"user_id": "abc"},
            "step_2_output": {"status": "active"},
        }
        step = make_step(
            input_variables=["step_0_output.user_id", "step_2_output.status"]
        )

        context = builder.build(step, step_outputs)
        assert "step_0_output" in context
        assert "step_2_output" in context
        assert "user_id" in context
        assert "status" in context

    def test_extracts_step_name_from_dotted_path(self):
        """Input variable 'step_0_output.user_id' -> includes step_0_output."""
        builder = ContextBuilder()
        step_outputs = {
            "step_0_output": {"user_id": "abc", "extra": "data"},
        }
        step = make_step(input_variables=["step_0_output.user_id"])

        context = builder.build(step, step_outputs)
        # Full output is included, not just the referenced field
        assert "extra: data" in context

    def test_empty_input_variables(self):
        builder = ContextBuilder()
        step = make_step(input_variables=[], step=0)
        context = builder.build(step, {})
        assert context == ""  # no context needed

    def test_missing_step_output_raises(self):
        """If a referenced step hasn't been executed yet, raise."""
        builder = ContextBuilder()
        step_outputs = {}  # no outputs yet
        step = make_step(input_variables=["step_0_output.field"])

        with pytest.raises(KeyError, match="step_0_output"):
            builder.build(step, step_outputs)

    def test_context_is_valid_yaml(self):
        """Built context should be parseable YAML."""
        builder = ContextBuilder()
        step_outputs = {
            "step_0_output": {"nested": {"key": "value"}, "list": [1, 2, 3]},
        }
        step = make_step(input_variables=["step_0_output.nested"])

        context = builder.build(step, step_outputs)
        parsed = yaml.safe_load(context)
        assert isinstance(parsed, dict)
        assert "step_0_output" in parsed

    def test_deduplicates_step_references(self):
        """Multiple references to same step only includes output once."""
        builder = ContextBuilder()
        step_outputs = {
            "step_0_output": {"a": 1, "b": 2},
        }
        step = make_step(
            input_variables=["step_0_output.a", "step_0_output.b"]
        )

        context = builder.build(step, step_outputs)
        # step_0_output should appear only once as a header
        assert context.count("step_0_output:") == 1
