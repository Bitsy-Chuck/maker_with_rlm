# Milestone 8: Executor + Result Collector

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the Executor module that iterates plan steps sequentially, manages context, handles conditional routing, and collects results. Wires together AgentRunner, RedFlagger, Voter, and ContextBuilder.

**Architecture:** `ExecutorModule` is a `Module` that receives `ValidationPassed`, drives step-by-step execution, and emits step events. `ResultCollector` aggregates outputs into the final task result.

**Tech Stack:** Python 3.11+, `pytest`, `pytest-asyncio`

**Depends On:** M1 (models, events), M6 (AgentRunner, RedFlagger, ContextBuilder), M7 (Voting)

---

## Task 1: Result Collector

**Files:**
- Create: `src/maker/executor/result_collector.py`
- Create: `tests/test_executor/test_result_collector.py`

**Step 1: Write tests**

```python
# tests/test_executor/test_result_collector.py
import pytest
from maker.executor.result_collector import ResultCollector
from maker.core.models import VotingSummary


class TestResultCollector:
    def test_empty_result(self):
        collector = ResultCollector(instruction="test task")
        result = collector.finalize()
        assert result["task"] == "test task"
        assert result["status"] == "completed"
        assert result["steps"] == []
        assert result["total_cost_usd"] == 0.0
        assert result["total_duration_ms"] == 0

    def test_add_step_result(self):
        collector = ResultCollector(instruction="test")
        summary = VotingSummary(strategy="none", total_samples=1, red_flagged=0, winning_votes=1)
        collector.add_step(
            step=0, title="fetch", output={"data": "x"},
            voting_summary=summary, cost_usd=0.01, duration_ms=1000,
        )
        result = collector.finalize()
        assert len(result["steps"]) == 1
        assert result["steps"][0]["step"] == 0
        assert result["steps"][0]["output"] == {"data": "x"}
        assert result["total_cost_usd"] == 0.01
        assert result["total_duration_ms"] == 1000

    def test_multiple_steps_aggregate(self):
        collector = ResultCollector(instruction="test")
        summary = VotingSummary(strategy="majority", total_samples=3, red_flagged=0, winning_votes=2)

        collector.add_step(step=0, title="a", output={}, voting_summary=summary, cost_usd=0.01, duration_ms=500)
        collector.add_step(step=1, title="b", output={}, voting_summary=summary, cost_usd=0.02, duration_ms=800)

        result = collector.finalize()
        assert len(result["steps"]) == 2
        assert result["total_cost_usd"] == pytest.approx(0.03)
        assert result["total_duration_ms"] == 1300

    def test_finalize_as_failed(self):
        collector = ResultCollector(instruction="test")
        result = collector.finalize(status="failed")
        assert result["status"] == "failed"

    def test_step_voting_summary_in_output(self):
        collector = ResultCollector(instruction="test")
        summary = VotingSummary(strategy="first_to_k", total_samples=5, red_flagged=1, winning_votes=3)
        collector.add_step(step=0, title="t", output={}, voting_summary=summary, cost_usd=0.0, duration_ms=0)

        result = collector.finalize()
        voting = result["steps"][0]["voting"]
        assert voting["strategy"] == "first_to_k"
        assert voting["samples"] == 5
        assert voting["red_flagged"] == 1
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement `src/maker/executor/result_collector.py`**

```python
from maker.core.models import VotingSummary


class ResultCollector:
    def __init__(self, instruction: str):
        self._instruction = instruction
        self._steps: list[dict] = []
        self._total_cost = 0.0
        self._total_duration = 0

    def add_step(self, step: int, title: str, output: dict,
                 voting_summary: VotingSummary, cost_usd: float, duration_ms: int) -> None:
        ...

    def finalize(self, status: str = "completed") -> dict:
        ...
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/executor/result_collector.py tests/test_executor/test_result_collector.py
git commit -m "feat: add result collector for step output aggregation"
```

---

## Task 2: Voter Factory

**Files:**
- Create: `src/maker/voting/factory.py`
- Create: `tests/test_voting/test_factory.py`

A helper that creates the right Voter instance based on TaskConfig.

**Step 1: Write tests**

```python
# tests/test_voting/test_factory.py
import pytest
from unittest.mock import MagicMock
from maker.voting.factory import create_voter
from maker.voting.no_voter import NoVoter
from maker.voting.majority_voter import MajorityVoter
from maker.voting.first_to_k_voter import FirstToKVoter
from maker.core.models import TaskConfig
from maker.executor.agent_runner import AgentRunner
from maker.red_flag.red_flagger import RedFlagger


