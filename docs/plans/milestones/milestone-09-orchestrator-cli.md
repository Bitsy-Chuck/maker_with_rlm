# Milestone 9: Orchestrator + CLI

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the Orchestrator that wires all modules together into a complete pipeline, the public API (`run_task`), and the CLI entry point.

**Architecture:** Orchestrator manages the pipeline: TaskSubmitted → Planner → Validator → Executor → Result. It handles replanning on validation failure. CLI uses `argparse` and calls `run_task()`.

**Tech Stack:** Python 3.11+, `argparse`, `pytest`, `pytest-asyncio`

**Depends On:** All previous milestones (M1-M8)

---

## Task 1: Orchestrator

**Files:**
- Create: `src/maker/core/orchestrator.py`
- Create: `tests/test_core/test_orchestrator.py`

**Step 1: Write tests**

```python
# tests/test_core/test_orchestrator.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time
from maker.core.orchestrator import Orchestrator
from maker.core.events import (
    TaskSubmitted, PlanCreated, ValidationPassed, ValidationFailed,
    StepStarted, StepCompleted, TaskCompleted, TaskFailed,
)
from maker.core.models import TaskConfig, Plan, PlanStep, VotingSummary
from maker.tools.registry import ToolRegistry


def make_valid_plan():
    steps = [
        PlanStep(
            step=0, task_type="action_step", title="fetch",
            task_description="Fetch data", primary_tools=["Read"],
            fallback_tools=[], primary_tool_instructions="",
            fallback_tool_instructions="", input_variables=[],
            output_variable="step_0_output",
            output_schema="{data: string}",
            next_step_sequence_number=-1,
        )
    ]
    return Plan(reasoning="test", steps=steps)


def make_config():
    return TaskConfig(instruction="test task", max_planner_retries=2)


class TestOrchestrator:
    async def test_full_pipeline_success(self):
        """Orchestrator should drive: plan → validate → execute → complete."""
        config = make_config()
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")

        orchestrator = Orchestrator(config=config, registry=registry)

        # Mock planner to return a valid plan
        plan = make_valid_plan()

        async def mock_planner_process(event):
            if isinstance(event, TaskSubmitted):
                yield PlanCreated(timestamp=time.time(), plan=plan)

        async def mock_validator_process(event):
            if isinstance(event, PlanCreated):
                yield ValidationPassed(timestamp=time.time(), checks_passed=10)

        async def mock_executor_process(event):
            if isinstance(event, ValidationPassed):
                summary = VotingSummary(strategy="none", total_samples=1, red_flagged=0, winning_votes=1)
                yield StepStarted(timestamp=time.time(), step=0, title="fetch")
                yield StepCompleted(
                    timestamp=time.time(), step=0, title="fetch",
                    output={"data": "result"}, voting_summary=summary,
                    cost_usd=0.01, duration_ms=500,
                )
                yield TaskCompleted(
                    timestamp=time.time(),
                    result={"status": "completed", "steps": []},
                    total_cost_usd=0.01, total_duration_ms=500,
                )

        orchestrator._planner.process = mock_planner_process
        orchestrator._validator.process = mock_validator_process
        orchestrator._executor.process = mock_executor_process

        events = []
        async for event in orchestrator.run():
            events.append(event)

        event_types = [type(e).__name__ for e in events]
        assert "TaskSubmitted" in event_types
        assert "PlanCreated" in event_types
        assert "ValidationPassed" in event_types
        assert "TaskCompleted" in event_types

    async def test_replanning_on_validation_failure(self):
        """If validation fails, orchestrator should retry planner."""
        config = make_config()
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")

        orchestrator = Orchestrator(config=config, registry=registry)

        planner_call_count = 0

        async def mock_planner_process(event):
            nonlocal planner_call_count
            if isinstance(event, TaskSubmitted):
                planner_call_count += 1
                yield PlanCreated(timestamp=time.time(), plan=make_valid_plan())

        validator_call_count = 0

        async def mock_validator_process(event):
            nonlocal validator_call_count
            if isinstance(event, PlanCreated):
                validator_call_count += 1
                if validator_call_count == 1:
                    yield ValidationFailed(
                        timestamp=time.time(),
                        errors=[{"check": "test", "message": "bad plan"}],
                    )
                else:
                    yield ValidationPassed(timestamp=time.time(), checks_passed=10)

        async def mock_executor_process(event):
            if isinstance(event, ValidationPassed):
                yield TaskCompleted(
                    timestamp=time.time(),
                    result={"status": "completed", "steps": []},
                    total_cost_usd=0.0, total_duration_ms=0,
                )

        orchestrator._planner.process = mock_planner_process
        orchestrator._validator.process = mock_validator_process
        orchestrator._executor.process = mock_executor_process

        events = [e async for e in orchestrator.run()]
        assert planner_call_count == 2
        assert validator_call_count == 2

    async def test_max_planner_retries_exceeded(self):
        """If planner fails max_planner_retries times, task should fail."""
        config = TaskConfig(instruction="test", max_planner_retries=2)
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")

        orchestrator = Orchestrator(config=config, registry=registry)

        async def mock_planner_process(event):
            if isinstance(event, TaskSubmitted):
                yield PlanCreated(timestamp=time.time(), plan=make_valid_plan())

        async def mock_validator_process(event):
            if isinstance(event, PlanCreated):
                yield ValidationFailed(
                    timestamp=time.time(),
                    errors=[{"check": "test", "message": "always fails"}],
                )

        orchestrator._planner.process = mock_planner_process
        orchestrator._validator.process = mock_validator_process

        events = [e async for e in orchestrator.run()]
        task_failed = [e for e in events if isinstance(e, TaskFailed)]
        assert len(task_failed) == 1

    async def test_all_events_emitted_to_bus(self):
        """Every event from every module should appear in the output stream."""
        config = make_config()
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")

        orchestrator = Orchestrator(config=config, registry=registry)

        async def mock_planner_process(event):
            if isinstance(event, TaskSubmitted):
                yield PlanCreated(timestamp=time.time(), plan=make_valid_plan())

        async def mock_validator_process(event):
            if isinstance(event, PlanCreated):
                yield ValidationPassed(timestamp=time.time(), checks_passed=10)

        async def mock_executor_process(event):
            if isinstance(event, ValidationPassed):
                yield TaskCompleted(
                    timestamp=time.time(),
                    result={"status": "completed", "steps": []},
                    total_cost_usd=0.0, total_duration_ms=0,
                )

        orchestrator._planner.process = mock_planner_process
        orchestrator._validator.process = mock_validator_process
        orchestrator._executor.process = mock_executor_process

        events = [e async for e in orchestrator.run()]
        # Should have at least: TaskSubmitted, PlanCreated, ValidationPassed, TaskCompleted
        assert len(events) >= 4
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement `src/maker/core/orchestrator.py`**

Key interface:

```python
from maker.core.models import TaskConfig
from maker.core.events import (
    TaskSubmitted, PlanCreated, ValidationPassed, ValidationFailed,
    TaskFailed,
)
from maker.planner.planner import PlannerModule
from maker.validator.validator import ValidatorModule
from maker.executor.executor import ExecutorModule
from maker.tools.registry import ToolRegistry
from typing import AsyncIterator
import time


