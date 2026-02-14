import pytest
from maker.planner.parser import parse_plan
from maker.core.models import Plan, PlanStep


class TestParsePlan:
    def test_basic_plan(self):
        raw = {
            "reasoning": "Simple plan to fetch data",
            "plan": [
                {
                    "step": 0,
                    "task_type": "action_step",
                    "title": "fetch_data",
                    "task_description": "Fetch data from API",
                    "primary_tools": ["WebFetch"],
                    "fallback_tools": [],
                    "primary_tool_instructions": "Use WebFetch",
                    "fallback_tool_instructions": "",
                    "input_variables": [],
                    "output_variable": "step_0_output",
                    "output_schema": "{data: string}",
                    "next_step_sequence_number": -1,
                }
            ],
        }
        plan = parse_plan(raw)
        assert isinstance(plan, Plan)
        assert plan.reasoning == "Simple plan to fetch data"
        assert len(plan.steps) == 1
        assert plan.steps[0].step == 0
        assert plan.steps[0].title == "fetch_data"

    def test_plan_key_maps_to_steps(self):
        """YAML uses 'plan' key but Plan dataclass uses 'steps'."""
        raw = {
            "reasoning": "test",
            "plan": [
                {
                    "step": 0,
                    "task_type": "action_step",
                    "title": "t",
                    "task_description": "d",
                    "primary_tools": [],
                    "fallback_tools": [],
                    "primary_tool_instructions": "",
                    "fallback_tool_instructions": "",
                    "input_variables": [],
                    "output_variable": "step_0_output",
                    "output_schema": "{}",
                    "next_step_sequence_number": -1,
                }
            ],
        }
        plan = parse_plan(raw)
        assert hasattr(plan, "steps")
        assert len(plan.steps) == 1

    def test_steps_key_also_works(self):
        """If YAML already uses 'steps' key, that should also parse."""
        raw = {
            "reasoning": "test",
            "steps": [
                {
                    "step": 0,
                    "task_type": "action_step",
                    "title": "t",
                    "task_description": "d",
                    "primary_tools": [],
                    "fallback_tools": [],
                    "primary_tool_instructions": "",
                    "fallback_tool_instructions": "",
                    "input_variables": [],
                    "output_variable": "step_0_output",
                    "output_schema": "{}",
                    "next_step_sequence_number": -1,
                }
            ],
        }
        plan = parse_plan(raw)
        assert len(plan.steps) == 1

    def test_multi_step_plan(self):
        raw = {
            "reasoning": "multi-step",
            "plan": [
                {
                    "step": 0,
                    "task_type": "action_step",
                    "title": "step_one",
                    "task_description": "First step",
                    "primary_tools": ["Read"],
                    "fallback_tools": [],
                    "primary_tool_instructions": "",
                    "fallback_tool_instructions": "",
                    "input_variables": [],
                    "output_variable": "step_0_output",
                    "output_schema": "{file: string}",
                    "next_step_sequence_number": 1,
                },
                {
                    "step": 1,
                    "task_type": "action_step",
                    "title": "step_two",
                    "task_description": "Second step",
                    "primary_tools": ["Write"],
                    "fallback_tools": [],
                    "primary_tool_instructions": "",
                    "fallback_tool_instructions": "",
                    "input_variables": ["step_0_output.file"],
                    "output_variable": "step_1_output",
                    "output_schema": "{result: string}",
                    "next_step_sequence_number": -1,
                },
            ],
        }
        plan = parse_plan(raw)
        assert len(plan.steps) == 2
        assert plan.steps[0].next_step_sequence_number == 1
        assert plan.steps[1].next_step_sequence_number == -1

    def test_conditional_step(self):
        raw = {
            "reasoning": "conditional",
            "plan": [
                {
                    "step": 0,
                    "task_type": "action_step",
                    "title": "get_status",
                    "task_description": "Get status",
                    "primary_tools": ["Read"],
                    "fallback_tools": [],
                    "primary_tool_instructions": "",
                    "fallback_tool_instructions": "",
                    "input_variables": [],
                    "output_variable": "step_0_output",
                    "output_schema": "{status: string}",
                    "next_step_sequence_number": 1,
                },
                {
                    "step": 1,
                    "task_type": "conditional_step",
                    "title": "decide_next",
                    "task_description": "If critical go to 2 else end",
                    "primary_tools": [],
                    "fallback_tools": [],
                    "primary_tool_instructions": "",
                    "fallback_tool_instructions": "",
                    "input_variables": ["step_0_output.status"],
                    "output_variable": "step_1_output",
                    "output_schema": "{next_step: int, reason: string}",
                    "next_step_sequence_number": -2,
                },
            ],
        }
        plan = parse_plan(raw)
        assert plan.steps[1].task_type == "conditional_step"
        assert plan.steps[1].next_step_sequence_number == -2

    def test_missing_reasoning_raises(self):
        raw = {"plan": []}
        with pytest.raises(ValueError, match="reasoning"):
            parse_plan(raw)

    def test_missing_plan_and_steps_raises(self):
        raw = {"reasoning": "test"}
        with pytest.raises(ValueError, match="plan.*steps"):
            parse_plan(raw)

    def test_not_a_dict_raises(self):
        with pytest.raises(ValueError):
            parse_plan(["a", "b"])

    def test_plan_not_a_list_raises(self):
        raw = {"reasoning": "test", "plan": "not a list"}
        with pytest.raises(ValueError):
            parse_plan(raw)

    def test_missing_required_step_field_raises(self):
        raw = {
            "reasoning": "test",
            "plan": [
                {"step": 0, "task_type": "action_step"}
                # missing many fields
            ],
        }
        with pytest.raises((ValueError, KeyError, TypeError)):
            parse_plan(raw)
