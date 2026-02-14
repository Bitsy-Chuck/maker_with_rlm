# Milestone 1: Project Foundation

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Set up the installable Python package with all data models, typed event system, event bus, and module ABC interface.

**Architecture:** Pure Python dataclasses for models/events, async queue-based event bus, ABC for module contract. No SDK dependency needed — this is the foundation everything else builds on.

**Tech Stack:** Python 3.11+, `pyyaml`, `pytest`, `pytest-asyncio`

---

## Task 1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `src/maker/__init__.py`
- Create: `src/maker/core/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "maker"
version = "0.1.0"
description = "MAKER: Maximal Agentic Decomposition with Error Correction and Red-flagging"
requires-python = ">=3.11"
dependencies = [
    "claude-agent-sdk",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[project.scripts]
maker = "maker.cli.main:cli"

[tool.hatch.build.targets.wheel]
packages = ["src/maker"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 2: Create package init files**

`src/maker/__init__.py`:
```python
"""MAKER: Maximal Agentic Decomposition with Error Correction and Red-flagging."""
```

`src/maker/core/__init__.py`:
```python
```

`tests/__init__.py`:
```python
```

`tests/conftest.py`:
```python
```

**Step 3: Install in dev mode**

Run: `cd /Users/air/Dropbox/air/projects/maker && uv venv && uv pip install -e ".[dev]"`

**Step 4: Verify install**

Run: `uv run python -c "import maker; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git init
git add pyproject.toml src/ tests/
git commit -m "feat: initialize maker project structure"
```

---

## Task 2: Data Models

**Files:**
- Create: `src/maker/core/models.py`
- Create: `tests/test_core/__init__.py`
- Create: `tests/test_core/test_models.py`

**Step 1: Write tests**

```python
# tests/test_core/test_models.py
import pytest
from maker.core.models import (
    TaskConfig,
    PlanStep,
    Plan,
    AgentResult,
    VoteResult,
    VotingSummary,
    MCPServerConfig,
    ToolInfo,
)


class TestTaskConfig:
    def test_defaults(self):
        config = TaskConfig(instruction="do something")
        assert config.instruction == "do something"
        assert config.model == "claude-sonnet-4-5"
        assert config.voting_strategy == "none"
        assert config.voting_n == 3
        assert config.voting_k == 2
        assert config.max_voting_samples == 10
        assert config.step_max_retries == 2
        assert config.enable_quality_checks is False
        assert config.max_planner_retries == 2
        assert config.mcp_servers == {}
        assert config.allowed_builtin_tools is None

    def test_custom_values(self):
        config = TaskConfig(
            instruction="deploy",
            model="claude-opus-4-6",
            voting_strategy="first_to_k",
            voting_k=3,
            max_voting_samples=20,
        )
        assert config.model == "claude-opus-4-6"
        assert config.voting_strategy == "first_to_k"
        assert config.voting_k == 3
        assert config.max_voting_samples == 20

    def test_invalid_voting_strategy_is_just_a_string(self):
        """TaskConfig doesn't validate strategy names — that's the orchestrator's job."""
        config = TaskConfig(instruction="x", voting_strategy="invalid")
        assert config.voting_strategy == "invalid"


class TestPlanStep:
    def test_action_step(self):
        step = PlanStep(
            step=0,
            task_type="action_step",
            title="fetch_data",
            task_description="Fetch data from API",
            primary_tools=["WebFetch"],
            fallback_tools=[],
            primary_tool_instructions="Use WebFetch with URL...",
            fallback_tool_instructions="",
            input_variables=[],
            output_variable="step_0_output",
            output_schema="{data: string}",
            next_step_sequence_number=1,
        )
        assert step.step == 0
        assert step.task_type == "action_step"
        assert step.primary_tools == ["WebFetch"]
        assert step.fallback_tools == []
        assert step.input_variables == []
        assert step.next_step_sequence_number == 1

    def test_conditional_step(self):
        step = PlanStep(
            step=3,
            task_type="conditional_step",
            title="decide_next",
            task_description="If status is critical go to step 4 else step 6",
            primary_tools=[],
            fallback_tools=[],
            primary_tool_instructions="",
            fallback_tool_instructions="",
            input_variables=["step_2_output.status"],
            output_variable="step_3_output",
            output_schema="{next_step: int, reason: string}",
            next_step_sequence_number=-2,
        )
        assert step.task_type == "conditional_step"
        assert step.next_step_sequence_number == -2