class Orchestrator:
    def __init__(self, config: TaskConfig, registry: ToolRegistry):
        self._config = config
        self._registry = registry
        self._planner = PlannerModule(registry=registry)
        self._validator = ValidatorModule(registry=registry, config=config)
        self._executor = None  # created after plan is validated

    async def run(self) -> AsyncIterator:
        """Drive the full pipeline. Yields all events."""
        # 1. Emit TaskSubmitted
        task_event = TaskSubmitted(
            timestamp=time.time(),
            instruction=self._config.instruction,
            config=self._config,
        )
        yield task_event

        # 2. Plan → Validate loop (with retries)
        plan = None
        for attempt in range(self._config.max_planner_retries + 1):
            # Run planner
            async for event in self._planner.process(task_event):
                yield event
                if isinstance(event, PlanCreated):
                    plan_event = event

            # Run validator
            async for event in self._validator.process(plan_event):
                yield event
                if isinstance(event, ValidationPassed):
                    plan = plan_event.plan
                    break
                elif isinstance(event, ValidationFailed):
                    # Feed errors back to planner on retry
                    pass

            if plan:
                break

        if not plan:
            yield TaskFailed(...)
            return

        # 3. Execute
        self._executor = ExecutorModule(config=self._config, plan=plan)
        # Wire up voter, etc.
        async for event in self._executor.process(
            ValidationPassed(timestamp=time.time(), checks_passed=0)
        ):
            yield event
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/core/orchestrator.py tests/test_core/test_orchestrator.py
git commit -m "feat: add orchestrator for full pipeline management"
```

---

## Task 2: Public API

**Files:**
- Modify: `src/maker/__init__.py`
- Create: `tests/test_api.py`

**Step 1: Write tests**

```python
# tests/test_api.py
import pytest
from unittest.mock import AsyncMock, patch
from maker import run_task, TaskConfig
from maker.core.events import TaskCompleted, TaskFailed


