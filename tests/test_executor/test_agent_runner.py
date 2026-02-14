import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from maker.executor.agent_runner import AgentRunner
from maker.core.models import PlanStep, AgentResult, TaskConfig


def make_step(**overrides):
    defaults = {
        "step": 0, "task_type": "action_step", "title": "test",
        "task_description": "Do something", "primary_tools": ["Read"],
        "fallback_tools": [], "primary_tool_instructions": "Use Read",
        "fallback_tool_instructions": "", "input_variables": [],
        "output_variable": "step_0_output",
        "output_schema": "{result: string}",
        "next_step_sequence_number": -1,
    }
    defaults.update(overrides)
    return PlanStep(**defaults)


def make_config(**overrides):
    defaults = {"instruction": "test"}
    defaults.update(overrides)
    return TaskConfig(**defaults)


def make_mock_assistant_message(text: str):
    """Create a mock AssistantMessage with a TextBlock."""
    text_block = MagicMock()
    text_block.text = text
    text_block.__class__.__name__ = "TextBlock"

    msg = MagicMock()
    msg.__class__.__name__ = "AssistantMessage"
    msg.content = [text_block]
    return msg


def make_mock_result_message(cost=0.001, duration=500, error=False):
    """Create a mock ResultMessage."""
    msg = MagicMock()
    msg.__class__.__name__ = "ResultMessage"
    msg.total_cost_usd = cost
    msg.duration_ms = duration
    msg.subtype = "error" if error else "success"
    return msg


class TestAgentRunner:
    async def test_extracts_yaml_from_assistant_message(self):
        runner = AgentRunner()

        async def mock_query(*args, **kwargs):
            yield make_mock_assistant_message("result: success")
            yield make_mock_result_message()

        with patch.object(runner, "_sdk_query", mock_query):
            result = await runner.run(make_step(), context="", config=make_config())

        assert isinstance(result, AgentResult)
        assert result.output == {"result": "success"}
        assert result.error is None

    async def test_extracts_last_text_block_from_final_message(self):
        """If multiple AssistantMessages, use last TextBlock of final one."""
        runner = AgentRunner()

        async def mock_query(*args, **kwargs):
            yield make_mock_assistant_message("intermediate: stuff")
            yield make_mock_assistant_message("final: answer")
            yield make_mock_result_message()

        with patch.object(runner, "_sdk_query", mock_query):
            result = await runner.run(make_step(), context="", config=make_config())

        assert result.output == {"final": "answer"}

    async def test_handles_result_message_error(self):
        runner = AgentRunner()

        async def mock_query(*args, **kwargs):
            yield make_mock_assistant_message("partial: output")
            yield make_mock_result_message(error=True)

        with patch.object(runner, "_sdk_query", mock_query):
            result = await runner.run(make_step(), context="", config=make_config())

        assert result.error is not None

    async def test_tracks_cost_and_duration(self):
        runner = AgentRunner()

        async def mock_query(*args, **kwargs):
            yield make_mock_assistant_message("result: ok")
            yield make_mock_result_message(cost=0.05, duration=2000)

        with patch.object(runner, "_sdk_query", mock_query):
            result = await runner.run(make_step(), context="", config=make_config())

        assert result.cost_usd == 0.05
        assert result.duration_ms == 2000

    async def test_yaml_cleaner_repairs_output(self):
        """If raw output needs repair, was_repaired should be True."""
        runner = AgentRunner()

        # Fenced YAML -- cleaner should strip fences
        async def mock_query(*args, **kwargs):
            yield make_mock_assistant_message("```yaml\nresult: fixed\n```")
            yield make_mock_result_message()

        with patch.object(runner, "_sdk_query", mock_query):
            result = await runner.run(make_step(), context="", config=make_config())

        assert result.output == {"result": "fixed"}

    async def test_empty_stream_returns_error(self):
        runner = AgentRunner()

        async def mock_query(*args, **kwargs):
            return
            yield  # make it an async generator

        with patch.object(runner, "_sdk_query", mock_query):
            result = await runner.run(make_step(), context="", config=make_config())

        assert result.error is not None

    async def test_passes_correct_tools_to_sdk(self):
        """Runner should pass step's tools as allowed_tools."""
        runner = AgentRunner()

        captured_kwargs = {}

        async def mock_query(*args, **kwargs):
            captured_kwargs.update(kwargs)
            yield make_mock_assistant_message("result: ok")
            yield make_mock_result_message()

        with patch.object(runner, "_sdk_query", mock_query):
            step = make_step(primary_tools=["Read", "Grep"], fallback_tools=["Bash"])
            await runner.run(step, context="", config=make_config())

        allowed = captured_kwargs.get("allowed_tools", [])
        assert "Read" in allowed
        assert "Grep" in allowed
        assert "Bash" in allowed
        assert "AskUserQuestion" in allowed  # Tier-3 implicit

    async def test_includes_context_in_prompt(self):
        runner = AgentRunner()

        captured_prompt = None

        async def mock_query(prompt, **kwargs):
            nonlocal captured_prompt
            captured_prompt = prompt
            yield make_mock_assistant_message("result: ok")
            yield make_mock_result_message()

        with patch.object(runner, "_sdk_query", mock_query):
            await runner.run(
                make_step(),
                context="step_0_output:\n  data: hello",
                config=make_config(),
            )

        assert "step_0_output" in captured_prompt
        assert "data: hello" in captured_prompt