class TestCreateVoter:
    def test_none_strategy(self):
        runner = MagicMock(spec=AgentRunner)
        voter = create_voter("none", runner, RedFlagger())
        assert isinstance(voter, NoVoter)

    def test_majority_strategy(self):
        runner = MagicMock(spec=AgentRunner)
        voter = create_voter("majority", runner, RedFlagger())
        assert isinstance(voter, MajorityVoter)

    def test_first_to_k_strategy(self):
        runner = MagicMock(spec=AgentRunner)
        voter = create_voter("first_to_k", runner, RedFlagger())
        assert isinstance(voter, FirstToKVoter)

    def test_invalid_strategy_raises(self):
        runner = MagicMock(spec=AgentRunner)
        with pytest.raises(ValueError, match="Unknown voting strategy"):
            create_voter("invalid", runner, RedFlagger())
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement `src/maker/voting/factory.py`**

```python
from maker.voting.base import Voter
from maker.voting.no_voter import NoVoter
from maker.voting.majority_voter import MajorityVoter
from maker.voting.first_to_k_voter import FirstToKVoter
from maker.executor.agent_runner import AgentRunner
from maker.red_flag.red_flagger import RedFlagger


def create_voter(strategy: str, runner: AgentRunner, red_flagger: RedFlagger) -> Voter:
    if strategy == "none":
        return NoVoter(runner=runner, red_flagger=red_flagger)
    elif strategy == "majority":
        return MajorityVoter(runner=runner, red_flagger=red_flagger)
    elif strategy == "first_to_k":
        return FirstToKVoter(runner=runner, red_flagger=red_flagger)
    else:
        raise ValueError(f"Unknown voting strategy: {strategy}")
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/voting/factory.py tests/test_voting/test_factory.py
git commit -m "feat: add voter factory"
```

---

## Task 3: Executor Module

**Files:**
- Create: `src/maker/executor/executor.py`
- Create: `tests/test_executor/test_executor.py`

**Step 1: Write tests**

