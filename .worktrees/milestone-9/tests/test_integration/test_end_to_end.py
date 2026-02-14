import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from maker import run_task
from maker.core.models import TaskConfig
from maker.core.events import (
    TaskSubmitted, PlanCreated, ValidationPassed,
    StepStarted, StepCompleted, TaskCompleted, TaskFailed,
)
from maker.tools.registry import ToolRegistry


MOCK_PLAN_YAML = """reasoning: >
  Simple plan to read a file and summarize it.

plan:
  - step: 0
    task_type: action_step
    title: read_file
    task_description: >
      Read the contents of the file at path /tmp/test.txt.
      Output the file contents.
    primary_tools: [Read]
    fallback_tools: []
    primary_tool_instructions: Use Read tool with path /tmp/test.txt
    fallback_tool_instructions: ""
    input_variables: []
    output_variable: step_0_output
    output_schema: "{content: string}"
    next_step_sequence_number: 1

  - step: 1
    task_type: action_step
    title: summarize
    task_description: >
      Summarize the text from step_0_output.content in one sentence.
    primary_tools: []
    fallback_tools: []
    primary_tool_instructions: ""
    fallback_tool_instructions: ""
    input_variables:
      - step_0_output.content
    output_variable: step_1_output
    output_schema: "{summary: string}"
    next_step_sequence_number: -1"""


class TestEndToEnd:
    async def test_full_pipeline_mocked_sdk(self):
        """Full end-to-end test with mocked SDK calls."""
        config = TaskConfig(instruction="Read /tmp/test.txt and summarize it")
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")

        # Mock the SDK query at the AgentRunner level
        step_responses = {
            0: "content: Hello world this is a test file with some content.",
            1: "summary: A test file containing greeting text.",
        }

        with patch("maker.executor.agent_runner.AgentRunner._sdk_query") as mock_query:
            call_count = [0]

            async def fake_query(prompt, **kwargs):
                step_num = call_count[0]
                call_count[0] += 1
                text = step_responses.get(step_num, "error: unknown step")

                msg = MagicMock()
                msg.__class__.__name__ = "AssistantMessage"
                block = MagicMock()
                block.__class__.__name__ = "TextBlock"
                block.text = text
                msg.content = [block]
                yield msg

                result = MagicMock()
                result.__class__.__name__ = "ResultMessage"
                result.total_cost_usd = 0.01
                result.duration_ms = 500
                result.subtype = "success"
                yield result

            mock_query.side_effect = fake_query

            # Also mock the planner's SDK call
            with patch("maker.planner.planner.PlannerModule._call_sdk") as mock_planner:
                mock_planner.return_value = MOCK_PLAN_YAML

                events = []
                async for event in run_task(config, registry=registry):
                    events.append(event)

        # Verify the full pipeline ran
        event_types = [type(e).__name__ for e in events]

        assert "TaskSubmitted" in event_types
        assert "PlanCreated" in event_types
        assert "ValidationPassed" in event_types
        assert "StepStarted" in event_types
        assert "StepCompleted" in event_types
        assert "TaskCompleted" in event_types
        assert "TaskFailed" not in event_types

        # Verify step outputs
        completed_events = [e for e in events if isinstance(e, StepCompleted)]
        assert len(completed_events) == 2

        task_completed = [e for e in events if isinstance(e, TaskCompleted)][0]
        assert task_completed.result["status"] == "completed"
