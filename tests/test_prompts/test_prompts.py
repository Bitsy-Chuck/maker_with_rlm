import pytest
from maker.prompts import load_prompt


class TestLoadPrompt:
    def test_load_existing_prompt(self):
        prompt = load_prompt("planner_system")
        assert isinstance(prompt, str)
        assert len(prompt) > 100  # planner prompt is substantial

    def test_load_with_kwargs(self):
        prompt = load_prompt("planner_user", instruction="Do X", tools_list="Read, Write")
        assert "Do X" in prompt
        assert "Read, Write" in prompt

    def test_load_nonexistent_raises(self):
        with pytest.raises(KeyError):
            load_prompt("nonexistent_prompt")

    def test_yaml_fixer_prompt(self):
        prompt = load_prompt("yaml_fixer", raw_yaml="bad: [", error="expected ]")
        assert "bad: [" in prompt
        assert "expected ]" in prompt

    def test_executor_step_prompt(self):
        prompt = load_prompt(
            "executor_step",
            task_description="Fetch data",
            context="step_0_output:\n  key: value",
            output_schema="{data: string}",
        )
        assert "Fetch data" in prompt
        assert "step_0_output" in prompt

    def test_all_quality_prompts_load(self):
        quality_prompts = [
            "quality_single_purpose",
            "quality_self_contained",
            "quality_max_k_tools",
            "quality_non_overlapping",
            "quality_maximally_decomposed",
            "quality_appropriately_merged",
        ]
        for name in quality_prompts:
            prompt = load_prompt(name)
            assert isinstance(prompt, str)
            assert len(prompt) > 20

    def test_planner_system_contains_key_sections(self):
        """Planner prompt should contain adapted SPEC content."""
        prompt = load_prompt("planner_system")
        assert "AskUserQuestion" in prompt  # adapted from human_input_tool
        assert "ask_duckie" not in prompt   # dropped per design
        assert "Maximal Task Decomposition" in prompt
        assert "output_schema" in prompt

    def test_planner_system_no_human_input_tool(self):
        """Planner prompt should NOT reference human_input_tool (replaced)."""
        prompt = load_prompt("planner_system")
        assert "human_input_tool" not in prompt