```python
# tests/test_executor/test_executor.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from maker.executor.executor import ExecutorModule
from maker.core.events import (
    ValidationPassed, StepStarted, StepCompleted, StepFailed,
    TaskCompleted, TaskFailed, PlanCreated,
)
from maker.core.models import (
    Plan, PlanStep, TaskConfig, VoteResult, VotingSummary,
)
from maker.tools.registry import ToolRegistry
import time


def make_step(step_num, next_step=-1, task_type="action_step", **overrides):
    defaults = {
        "step": step_num,
        "task_type": task_type,
        "title": f"step_{step_num}",
        "task_description": f"Do step {step_num}",
        "primary_tools": ["Read"],
        "fallback_tools": [],
        "primary_tool_instructions": "",
        "fallback_tool_instructions": "",
        "input_variables": [f"step_{step_num-1}_output.data"] if step_num > 0 else [],
        "output_variable": f"step_{step_num}_output",
        "output_schema": "{data: string}",
        "next_step_sequence_number": next_step,
    }
    defaults.update(overrides)
    return PlanStep(**defaults)


def make_linear_plan(n_steps):
    steps = []
    for i in range(n_steps):
        next_step = i + 1 if i < n_steps - 1 else -1
        steps.append(make_step(i, next_step=next_step))
    return Plan(reasoning="test", steps=steps)


def make_vote_result(output=None):
    return VoteResult(
        winner=output or {"data": "result"},
        canonical_hash="abc",
        total_samples=1,
        red_flagged=0,
        vote_counts={"abc": 1},
    )


def make_config():
    return TaskConfig(instruction="test")


class TestExecutorModule:
    async def test_linear_plan_three_steps(self):
        """Execute a simple 3-step linear plan."""
        plan = make_linear_plan(3)
        config = make_config()

        executor = ExecutorModule(config=config, plan=plan)

        # Mock voter to always succeed
        mock_voter = AsyncMock()
        mock_voter.vote = AsyncMock(return_value=make_vote_result())
        executor._voter = mock_voter

        event = ValidationPassed(timestamp=time.time(), checks_passed=10)
        events = [e async for e in executor.process(event)]

        # Should emit: 3x (StepStarted + StepCompleted) + TaskCompleted
        step_started = [e for e in events if isinstance(e, StepStarted)]
        step_completed = [e for e in events if isinstance(e, StepCompleted)]
        task_completed = [e for e in events if isinstance(e, TaskCompleted)]

        assert len(step_started) == 3
        assert len(step_completed) == 3
        assert len(task_completed) == 1

    async def test_step_outputs_passed_to_next(self):
        """Each step should receive previous step outputs as context."""
        plan = make_linear_plan(2)
        config = make_config()

        executor = ExecutorModule(config=config, plan=plan)

        contexts_received = []

        async def mock_vote(step, context, config):
            contexts_received.append(context)
            return make_vote_result({"data": f"result_{step.step}"})

        mock_voter = AsyncMock()
        mock_voter.vote = mock_vote
        executor._voter = mock_voter

        event = ValidationPassed(timestamp=time.time(), checks_passed=10)
        _ = [e async for e in executor.process(event)]

        # Step 0: no context
        assert contexts_received[0] == ""
        # Step 1: should have step_0_output
        assert "step_0_output" in contexts_received[1]

    async def test_conditional_step_routing(self):
        """Conditional step should route to the step specified in output."""
        steps = [
            make_step(0, next_step=1),
            make_step(1, next_step=-2, task_type="conditional_step",
                     primary_tools=[], fallback_tools=[],
                     input_variables=["step_0_output.data"]),
            make_step(2, next_step=-1, title="branch_a"),
            make_step(3, next_step=-1, title="branch_b"),
        ]
        plan = Plan(reasoning="conditional", steps=steps)
        config = make_config()

        executor = ExecutorModule(config=config, plan=plan)

        call_count = 0

        async def mock_vote(step, context, config):
            nonlocal call_count
            call_count += 1
            if step.task_type == "conditional_step":
                return make_vote_result({"next_step": 3, "reason": "go to B"})
            return make_vote_result({"data": f"result_{step.step}"})

        mock_voter = AsyncMock()
        mock_voter.vote = mock_vote
        executor._voter = mock_voter

        event = ValidationPassed(timestamp=time.time(), checks_passed=10)
        events = [e async for e in executor.process(event)]

        completed_titles = [e.title for e in events if isinstance(e, StepCompleted)]
        # Should execute: step_0, step_1 (conditional), step_3 (branch_b)
        # Should NOT execute step_2 (branch_a)
        assert "branch_b" in completed_titles
        assert "branch_a" not in completed_titles

    async def test_step_failure_emits_task_failed(self):
        """If a step fails, TaskFailed should be emitted."""
        plan = make_linear_plan(2)
        config = make_config()

        executor = ExecutorModule(config=config, plan=plan)

        mock_voter = AsyncMock()
        mock_voter.vote = AsyncMock(side_effect=RuntimeError("all samples red-flagged"))
        executor._voter = mock_voter

        event = ValidationPassed(timestamp=time.time(), checks_passed=10)
        events = [e async for e in executor.process(event)]

        step_failed = [e for e in events if isinstance(e, StepFailed)]
        task_failed = [e for e in events if isinstance(e, TaskFailed)]

        assert len(step_failed) == 1
        assert len(task_failed) == 1
        assert step_failed[0].step == 0

    async def test_conditional_missing_next_step_fails(self):
        """Conditional step without next_step in output should fail."""
        steps = [
            make_step(0, next_step=1),
            make_step(1, next_step=-2, task_type="conditional_step",
                     primary_tools=[], fallback_tools=[]),
        ]
        plan = Plan(reasoning="test", steps=steps)
        config = make_config()

        executor = ExecutorModule(config=config, plan=plan)

        async def mock_vote(step, context, config):
            if step.task_type == "conditional_step":
                return make_vote_result({"reason": "missing next_step field"})
            return make_vote_result()

        mock_voter = AsyncMock()
        mock_voter.vote = mock_vote
        executor._voter = mock_voter

        event = ValidationPassed(timestamp=time.time(), checks_passed=10)
        events = [e async for e in executor.process(event)]

        step_failed = [e for e in events if isinstance(e, StepFailed)]
        assert len(step_failed) >= 1

    async def test_ignores_non_validation_passed_events(self):
        plan = make_linear_plan(1)
        config = make_config()
        executor = ExecutorModule(config=config, plan=plan)

        event = StepStarted(timestamp=time.time(), step=0, title="x")
        events = [e async for e in executor.process(event)]
        assert events == []

    async def test_task_completed_has_full_result(self):
        plan = make_linear_plan(1)
        config = make_config()

        executor = ExecutorModule(config=config, plan=plan)
        mock_voter = AsyncMock()
        mock_voter.vote = AsyncMock(return_value=make_vote_result({"answer": 42}))
        executor._voter = mock_voter

        event = ValidationPassed(timestamp=time.time(), checks_passed=10)
        events = [e async for e in executor.process(event)]

        task_completed = [e for e in events if isinstance(e, TaskCompleted)]
        assert len(task_completed) == 1
        assert task_completed[0].result["status"] == "completed"
        assert len(task_completed[0].result["steps"]) == 1
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement `src/maker/executor/executor.py`**

Key interface:

```python
from maker.core.module import Module
from maker.core.events import (
    ValidationPassed, StepStarted, StepCompleted, StepFailed,
    TaskCompleted, TaskFailed,
)
from maker.core.models import Plan, TaskConfig, VotingSummary
from maker.executor.context_builder import ContextBuilder
from maker.executor.result_collector import ResultCollector
from maker.voting.base import Voter
from typing import AsyncIterator
import time