class TestPlan:
    def test_creation(self):
        steps = [
            PlanStep(
                step=0, task_type="action_step", title="t",
                task_description="d", primary_tools=["Read"],
                fallback_tools=[], primary_tool_instructions="",
                fallback_tool_instructions="", input_variables=[],
                output_variable="step_0_output",
                output_schema="{x: string}",
                next_step_sequence_number=-1,
            )
        ]
        plan = Plan(reasoning="test reasoning", steps=steps)
        assert plan.reasoning == "test reasoning"
        assert len(plan.steps) == 1
        assert plan.steps[0].step == 0


class TestAgentResult:
    def test_successful_result(self):
        result = AgentResult(
            output={"key": "value"},
            raw_response="key: value",
            was_repaired=False,
            tokens=100,
            cost_usd=0.001,
            duration_ms=500,
        )
        assert result.output == {"key": "value"}
        assert result.error is None

    def test_failed_result(self):
        result = AgentResult(
            output={},
            raw_response="",
            was_repaired=False,
            tokens=0,
            cost_usd=0.0,
            duration_ms=100,
            error="Agent crashed",
        )
        assert result.error == "Agent crashed"


class TestVoteResult:
    def test_creation(self):
        result = VoteResult(
            winner={"answer": 42},
            canonical_hash="abc123",
            total_samples=3,
            red_flagged=0,
            vote_counts={"abc123": 2, "def456": 1},
        )
        assert result.winner == {"answer": 42}
        assert result.total_samples == 3


class TestVotingSummary:
    def test_creation(self):
        summary = VotingSummary(
            strategy="majority",
            total_samples=3,
            red_flagged=0,
            winning_votes=2,
        )
        assert summary.strategy == "majority"


class TestToolInfo:
    def test_builtin(self):
        tool = ToolInfo(name="Read", description="Read files", source="builtin")
        assert tool.server_name is None

    def test_mcp(self):
        tool = ToolInfo(
            name="mcp__github__list_issues",
            description="List issues",
            source="mcp",
            server_name="github",
        )
        assert tool.server_name == "github"


class TestMCPServerConfig:
    def test_creation(self):
        config = MCPServerConfig(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_TOKEN": "abc"},
        )
        assert config.command == "npx"
        assert config.env == {"GITHUB_TOKEN": "abc"}

    def test_default_env(self):
        config = MCPServerConfig(command="node", args=["server.js"])
        assert config.env == {}
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/air/Dropbox/air/projects/maker && uv run pytest tests/test_core/test_models.py -v`
Expected: FAIL (imports not found)

**Step 3: Implement `src/maker/core/models.py`**

```python
from dataclasses import dataclass, field


@dataclass
class MCPServerConfig:
    command: str
    args: list[str]
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class ToolInfo:
    name: str
    description: str
    source: str  # "builtin" | "mcp"
    server_name: str | None = None


@dataclass
class TaskConfig:
    instruction: str
    model: str = "claude-sonnet-4-5"
    voting_strategy: str = "none"  # "none" | "majority" | "first_to_k"
    voting_n: int = 3
    voting_k: int = 2
    max_voting_samples: int = 10
    step_max_retries: int = 2
    enable_quality_checks: bool = False
    max_planner_retries: int = 2
    mcp_servers: dict = field(default_factory=dict)
    allowed_builtin_tools: list[str] | None = None


