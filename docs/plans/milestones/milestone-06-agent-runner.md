# Milestone 6: Agent Runner + Red Flagger + Context Builder

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the single-step execution core: run one agent via SDK, extract output from the message stream, validate with red-flagger, and build context from previous step outputs.

**Architecture:** Three independent components: `AgentRunner` (SDK call + stream extraction), `RedFlagger` (loose output validation), `ContextBuilder` (inject whole step outputs as YAML). Each testable in isolation.

**Tech Stack:** Python 3.11+, `claude-agent-sdk`, `pytest`, `pytest-asyncio`

**Depends On:** M1 (models, events), M2 (YAML cleaner)

---

## Task 1: Context Builder

**Files:**
- Create: `src/maker/executor/__init__.py`
- Create: `src/maker/executor/context_builder.py`
- Create: `tests/test_executor/__init__.py`
- Create: `tests/test_executor/test_context_builder.py`

**Step 1: Write tests**

```python
# tests/test_executor/test_context_builder.py
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
        """Input variable 'step_0_output.user_id' → includes step_0_output."""
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
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement `src/maker/executor/context_builder.py`**

```python
import yaml
from maker.core.models import PlanStep


class ContextBuilder:
    def build(self, step: PlanStep, step_outputs: dict[str, dict]) -> str:
        """Build context string by injecting full outputs of referenced steps.

        From each input_variable, extracts the step name (everything before first '.'),
        then injects the full output dict of that step as YAML.

        Returns empty string if no input_variables.
        """
        if not step.input_variables:
            return ""

        # Extract unique step names
        step_names = set()
        for var in step.input_variables:
            step_name = var.split(".")[0]
            step_names.add(step_name)

        # Build context dict
        context = {}
        for name in sorted(step_names):
            if name not in step_outputs:
                raise KeyError(f"Step output '{name}' not found. Available: {list(step_outputs.keys())}")
            context[name] = step_outputs[name]

        return yaml.dump(context, default_flow_style=False)
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/executor/ tests/test_executor/
git commit -m "feat: add context builder for step output injection"
```

---

## Task 2: Red Flagger

**Files:**
- Create: `src/maker/red_flag/__init__.py`
- Create: `src/maker/red_flag/red_flagger.py`
- Create: `tests/test_red_flag/__init__.py`
- Create: `tests/test_red_flag/test_red_flagger.py`

**Step 1: Write tests**

```python
# tests/test_red_flag/test_red_flagger.py
import pytest
from maker.red_flag.red_flagger import RedFlagger
from maker.core.models import AgentResult


def make_result(**overrides):
    defaults = {
        "output": {"key": "value"},
        "raw_response": "key: value",
        "was_repaired": False,
        "tokens": 100,
        "cost_usd": 0.001,
        "duration_ms": 500,
        "error": None,
    }
    defaults.update(overrides)
    return AgentResult(**defaults)


class TestRedFlagger:
    def test_valid_dict_passes(self):
        flagger = RedFlagger()
        result = make_result(output={"key": "value"})
        assert flagger.check(result) is False  # not flagged

    def test_nested_dict_passes(self):
        flagger = RedFlagger()
        result = make_result(output={"outer": {"inner": 42}})
        assert flagger.check(result) is False

    def test_empty_dict_passes(self):
        """Empty dict is valid — maybe step just confirms something."""
        flagger = RedFlagger()
        result = make_result(output={})
        assert flagger.check(result) is False

    def test_list_output_flagged(self):
        flagger = RedFlagger()
        result = make_result(output=["a", "b"])
        assert flagger.check(result) is True  # flagged

    def test_string_output_flagged(self):
        flagger = RedFlagger()
        result = make_result(output="just a string")
        assert flagger.check(result) is True

    def test_number_output_flagged(self):
        flagger = RedFlagger()
        result = make_result(output=42)
        assert flagger.check(result) is True

    def test_none_output_flagged(self):
        flagger = RedFlagger()
        result = make_result(output=None)
        assert flagger.check(result) is True

    def test_agent_error_flagged(self):
        flagger = RedFlagger()
        result = make_result(error="Agent crashed")
        assert flagger.check(result) is True

    def test_reason_for_flagging(self):
        """Red flagger should explain why it flagged."""
        flagger = RedFlagger()

        result = make_result(output="string")
        flagged, reason = flagger.check_with_reason(result)
        assert flagged is True
        assert "dict" in reason.lower()

        result = make_result(error="crash")
        flagged, reason = flagger.check_with_reason(result)
        assert flagged is True
        assert "error" in reason.lower()

    def test_dict_with_extra_fields_passes(self):
        """Extra fields beyond output_schema are allowed (loose validation)."""
        flagger = RedFlagger()
        result = make_result(output={"expected": "val", "bonus": "extra"})
        assert flagger.check(result) is False

    def test_dict_with_error_key_passes(self):
        """A dict containing an 'error' key is still valid output."""
        flagger = RedFlagger()
        result = make_result(output={"error": "something went wrong"})
        assert flagger.check(result) is False  # it's still a dict
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement `src/maker/red_flag/red_flagger.py`**

