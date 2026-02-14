# Milestone 4: Planner Module

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the Planner module that takes a user task + available tools and produces a parsed, structured Plan via a single Claude Agent SDK call.

**Architecture:** Planner is a `Module` that receives `TaskSubmitted`, calls SDK `query()` with the planner prompt, parses the YAML output (mapping `plan` → `steps`), and emits `PlanCreated`.

**Tech Stack:** Python 3.11+, `claude-agent-sdk`, `pytest`, `pytest-asyncio`

**Depends On:** M1 (models, events, module ABC), M2 (YAML cleaner), M3 (tool registry, prompts)

---

## Task 1: Plan Parser

**Files:**
- Create: `src/maker/planner/__init__.py`
- Create: `src/maker/planner/parser.py`
- Create: `tests/test_planner/__init__.py`
- Create: `tests/test_planner/test_parser.py`

The parser converts raw YAML (after cleaning) into a `Plan` dataclass. This is separate from the planner module itself so it can be tested without SDK mocking.

**Step 1: Write tests**

```python
# tests/test_planner/test_parser.py
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
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement `src/maker/planner/parser.py`**

```python
from maker.core.models import Plan, PlanStep


def parse_plan(raw: dict) -> Plan:
    """Parse a raw YAML dict into a Plan dataclass.

    Handles the YAML key mapping: 'plan' → 'steps'.
    Validates required fields exist.
    """
    if not isinstance(raw, dict):
        raise ValueError("Plan must be a dict")

    if "reasoning" not in raw:
        raise ValueError("Plan must have 'reasoning' field")

    # Map 'plan' → 'steps'
    step_list = raw.get("plan") or raw.get("steps")
    if step_list is None:
        raise ValueError("Plan must have 'plan' or 'steps' field")
    if not isinstance(step_list, list):
        raise ValueError("'plan'/'steps' must be a list")

    steps = [_parse_step(s) for s in step_list]
    return Plan(reasoning=raw["reasoning"], steps=steps)


def _parse_step(raw_step: dict) -> PlanStep:
    """Parse a raw step dict into a PlanStep dataclass."""
    ...
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/planner/ tests/test_planner/
git commit -m "feat: add plan parser with plan→steps key mapping"
```

---

## Task 2: Planner Module

**Files:**
- Create: `src/maker/planner/planner.py`
- Create: `tests/test_planner/test_planner.py`

**Step 1: Write tests**

```python
# tests/test_planner/test_planner.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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

        # Mock the SDK query to return a stream with our YAML
        mock_messages = _mock_sdk_stream(make_valid_yaml_output())

        with patch.object(planner, "_call_sdk", return_value=mock_messages):
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
            return _mock_sdk_stream(make_valid_yaml_output())

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
        mock_messages = _mock_sdk_stream(fenced_yaml)

        with patch.object(planner, "_call_sdk", return_value=mock_messages):
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


def _mock_sdk_stream(text_content: str):
    """Create a mock SDK message stream that returns the given text."""
    # Returns an async iterator of mock messages
    # Final AssistantMessage with a TextBlock containing text_content
    ...
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement `src/maker/planner/planner.py`**

Key interface:

```python
from maker.core.module import Module
from maker.core.events import TaskSubmitted, PlanCreated
from maker.core.models import TaskConfig
from maker.planner.parser import parse_plan
from maker.yaml_cleaner.cleaner import YAMLCleaner
from maker.prompts import load_prompt
from maker.tools.registry import ToolRegistry
from typing import AsyncIterator
import time


class PlannerModule(Module):
    def __init__(self, registry: ToolRegistry):
        self._registry = registry
        self._yaml_cleaner = YAMLCleaner()

    async def process(self, event) -> AsyncIterator:
        if not isinstance(event, TaskSubmitted):
            return

        # 1. Build prompt with tools
        tools_list = self._format_tools()
        system_prompt = load_prompt("planner_system")
        user_prompt = load_prompt(
            "planner_user",
            instruction=event.instruction,
            tools_list=tools_list,
        )

        # 2. Call SDK
        raw_output = await self._call_sdk(user_prompt, system_prompt=system_prompt, config=event.config)

        # 3. Parse through YAML cleaner
        parsed, _ = await self._yaml_cleaner.parse(raw_output)

        # 4. Parse into Plan (maps 'plan' → 'steps')
        plan = parse_plan(parsed)

        yield PlanCreated(timestamp=time.time(), plan=plan)

    async def _call_sdk(self, prompt: str, **kwargs) -> str:
        """Call claude-agent-sdk query() and extract final text output.

        Extraction rule:
        1. Iterate all messages from query()
        2. Collect AssistantMessage objects
        3. From final AssistantMessage, take last TextBlock content
        4. If ResultMessage has subtype=="error", raise
        """
        ...

    def _format_tools(self) -> str:
        """Format tool list for insertion into planner prompt."""
        ...
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/planner/ tests/test_planner/
git commit -m "feat: add planner module with SDK integration"
```

---

## Definition of Done

- [ ] `uv run pytest tests/test_planner/ -v` — all tests pass
- [ ] Plan parser handles `plan` → `steps` key mapping
- [ ] Plan parser handles both `plan` and `steps` keys
- [ ] Plan parser validates required fields
- [ ] Plan parser handles conditional steps
- [ ] Planner module emits `PlanCreated` with valid Plan
- [ ] Planner passes tools list to prompt
- [ ] Planner uses YAML cleaner (fence-wrapped output works)
- [ ] Planner ignores non-`TaskSubmitted` events
- [ ] SDK errors propagate correctly
- [ ] All code committed