class TestPublicAPI:
    async def test_run_task_yields_events(self):
        """run_task should yield events from the orchestrator."""
        config = TaskConfig(instruction="test")

        events = []
        with patch("maker.Orchestrator") as MockOrch:
            mock_instance = AsyncMock()

            async def mock_run():
                yield TaskCompleted(
                    timestamp=1000.0,
                    result={"status": "completed", "steps": []},
                    total_cost_usd=0.0, total_duration_ms=0,
                )

            mock_instance.run = mock_run
            MockOrch.return_value = mock_instance

            async for event in run_task(config):
                events.append(event)

        assert len(events) >= 1
        assert isinstance(events[-1], TaskCompleted)

    async def test_run_task_uses_default_registry(self):
        """run_task should create a default registry if not provided."""
        config = TaskConfig(instruction="test")

        with patch("maker.Orchestrator") as MockOrch:
            mock_instance = AsyncMock()

            async def mock_run():
                return
                yield

            mock_instance.run = mock_run
            MockOrch.return_value = mock_instance

            async for _ in run_task(config):
                pass

            # Orchestrator should have been called with a registry
            call_kwargs = MockOrch.call_args
            assert call_kwargs is not None
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement public API in `src/maker/__init__.py`**

```python
"""MAKER: Maximal Agentic Decomposition with Error Correction and Red-flagging."""

from maker.core.models import TaskConfig
from maker.core.orchestrator import Orchestrator
from maker.tools.registry import ToolRegistry
from typing import AsyncIterator


async def run_task(config: TaskConfig, registry: ToolRegistry | None = None) -> AsyncIterator:
    """Run a MAKER task. Yields events as they occur."""
    if registry is None:
        registry = ToolRegistry.with_defaults()

    orchestrator = Orchestrator(config=config, registry=registry)
    async for event in orchestrator.run():
        yield event
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/__init__.py tests/test_api.py
git commit -m "feat: add run_task public API"
```

---

## Task 3: CLI

**Files:**
- Create: `src/maker/cli/__init__.py`
- Create: `src/maker/cli/main.py`
- Create: `tests/test_cli/__init__.py`
- Create: `tests/test_cli/test_main.py`

**Step 1: Write tests**