```python
from maker.core.models import AgentResult


class RedFlagger:
    def check(self, result: AgentResult) -> bool:
        """Returns True if the result should be discarded (red-flagged)."""
        flagged, _ = self.check_with_reason(result)
        return flagged

    def check_with_reason(self, result: AgentResult) -> tuple[bool, str]:
        """Returns (is_flagged, reason)."""
        if result.error:
            return True, f"Agent error: {result.error}"
        if not isinstance(result.output, dict):
            return True, f"Output is not a dict (got {type(result.output).__name__})"
        return False, ""
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/red_flag/ tests/test_red_flag/
git commit -m "feat: add red flagger with loose output validation"
```

---

## Task 3: Agent Runner

**Files:**
- Create: `src/maker/executor/agent_runner.py`
- Create: `tests/test_executor/test_agent_runner.py`

**Step 1: Write tests**

```python
# tests/test_executor/test_agent_runner.py
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

        # Fenced YAML — cleaner should strip fences
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
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement `src/maker/executor/agent_runner.py`**

Key interface:

```python
from maker.core.models import PlanStep, AgentResult, TaskConfig
from maker.yaml_cleaner.cleaner import YAMLCleaner
from maker.prompts import load_prompt


class AgentRunner:
    def __init__(self):
        self._yaml_cleaner = YAMLCleaner()

    async def run(self, step: PlanStep, context: str, config: TaskConfig) -> AgentResult:
        """Run one isolated agent for one step.

        1. Build prompt from step description + context
        2. Call SDK query() with step's tools
        3. Extract last TextBlock from final AssistantMessage
        4. Parse through YAML cleaner
        5. Return AgentResult
        """
        ...

    async def _sdk_query(self, prompt: str, **kwargs):
        """Call claude-agent-sdk query(). Yields message stream.
        This method exists to be easily mocked in tests."""
        ...
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/executor/agent_runner.py tests/test_executor/test_agent_runner.py
git commit -m "feat: add agent runner with SDK stream extraction"
```

---

## Definition of Done

- [ ] `uv run pytest tests/test_executor/test_context_builder.py tests/test_red_flag/ tests/test_executor/test_agent_runner.py -v` — all tests pass
- [ ] ContextBuilder injects full step outputs as YAML for referenced steps
- [ ] ContextBuilder extracts step name from dotted paths (e.g., `step_0_output` from `step_0_output.field`)
- [ ] ContextBuilder deduplicates step references
- [ ] ContextBuilder raises on missing step outputs
- [ ] RedFlagger passes valid dicts, flags non-dicts and errors
- [ ] RedFlagger provides reason for flagging
- [ ] AgentRunner extracts last TextBlock from final AssistantMessage
- [ ] AgentRunner handles error ResultMessages
- [ ] AgentRunner uses YAML cleaner for output parsing
- [ ] AgentRunner passes correct tools (primary + fallback + AskUserQuestion) to SDK
- [ ] AgentRunner includes context in prompt
- [ ] All code committed