@dataclass
class PlanStep:
    step: int
    task_type: str  # "action_step" | "conditional_step"
    title: str
    task_description: str
    primary_tools: list[str]
    fallback_tools: list[str]
    primary_tool_instructions: str
    fallback_tool_instructions: str
    input_variables: list[str]
    output_variable: str
    output_schema: str
    next_step_sequence_number: int


@dataclass
class Plan:
    reasoning: str
    steps: list[PlanStep]


@dataclass
class AgentResult:
    output: dict
    raw_response: str
    was_repaired: bool
    tokens: int
    cost_usd: float
    duration_ms: int
    error: str | None = None


@dataclass
class VotingSummary:
    strategy: str
    total_samples: int
    red_flagged: int
    winning_votes: int


@dataclass
class VoteResult:
    winner: dict
    canonical_hash: str
    total_samples: int
    red_flagged: int
    vote_counts: dict[str, int]
```

**Step 4: Run tests**

Run: `cd /Users/air/Dropbox/air/projects/maker && uv run pytest tests/test_core/test_models.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/maker/core/models.py tests/test_core/
git commit -m "feat: add core data models"
```

---

## Task 3: Typed Event System

**Files:**
- Create: `src/maker/core/events.py`
- Create: `tests/test_core/test_events.py`

**Step 1: Write tests**

```python
# tests/test_core/test_events.py
import pytest
import time
import asyncio
import json
from maker.core.events import (
    TaskSubmitted,
    PlanCreated,
    ValidationPassed,
    ValidationFailed,
    StepStarted,
    AgentSampleCompleted,
    AgentSampleRedFlagged,
    VoteCompleted,
    StepCompleted,
    StepFailed,
    TaskCompleted,
    TaskFailed,
    EventBus,
    event_to_dict,
)
from maker.core.models import TaskConfig, Plan, PlanStep, VotingSummary


class TestEventCreation:
    def test_task_submitted(self):
        config = TaskConfig(instruction="test")
        event = TaskSubmitted(
            timestamp=1000.0, instruction="test", config=config
        )
        assert event.type == "task_submitted"
        assert event.instruction == "test"

    def test_plan_created(self):
        plan = Plan(reasoning="r", steps=[])
        event = PlanCreated(timestamp=1000.0, plan=plan)
        assert event.type == "plan_created"
        assert event.plan.reasoning == "r"

    def test_validation_passed(self):
        event = ValidationPassed(timestamp=1000.0, checks_passed=12)
        assert event.type == "validation_passed"

    def test_validation_failed(self):
        errors = [{"check": "valid_yaml", "message": "bad yaml"}]
        event = ValidationFailed(timestamp=1000.0, errors=errors)
        assert event.type == "validation_failed"
        assert len(event.errors) == 1

    def test_step_started(self):
        event = StepStarted(timestamp=1000.0, step=0, title="fetch_data")
        assert event.type == "step_started"
        assert event.step == 0

    def test_agent_sample_completed(self):
        event = AgentSampleCompleted(
            timestamp=1000.0, step=0, sample_index=0,
            output={"key": "val"}, cost_usd=0.001, duration_ms=500,
        )
        assert event.type == "agent_sample_completed"

    def test_agent_sample_red_flagged(self):
        event = AgentSampleRedFlagged(
            timestamp=1000.0, step=0, sample_index=1, reason="not a dict"
        )
        assert event.type == "agent_sample_red_flagged"

    def test_vote_completed(self):
        event = VoteCompleted(
            timestamp=1000.0, step=0, winner={"a": 1},
            total_samples=3, red_flagged=0,
        )
        assert event.type == "vote_completed"

    def test_step_completed(self):
        summary = VotingSummary(strategy="none", total_samples=1, red_flagged=0, winning_votes=1)
        event = StepCompleted(
            timestamp=1000.0, step=0, title="fetch_data",
            output={"data": "x"}, voting_summary=summary,
            cost_usd=0.001, duration_ms=500,
        )
        assert event.type == "step_completed"
        assert event.output == {"data": "x"}

    def test_step_failed(self):
        event = StepFailed(
            timestamp=1000.0, step=2, title="broken",
            error="all samples red-flagged",
        )
        assert event.type == "step_failed"

    def test_task_completed(self):
        event = TaskCompleted(
            timestamp=1000.0,
            result={"status": "completed", "steps": []},
            total_cost_usd=0.05,
            total_duration_ms=15000,
        )
        assert event.type == "task_completed"

    def test_task_failed(self):
        event = TaskFailed(
            timestamp=1000.0, error="step 2 failed", step=2,
        )
        assert event.type == "task_failed"