class ExecutorModule(Module):
    def __init__(self, config: TaskConfig, plan: Plan):
        self._config = config
        self._plan = plan
        self._context_builder = ContextBuilder()
        self._step_outputs: dict[str, dict] = {}
        self._voter: Voter = None  # set externally or via factory

    async def process(self, event) -> AsyncIterator:
        if not isinstance(event, ValidationPassed):
            return

        collector = ResultCollector(instruction=self._config.instruction)
        step_map = {s.step: s for s in self._plan.steps}
        current_step_num = 0

        while current_step_num >= 0:
            step = step_map.get(current_step_num)
            if step is None:
                yield StepFailed(...)
                yield TaskFailed(...)
                return

            yield StepStarted(timestamp=time.time(), step=step.step, title=step.title)

            try:
                context = self._context_builder.build(step, self._step_outputs)
                vote_result = await self._voter.vote(step, context, self._config)
                self._step_outputs[step.output_variable] = vote_result.winner

                # Handle conditional routing
                if step.task_type == "conditional_step":
                    next_step = vote_result.winner.get("next_step")
                    if next_step is None:
                        yield StepFailed(...)
                        yield TaskFailed(...)
                        return
                    current_step_num = next_step
                else:
                    current_step_num = step.next_step_sequence_number

                # Emit step completed
                summary = VotingSummary(...)
                yield StepCompleted(...)
                collector.add_step(...)

            except Exception as e:
                yield StepFailed(...)
                yield TaskFailed(...)
                return

        yield TaskCompleted(
            timestamp=time.time(),
            result=collector.finalize(),
            total_cost_usd=...,
            total_duration_ms=...,
        )
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/executor/executor.py tests/test_executor/test_executor.py
git commit -m "feat: add executor module with step sequencing and conditional routing"
```

---

## Definition of Done

- [ ] `uv run pytest tests/test_executor/ tests/test_voting/test_factory.py -v` — all tests pass
- [ ] ResultCollector aggregates step outputs, costs, and durations
- [ ] ResultCollector produces correct final result dict
- [ ] Voter factory creates correct voter type from strategy string
- [ ] Executor runs linear multi-step plans
- [ ] Executor passes step outputs as context to subsequent steps
- [ ] Executor handles conditional step routing via `next_step` field
- [ ] Executor emits StepStarted, StepCompleted, StepFailed events
- [ ] Executor emits TaskCompleted with full result or TaskFailed on error
- [ ] Executor handles missing `next_step` in conditional output
- [ ] Executor ignores non-`ValidationPassed` events
- [ ] All code committed