```python
# tests/test_cli/test_main.py
import pytest
from unittest.mock import AsyncMock, patch
from maker.cli.main import parse_args, format_event
from maker.core.events import (
    TaskSubmitted, PlanCreated, StepStarted, StepCompleted,
    TaskCompleted, TaskFailed, ValidationPassed,
)
from maker.core.models import TaskConfig, Plan, VotingSummary


class TestParseArgs:
    def test_basic_instruction(self):
        args = parse_args(["Find all TODO comments"])
        assert args.instruction == "Find all TODO comments"
        assert args.model == "claude-sonnet-4-5"
        assert args.voting == "none"

    def test_with_options(self):
        args = parse_args([
            "Deploy staging",
            "--model", "claude-opus-4-6",
            "--voting", "majority",
            "--voting-n", "5",
            "--max-voting-samples", "15",
            "--quality-checks",
        ])
        assert args.instruction == "Deploy staging"
        assert args.model == "claude-opus-4-6"
        assert args.voting == "majority"
        assert args.voting_n == 5
        assert args.max_voting_samples == 15
        assert args.quality_checks is True

    def test_first_to_k_options(self):
        args = parse_args([
            "task",
            "--voting", "first_to_k",
            "--voting-k", "3",
        ])
        assert args.voting == "first_to_k"
        assert args.voting_k == 3

    def test_defaults(self):
        args = parse_args(["task"])
        assert args.voting_n == 3
        assert args.voting_k == 2
        assert args.max_voting_samples == 10
        assert args.quality_checks is False


class TestFormatEvent:
    def test_format_step_started(self):
        event = StepStarted(timestamp=1000.0, step=0, title="fetch_data")
        output = format_event(event)
        assert "Step 0" in output
        assert "fetch_data" in output

    def test_format_step_completed(self):
        summary = VotingSummary(strategy="none", total_samples=1, red_flagged=0, winning_votes=1)
        event = StepCompleted(
            timestamp=1000.0, step=0, title="fetch",
            output={"data": "x"}, voting_summary=summary,
            cost_usd=0.01, duration_ms=500,
        )
        output = format_event(event)
        assert "Step 0" in output
        assert "completed" in output.lower() or "fetch" in output

    def test_format_task_completed(self):
        event = TaskCompleted(
            timestamp=1000.0,
            result={"status": "completed", "steps": []},
            total_cost_usd=0.05, total_duration_ms=15000,
        )
        output = format_event(event)
        assert "completed" in output.lower()
        assert "$0.05" in output or "0.05" in output

    def test_format_task_failed(self):
        event = TaskFailed(timestamp=1000.0, error="step 2 failed", step=2)
        output = format_event(event)
        assert "failed" in output.lower()
        assert "step 2" in output.lower()

    def test_format_validation_passed(self):
        event = ValidationPassed(timestamp=1000.0, checks_passed=12)
        output = format_event(event)
        assert "12" in output or "passed" in output.lower()
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement**

`src/maker/cli/main.py`:

```python
import argparse
import asyncio
from maker import run_task
from maker.core.models import TaskConfig
from maker.core.events import (
    TaskSubmitted, PlanCreated, ValidationPassed, ValidationFailed,
    StepStarted, StepCompleted, StepFailed, TaskCompleted, TaskFailed,
)


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MAKER: Maximal Agentic Decomposition")
    parser.add_argument("instruction", help="The task to execute")
    parser.add_argument("--model", default="claude-sonnet-4-5", help="Model to use")
    parser.add_argument("--voting", default="none", choices=["none", "majority", "first_to_k"])
    parser.add_argument("--voting-n", type=int, default=3, help="Samples for majority voting")
    parser.add_argument("--voting-k", type=int, default=2, help="K for first-to-K voting")
    parser.add_argument("--max-voting-samples", type=int, default=10, help="Max voting samples per step")
    parser.add_argument("--quality-checks", action="store_true", help="Enable LLM quality checks")
    return parser.parse_args(argv)


def format_event(event) -> str:
    """Format an event for CLI display."""
    ...


def cli():
    args = parse_args()
    config = TaskConfig(
        instruction=args.instruction,
        model=args.model,
        voting_strategy=args.voting,
        voting_n=args.voting_n,
        voting_k=args.voting_k,
        max_voting_samples=args.max_voting_samples,
        enable_quality_checks=args.quality_checks,
    )

    async def _run():
        async for event in run_task(config):
            print(format_event(event))

    asyncio.run(_run())


if __name__ == "__main__":
    cli()
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/cli/ tests/test_cli/
git commit -m "feat: add CLI entry point with argument parsing"
```

---

## Task 4: End-to-End Integration Test

**Files:**
- Create: `tests/test_integration/__init__.py`
- Create: `tests/test_integration/test_end_to_end.py`

**Step 1: Write test**

```python
# tests/test_integration/test_end_to_end.py
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
```

**Step 2: Run test — expect PASS (all components wired together)**

**Step 3: Commit**

```bash
git add tests/test_integration/
git commit -m "feat: add end-to-end integration test"
```

---

## Definition of Done

- [ ] `uv run pytest tests/ -v` — ALL tests across ALL milestones pass
- [ ] Orchestrator drives plan → validate → execute pipeline
- [ ] Orchestrator retries planner on validation failure
- [ ] Orchestrator respects max_planner_retries
- [ ] `run_task()` yields events from the orchestrator
- [ ] `run_task()` creates default registry if none provided
- [ ] CLI parses all arguments correctly
- [ ] CLI formats all event types for display
- [ ] `maker "instruction"` command works (with mocked SDK)
- [ ] End-to-end test passes with mocked SDK
- [ ] All code committed
- [ ] Package installs and runs cleanly