class TestEventSerialization:
    def test_event_to_dict(self):
        event = StepStarted(timestamp=1000.0, step=0, title="fetch")
        d = event_to_dict(event)
        assert d["type"] == "step_started"
        assert d["step"] == 0
        assert d["title"] == "fetch"
        assert d["timestamp"] == 1000.0

    def test_event_to_json(self):
        event = StepStarted(timestamp=1000.0, step=0, title="fetch")
        d = event_to_dict(event)
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["type"] == "step_started"

    def test_nested_event_to_dict(self):
        """Events with nested dataclasses should serialize fully."""
        summary = VotingSummary(strategy="majority", total_samples=3, red_flagged=0, winning_votes=2)
        event = StepCompleted(
            timestamp=1000.0, step=0, title="t",
            output={"k": "v"}, voting_summary=summary,
            cost_usd=0.01, duration_ms=100,
        )
        d = event_to_dict(event)
        assert d["voting_summary"]["strategy"] == "majority"


class TestEventBus:
    async def test_emit_and_subscribe(self):
        bus = EventBus()
        event = StepStarted(timestamp=1000.0, step=0, title="fetch")

        received = []

        async def consumer():
            async for e in bus.subscribe():
                received.append(e)
                break  # stop after first event

        task = asyncio.create_task(consumer())
        await bus.emit(event)
        await asyncio.wait_for(task, timeout=1.0)
        assert len(received) == 1
        assert received[0].step == 0

    async def test_multiple_subscribers(self):
        bus = EventBus()
        event = StepStarted(timestamp=1000.0, step=0, title="fetch")

        received_1 = []
        received_2 = []

        async def consumer(target_list):
            async for e in bus.subscribe():
                target_list.append(e)
                break

        t1 = asyncio.create_task(consumer(received_1))
        t2 = asyncio.create_task(consumer(received_2))
        await bus.emit(event)
        await asyncio.wait_for(asyncio.gather(t1, t2), timeout=1.0)
        assert len(received_1) == 1
        assert len(received_2) == 1

    async def test_multiple_events(self):
        bus = EventBus()
        events = [
            StepStarted(timestamp=1000.0, step=0, title="a"),
            StepStarted(timestamp=1001.0, step=1, title="b"),
        ]

        received = []

        async def consumer():
            async for e in bus.subscribe():
                received.append(e)
                if len(received) == 2:
                    break

        task = asyncio.create_task(consumer())
        for e in events:
            await bus.emit(e)
        await asyncio.wait_for(task, timeout=1.0)
        assert len(received) == 2
        assert received[0].title == "a"
        assert received[1].title == "b"

    async def test_shutdown(self):
        """After shutdown, subscribers should stop iterating."""
        bus = EventBus()
        received = []

        async def consumer():
            async for e in bus.subscribe():
                received.append(e)

        task = asyncio.create_task(consumer())
        await bus.emit(StepStarted(timestamp=1000.0, step=0, title="x"))
        await asyncio.sleep(0.05)
        await bus.shutdown()
        await asyncio.wait_for(task, timeout=1.0)
        assert len(received) == 1
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/air/Dropbox/air/projects/maker && uv run pytest tests/test_core/test_events.py -v`
Expected: FAIL (imports not found)

**Step 3: Implement `src/maker/core/events.py`**

Key interfaces:

```python
from dataclasses import dataclass, asdict, fields
from typing import AsyncIterator
import asyncio

