import pytest
from unittest.mock import AsyncMock, patch
from maker.planner.planner import PlannerModule
from maker.core.events import TaskSubmitted, PlanCreated
from maker.core.models import TaskConfig
from maker.tools.registry import ToolRegistry


def make_task_submitted(instruction="Do something"):
    config = TaskConfig(instruction=instruction)
    return TaskSubmitted(timestamp=1000.0, instruction=instruction, config=config)


def make_valid_yaml_output():
    """Simulate raw YAML that the planner LLM would produce."""
    return """reasoning: >
  Simple plan to read a file.

plan:
  - step: 0
    task_type: action_step
    title: read_file
    task_description: Read the file contents
    primary_tools: [Read]
    fallback_tools: []
    primary_tool_instructions: Use Read tool
    fallback_tool_instructions: ""
    input_variables: []
    output_variable: step_0_output
    output_schema: "{content: string}"
    next_step_sequence_number: -1"""


class TestPlannerModule:
    async def test_emits_plan_created(self):
        """Planner should emit PlanCreated with a valid Plan."""
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")

        planner = PlannerModule(registry=registry)

        planner._call_sdk = AsyncMock(return_value=make_valid_yaml_output())

        event = make_task_submitted("Read a file")
        events = [e async for e in planner.process(event)]

        assert len(events) == 1
        assert isinstance(events[0], PlanCreated)
        assert events[0].plan.reasoning is not None
        assert len(events[0].plan.steps) == 1
        assert events[0].plan.steps[0].title == "read_file"

    async def test_passes_tools_to_prompt(self):
        """Planner should include available tools in the prompt."""
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")
        registry.register_builtin("Write", "Write files")

        planner = PlannerModule(registry=registry)

        prompt_used = None

        async def capture_prompt(prompt, **kwargs):
            nonlocal prompt_used
            prompt_used = prompt
            return make_valid_yaml_output()

        planner._call_sdk = capture_prompt

        event = make_task_submitted("Do something")
        _ = [e async for e in planner.process(event)]

        assert "Read" in prompt_used
        assert "Write" in prompt_used

    async def test_uses_yaml_cleaner(self):
        """Planner should parse output through YAMLCleaner."""
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")

        planner = PlannerModule(registry=registry)

        # Wrap YAML in fences — cleaner should strip them
        fenced_yaml = "```yaml\n" + make_valid_yaml_output() + "\n```"
        planner._call_sdk = AsyncMock(return_value=fenced_yaml)

        events = [e async for e in planner.process(make_task_submitted())]

        assert len(events) == 1
        assert isinstance(events[0], PlanCreated)

    async def test_ignores_non_task_submitted_events(self):
        """Planner should yield nothing for events it doesn't handle."""
        from maker.core.events import StepStarted

        registry = ToolRegistry()
        planner = PlannerModule(registry=registry)

        event = StepStarted(timestamp=1000.0, step=0, title="x")
        events = [e async for e in planner.process(event)]
        assert events == []

    async def test_sdk_error_raises(self):
        """If SDK query fails, planner should propagate the error."""
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")

        planner = PlannerModule(registry=registry)

        async def failing_sdk(*args, **kwargs):
            raise RuntimeError("SDK connection failed")

        planner._call_sdk = failing_sdk

        with pytest.raises(RuntimeError, match="SDK connection failed"):
            _ = [e async for e in planner.process(make_task_submitted())]

    async def test_validation_feedback_included_in_retry_prompt(self):
        """When validation errors are set, planner should include them in the prompt."""
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")

        planner = PlannerModule(registry=registry)

        prompt_used = None

        async def capture_prompt(prompt, **kwargs):
            nonlocal prompt_used
            prompt_used = prompt
            return make_valid_yaml_output()

        planner._call_sdk = capture_prompt
        planner.set_validation_feedback([
            {"check": "reachability", "message": "Orphan steps not reachable from step 0: [4, 5]"},
            {"check": "final_step", "message": "Final step must have next_step_sequence_number=-1"},
        ])

        _ = [e async for e in planner.process(make_task_submitted())]

        assert "Orphan steps not reachable from step 0" in prompt_used
        assert "next_step_sequence_number=-1" in prompt_used
        assert "previous plan failed validation" in prompt_used

    async def test_validation_feedback_cleared_after_use(self):
        """Validation feedback should be cleared after one use."""
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")

        planner = PlannerModule(registry=registry)

        prompts = []

        async def capture_prompt(prompt, **kwargs):
            prompts.append(prompt)
            return make_valid_yaml_output()

        planner._call_sdk = capture_prompt
        planner.set_validation_feedback([
            {"check": "test", "message": "bad plan"},
        ])

        # First call should include feedback
        _ = [e async for e in planner.process(make_task_submitted())]
        # Second call should not
        _ = [e async for e in planner.process(make_task_submitted())]

        assert "previous plan failed validation" in prompts[0]
        assert "previous plan failed validation" not in prompts[1]