# --- Event types ---
# Each event is a typed dataclass. The `type` field is a string literal
# set as a class default (not passed by caller).

@dataclass
class TaskSubmitted:
    type: str = "task_submitted"  # class-level default, field(init=False) pattern
    timestamp: float
    instruction: str
    config: "TaskConfig"
    # ... etc for all event types listed in design §4.3

# --- Event serialization ---
def event_to_dict(event) -> dict:
    """Recursively convert a dataclass event to a plain dict.
    Handles nested dataclasses."""
    ...

# --- Event Bus ---
class EventBus:
    """Async broadcast bus. Multiple subscribers each get every event."""
    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    async def emit(self, event) -> None:
        """Put event into every subscriber's queue."""
        ...

    async def subscribe(self) -> AsyncIterator:
        """Yield events as they arrive. Stops on shutdown sentinel."""
        ...

    async def shutdown(self) -> None:
        """Signal all subscribers to stop."""
        ...
```

Implementation notes:
- `event_to_dict` must recurse into nested dataclasses (e.g., `VotingSummary` inside `StepCompleted`)
- `EventBus.subscribe()` creates a new `asyncio.Queue`, adds it to `_subscribers`, and yields from it
- `EventBus.shutdown()` puts a `None` sentinel into each queue, which `subscribe()` treats as termination
- Use `field(init=False)` for the `type` field on each event so callers don't pass it

**Step 4: Run tests**

Run: `cd /Users/air/Dropbox/air/projects/maker && uv run pytest tests/test_core/test_events.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/maker/core/events.py tests/test_core/test_events.py
git commit -m "feat: add typed event system and event bus"
```

---

## Task 4: Module ABC Interface

**Files:**
- Create: `src/maker/core/module.py`
- Create: `tests/test_core/test_module.py`

**Step 1: Write tests**

```python
# tests/test_core/test_module.py
import pytest
from maker.core.module import Module
from maker.core.events import StepStarted, StepCompleted
from maker.core.models import VotingSummary


class TestModuleABC:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            Module()

    async def test_concrete_implementation(self):
        class EchoModule(Module):
            async def process(self, event):
                if isinstance(event, StepStarted):
                    summary = VotingSummary(
                        strategy="none", total_samples=1,
                        red_flagged=0, winning_votes=1,
                    )
                    yield StepCompleted(
                        timestamp=event.timestamp,
                        step=event.step,
                        title=event.title,
                        output={"echo": True},
                        voting_summary=summary,
                        cost_usd=0.0,
                        duration_ms=0,
                    )

        mod = EchoModule()
        event = StepStarted(timestamp=1000.0, step=0, title="test")
        results = [e async for e in mod.process(event)]
        assert len(results) == 1
        assert isinstance(results[0], StepCompleted)

    async def test_process_can_yield_nothing(self):
        class IgnoreModule(Module):
            async def process(self, event):
                return  # yields nothing
                yield  # make it a generator

        mod = IgnoreModule()
        event = StepStarted(timestamp=1000.0, step=0, title="test")
        results = [e async for e in mod.process(event)]
        assert results == []
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement `src/maker/core/module.py`**

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator


class Module(ABC):
    @abstractmethod
    async def process(self, event) -> AsyncIterator:
        """Receive an event, yield zero or more events."""
        ...
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/core/module.py tests/test_core/test_module.py
git commit -m "feat: add Module ABC interface"
```

---

## Definition of Done

- [ ] `uv run pytest tests/test_core/ -v` — all tests pass
- [ ] Package installs cleanly with `uv pip install -e ".[dev]"`
- [ ] All data models create correctly with defaults and custom values
- [ ] All event types are creatable and serializable to dict/JSON
- [ ] EventBus supports emit, subscribe (multiple), and shutdown
- [ ] Module ABC enforces `process()` contract
- [ ] All code committed
