# Milestone 5: Validator Module

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the Validator module that checks plans against deterministic rules and optionally scores them with LLM quality checks.

**Architecture:** Two-layer validation: deterministic checks (always on, pass/fail) and LLM quality checks (optional, 0-1 scores). Each check is an independent function. Validator orchestrates all checks and emits `ValidationPassed` or `ValidationFailed`.

**Implementation note:** Quality prompts come in two flavors: per-step checks (`{step_yaml}`) and plan-level checks (`{plan_yaml}`). The `non_overlapping` and `appropriately_merged` checks are plan-level — they evaluate the whole plan at once rather than comparing step pairs. The quality checker dispatches to the correct prompt kwargs based on check type.

**Tech Stack:** Python 3.11+, `pytest`, `pytest-asyncio`

**Depends On:** M1 (models, events), M3 (tool registry for tool validation)

---

## Task 1: Deterministic Checks

**Files:**
- Create: `src/maker/validator/__init__.py`
- Create: `src/maker/validator/deterministic.py`
- Create: `tests/test_validator/__init__.py`
- Create: `tests/test_validator/test_deterministic.py`

**Step 1: Write tests**

```python
# tests/test_validator/test_deterministic.py
import pytest
from maker.validator.deterministic import (
    check_required_fields,
    check_step_numbering,
    check_task_type_valid,
    check_reasoning_present,
    check_tools_mutually_exclusive,
    check_tools_are_valid,
    check_conditional_step_no_tools,
    check_conditional_step_no_instructions,
    check_next_step_valid,
    check_conditional_returns_minus_2,
    check_final_step_returns_minus_1,
    check_no_orphan_steps,
    check_output_schema_exists,
    run_all_deterministic_checks,
    CheckResult,
)
from maker.core.models import Plan, PlanStep
from maker.tools.registry import ToolRegistry


def make_step(**overrides):
    """Create a valid action step with overrides."""
    defaults = {
        "step": 0,
        "task_type": "action_step",
        "title": "test_step",
        "task_description": "Do something",
        "primary_tools": ["Read"],
        "fallback_tools": [],
        "primary_tool_instructions": "Use Read",
        "fallback_tool_instructions": "",
        "input_variables": [],
        "output_variable": "step_0_output",
        "output_schema": "{result: string}",
        "next_step_sequence_number": -1,
    }
    defaults.update(overrides)
    return PlanStep(**defaults)


def make_plan(steps=None, reasoning="test reasoning"):
    if steps is None:
        steps = [make_step()]
    return Plan(reasoning=reasoning, steps=steps)


def make_registry():
    registry = ToolRegistry()
    registry.register_builtin("Read", "Read files")
    registry.register_builtin("Write", "Write files")
    registry.register_builtin("Bash", "Run commands")
    return registry


class TestRequiredFields:
    def test_valid_step_passes(self):
        plan = make_plan()
        result = check_required_fields(plan)
        assert result.passed

    def test_missing_output_schema(self):
        step = make_step(output_schema="")
        # output_schema exists but is empty — check_output_schema_exists handles this
        # check_required_fields only checks field presence on the dataclass
        plan = make_plan([step])
        result = check_required_fields(plan)
        assert result.passed  # field exists, just empty


class TestStepNumbering:
    def test_sequential_steps_pass(self):
        steps = [make_step(step=0, next_step_sequence_number=1),
                 make_step(step=1, next_step_sequence_number=-1)]
        result = check_step_numbering(make_plan(steps))
        assert result.passed

    def test_gap_in_numbering_fails(self):
        steps = [make_step(step=0, next_step_sequence_number=2),
                 make_step(step=2, next_step_sequence_number=-1)]
        result = check_step_numbering(make_plan(steps))
        assert not result.passed
        assert "gap" in result.message.lower() or "sequential" in result.message.lower()

    def test_not_starting_at_zero_fails(self):
        steps = [make_step(step=1, next_step_sequence_number=-1)]
        result = check_step_numbering(make_plan(steps))
        assert not result.passed

    def test_single_step_passes(self):
        result = check_step_numbering(make_plan())
        assert result.passed


class TestTaskTypeValid:
    def test_action_step_passes(self):
        result = check_task_type_valid(make_plan())
        assert result.passed

    def test_conditional_step_passes(self):
        step = make_step(task_type="conditional_step", primary_tools=[],
                        fallback_tools=[], primary_tool_instructions="",
                        fallback_tool_instructions="", next_step_sequence_number=-2)
        result = check_task_type_valid(make_plan([step]))
        assert result.passed

    def test_invalid_type_fails(self):
        step = make_step(task_type="invalid_type")
        result = check_task_type_valid(make_plan([step]))
        assert not result.passed


class TestReasoningPresent:
    def test_reasoning_present(self):
        result = check_reasoning_present(make_plan())
        assert result.passed

    def test_empty_reasoning_fails(self):
        result = check_reasoning_present(make_plan(reasoning=""))
        assert not result.passed

    def test_whitespace_reasoning_fails(self):
        result = check_reasoning_present(make_plan(reasoning="   "))
        assert not result.passed


class TestToolsMutuallyExclusive:
    def test_no_overlap_passes(self):
        step = make_step(primary_tools=["Read"], fallback_tools=["Write"])
        result = check_tools_mutually_exclusive(make_plan([step]))
        assert result.passed

    def test_overlap_fails(self):
        step = make_step(primary_tools=["Read", "Write"], fallback_tools=["Read"])
        result = check_tools_mutually_exclusive(make_plan([step]))
        assert not result.passed

    def test_both_empty_passes(self):
        step = make_step(primary_tools=[], fallback_tools=[])
        result = check_tools_mutually_exclusive(make_plan([step]))
        assert result.passed


class TestToolsAreValid:
    def test_valid_tools_pass(self):
        registry = make_registry()
        step = make_step(primary_tools=["Read"], fallback_tools=["Write"])
        result = check_tools_are_valid(make_plan([step]), registry)
        assert result.passed

    def test_invalid_tool_fails(self):
        registry = make_registry()
        step = make_step(primary_tools=["FakeTool"])
        result = check_tools_are_valid(make_plan([step]), registry)
        assert not result.passed
        assert "FakeTool" in result.message

    def test_empty_tools_pass(self):
        registry = make_registry()
        step = make_step(primary_tools=[], fallback_tools=[])
        result = check_tools_are_valid(make_plan([step]), registry)
        assert result.passed


class TestConditionalStepNoTools:
    def test_conditional_with_empty_tools_passes(self):
        step = make_step(task_type="conditional_step", primary_tools=[],
                        fallback_tools=[], primary_tool_instructions="",
                        fallback_tool_instructions="", next_step_sequence_number=-2)
        result = check_conditional_step_no_tools(make_plan([step]))
        assert result.passed

    def test_conditional_with_primary_tools_fails(self):
        step = make_step(task_type="conditional_step", primary_tools=["Read"],
                        fallback_tools=[], primary_tool_instructions="",
                        fallback_tool_instructions="", next_step_sequence_number=-2)
        result = check_conditional_step_no_tools(make_plan([step]))
        assert not result.passed

    def test_action_step_with_tools_passes(self):
        """Action steps CAN have tools — this check only applies to conditional."""
        step = make_step(primary_tools=["Read"])
        result = check_conditional_step_no_tools(make_plan([step]))
        assert result.passed


class TestConditionalStepNoInstructions:
    def test_conditional_with_empty_instructions_passes(self):
        step = make_step(task_type="conditional_step", primary_tools=[],
                        fallback_tools=[], primary_tool_instructions="",
                        fallback_tool_instructions="", next_step_sequence_number=-2)
        result = check_conditional_step_no_instructions(make_plan([step]))
        assert result.passed

    def test_conditional_with_instructions_fails(self):
        step = make_step(task_type="conditional_step", primary_tools=[],
                        fallback_tools=[],
                        primary_tool_instructions="Use something",
                        fallback_tool_instructions="",
                        next_step_sequence_number=-2)
        result = check_conditional_step_no_instructions(make_plan([step]))
        assert not result.passed


class TestNextStepValid:
    def test_valid_next_step(self):
        steps = [make_step(step=0, next_step_sequence_number=1),
                 make_step(step=1, next_step_sequence_number=-1)]
        result = check_next_step_valid(make_plan(steps))
        assert result.passed

    def test_minus_1_is_valid(self):
        result = check_next_step_valid(make_plan())
        assert result.passed

    def test_minus_2_is_valid(self):
        step = make_step(next_step_sequence_number=-2, task_type="conditional_step",
                        primary_tools=[], fallback_tools=[],
                        primary_tool_instructions="", fallback_tool_instructions="")
        result = check_next_step_valid(make_plan([step]))
        assert result.passed

    def test_nonexistent_step_fails(self):
        step = make_step(next_step_sequence_number=5)
        result = check_next_step_valid(make_plan([step]))
        assert not result.passed


class TestConditionalReturnsMinus2:
    def test_conditional_with_minus_2_passes(self):
        step = make_step(task_type="conditional_step", primary_tools=[],
                        fallback_tools=[], primary_tool_instructions="",
                        fallback_tool_instructions="", next_step_sequence_number=-2)
        result = check_conditional_returns_minus_2(make_plan([step]))
        assert result.passed

    def test_conditional_with_other_value_fails(self):
        step = make_step(task_type="conditional_step", primary_tools=[],
                        fallback_tools=[], primary_tool_instructions="",
                        fallback_tool_instructions="", next_step_sequence_number=1)
        result = check_conditional_returns_minus_2(make_plan([step]))
        assert not result.passed


class TestFinalStepReturnsMinus1:
    def test_final_step_with_minus_1_passes(self):
        result = check_final_step_returns_minus_1(make_plan())
        assert result.passed

    def test_final_step_without_minus_1_fails(self):
        step = make_step(next_step_sequence_number=1)
        result = check_final_step_returns_minus_1(make_plan([step]))
        assert not result.passed

    def test_conditional_final_step_ok(self):
        """A conditional step can be the last step (routes dynamically)."""
        steps = [
            make_step(step=0, next_step_sequence_number=1),
            make_step(step=1, task_type="conditional_step", primary_tools=[],
                     fallback_tools=[], primary_tool_instructions="",
                     fallback_tool_instructions="", next_step_sequence_number=-2),
        ]
        result = check_final_step_returns_minus_1(make_plan(steps))
        assert result.passed  # conditional steps exempt


class TestNoOrphanSteps:
    def test_all_reachable_passes(self):
        steps = [make_step(step=0, next_step_sequence_number=1),
                 make_step(step=1, next_step_sequence_number=-1)]
        result = check_no_orphan_steps(make_plan(steps))
        assert result.passed

    def test_orphan_step_fails(self):
        steps = [
            make_step(step=0, next_step_sequence_number=-1),  # ends here
            make_step(step=1, next_step_sequence_number=-1),  # orphan
        ]
        result = check_no_orphan_steps(make_plan(steps))
        assert not result.passed

    def test_single_step_passes(self):
        result = check_no_orphan_steps(make_plan())
        assert result.passed


class TestOutputSchemaExists:
    def test_non_empty_schema_passes(self):
        result = check_output_schema_exists(make_plan())
        assert result.passed

    def test_empty_schema_fails(self):
        step = make_step(output_schema="")
        result = check_output_schema_exists(make_plan([step]))
        assert not result.passed

    def test_whitespace_schema_fails(self):
        step = make_step(output_schema="   ")
        result = check_output_schema_exists(make_plan([step]))
        assert not result.passed


class TestRunAllChecks:
    def test_valid_plan_passes_all(self):
        registry = make_registry()
        plan = make_plan()
        results = run_all_deterministic_checks(plan, registry)
        assert all(r.passed for r in results)

    def test_invalid_plan_has_failures(self):
        registry = make_registry()
        step = make_step(primary_tools=["FakeTool"], task_type="invalid")
        plan = make_plan([step])
        results = run_all_deterministic_checks(plan, registry)
        failed = [r for r in results if not r.passed]
        assert len(failed) >= 2  # at least task_type and tools_are_valid


class TestCheckResult:
    def test_passed_result(self):
        result = CheckResult(name="test", passed=True, message="OK")
        assert result.passed
        assert result.name == "test"

    def test_failed_result(self):
        result = CheckResult(name="test", passed=False, message="Bad")
        assert not result.passed
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement `src/maker/validator/deterministic.py`**

Key interface:

```python
from dataclasses import dataclass
from maker.core.models import Plan
from maker.tools.registry import ToolRegistry


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str


def check_required_fields(plan: Plan) -> CheckResult: ...
def check_step_numbering(plan: Plan) -> CheckResult: ...
def check_task_type_valid(plan: Plan) -> CheckResult: ...
def check_reasoning_present(plan: Plan) -> CheckResult: ...
def check_tools_mutually_exclusive(plan: Plan) -> CheckResult: ...
def check_tools_are_valid(plan: Plan, registry: ToolRegistry) -> CheckResult: ...
def check_conditional_step_no_tools(plan: Plan) -> CheckResult: ...
def check_conditional_step_no_instructions(plan: Plan) -> CheckResult: ...
def check_next_step_valid(plan: Plan) -> CheckResult: ...
def check_conditional_returns_minus_2(plan: Plan) -> CheckResult: ...
def check_final_step_returns_minus_1(plan: Plan) -> CheckResult: ...
def check_no_orphan_steps(plan: Plan) -> CheckResult: ...
def check_output_schema_exists(plan: Plan) -> CheckResult: ...

def run_all_deterministic_checks(plan: Plan, registry: ToolRegistry) -> list[CheckResult]:
    """Run all deterministic checks and return results."""
    ...
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/validator/ tests/test_validator/
git commit -m "feat: add deterministic plan validation checks"
```

---

## Task 2: LLM Quality Checks (Optional)

**Files:**
- Create: `src/maker/validator/quality.py`
- Create: `tests/test_validator/test_quality.py`

**Step 1: Write tests**

```python
# tests/test_validator/test_quality.py
import pytest
from unittest.mock import AsyncMock, patch
from maker.validator.quality import (
    QualityChecker,
    QualityResult,
)
from maker.core.models import Plan, PlanStep


def make_step(**overrides):
    defaults = {
        "step": 0, "task_type": "action_step", "title": "test",
        "task_description": "Do one thing", "primary_tools": ["Read"],
        "fallback_tools": [], "primary_tool_instructions": "Use Read",
        "fallback_tool_instructions": "", "input_variables": [],
        "output_variable": "step_0_output", "output_schema": "{r: string}",
        "next_step_sequence_number": -1,
    }
    defaults.update(overrides)
    return PlanStep(**defaults)


def make_plan(steps=None):
    return Plan(reasoning="test", steps=steps or [make_step()])


class TestQualityChecker:
    async def test_all_checks_return_scores(self):
        """Each quality check returns a QualityResult with a 0-1 score."""
        checker = QualityChecker()

        # Mock LLM to always return a score
        async def mock_score(prompt):
            return 0.9

        checker._call_llm_for_score = mock_score

        plan = make_plan()
        results = await checker.run_all(plan)
        assert len(results) == 6  # 6 quality dimensions
        for r in results:
            assert 0.0 <= r.score <= 1.0
            assert isinstance(r.name, str)

    async def test_check_names(self):
        checker = QualityChecker()
        checker._call_llm_for_score = AsyncMock(return_value=0.8)

        results = await checker.run_all(make_plan())
        names = {r.name for r in results}
        expected = {
            "single_purpose", "self_contained", "max_k_tools",
            "non_overlapping", "maximally_decomposed", "appropriately_merged",
        }
        assert names == expected

    async def test_weighted_aggregate_score(self):
        checker = QualityChecker()
        checker._call_llm_for_score = AsyncMock(return_value=1.0)

        results = await checker.run_all(make_plan())
        aggregate = checker.aggregate_score(results)
        assert aggregate == 1.0

    async def test_low_scores(self):
        checker = QualityChecker()
        checker._call_llm_for_score = AsyncMock(return_value=0.3)

        results = await checker.run_all(make_plan())
        aggregate = checker.aggregate_score(results)
        assert aggregate == pytest.approx(0.3)


class TestQualityResult:
    def test_creation(self):
        result = QualityResult(name="single_purpose", score=0.85, details="Good")
        assert result.name == "single_purpose"
        assert result.score == 0.85
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement `src/maker/validator/quality.py`**

```python
from dataclasses import dataclass
from maker.core.models import Plan, PlanStep
from maker.prompts import load_prompt

DEFAULT_MAX_K = 5

# Plan-level checks use {plan_yaml}; per-step checks use {step_yaml}
_PLAN_LEVEL_CHECKS = {"non_overlapping", "appropriately_merged"}
_EXTRA_KWARGS = {"max_k_tools": {"max_k": DEFAULT_MAX_K}}


@dataclass
class QualityResult:
    name: str
    score: float  # 0.0 - 1.0
    details: str


class QualityChecker:
    CHECKS = [
        "single_purpose", "self_contained", "max_k_tools",
        "non_overlapping", "maximally_decomposed", "appropriately_merged",
    ]

    async def run_all(self, plan: Plan) -> list[QualityResult]: ...
    def aggregate_score(self, results: list[QualityResult]) -> float: ...
    async def _call_llm_for_score(self, prompt: str) -> float: ...

def _build_prompt(check_name: str, plan: Plan) -> str:
    """Dispatches to plan_yaml for plan-level checks, step_yaml for per-step."""
    ...
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/validator/quality.py tests/test_validator/test_quality.py
git commit -m "feat: add LLM quality checks for plan validation"
```

---

## Task 3: Validator Module

**Files:**
- Create: `src/maker/validator/validator.py`
- Create: `tests/test_validator/test_validator.py`

**Step 1: Write tests**

```python
# tests/test_validator/test_validator.py
import pytest
from unittest.mock import AsyncMock
from maker.validator.validator import ValidatorModule
from maker.core.events import PlanCreated, ValidationPassed, ValidationFailed
from maker.core.models import Plan, PlanStep, TaskConfig
from maker.tools.registry import ToolRegistry
import time


def make_valid_plan():
    steps = [
        PlanStep(
            step=0, task_type="action_step", title="fetch",
            task_description="Fetch data", primary_tools=["Read"],
            fallback_tools=[], primary_tool_instructions="Use Read",
            fallback_tool_instructions="", input_variables=[],
            output_variable="step_0_output",
            output_schema="{data: string}",
            next_step_sequence_number=-1,
        )
    ]
    return Plan(reasoning="Simple plan", steps=steps)


def make_registry():
    r = ToolRegistry()
    r.register_builtin("Read", "Read files")
    return r


class TestValidatorModule:
    async def test_valid_plan_emits_passed(self):
        registry = make_registry()
        config = TaskConfig(instruction="test")
        validator = ValidatorModule(registry=registry, config=config)

        event = PlanCreated(timestamp=time.time(), plan=make_valid_plan())
        events = [e async for e in validator.process(event)]

        assert len(events) == 1
        assert isinstance(events[0], ValidationPassed)
        assert events[0].checks_passed > 0

    async def test_invalid_plan_emits_failed(self):
        registry = make_registry()
        config = TaskConfig(instruction="test")
        validator = ValidatorModule(registry=registry, config=config)

        bad_plan = Plan(
            reasoning="",  # empty reasoning
            steps=[
                PlanStep(
                    step=1,  # doesn't start at 0
                    task_type="bad_type",
                    title="t", task_description="d",
                    primary_tools=["FakeTool"], fallback_tools=[],
                    primary_tool_instructions="", fallback_tool_instructions="",
                    input_variables=[], output_variable="step_1_output",
                    output_schema="", next_step_sequence_number=-1,
                )
            ],
        )
        event = PlanCreated(timestamp=time.time(), plan=bad_plan)
        events = [e async for e in validator.process(event)]

        assert len(events) == 1
        assert isinstance(events[0], ValidationFailed)
        assert len(events[0].errors) > 0

    async def test_quality_checks_off_by_default(self):
        """Quality checks should not run unless enabled."""
        registry = make_registry()
        config = TaskConfig(instruction="test", enable_quality_checks=False)
        validator = ValidatorModule(registry=registry, config=config)

        event = PlanCreated(timestamp=time.time(), plan=make_valid_plan())
        events = [e async for e in validator.process(event)]

        assert isinstance(events[0], ValidationPassed)
        # No quality scores in output since disabled

    async def test_ignores_non_plan_created_events(self):
        from maker.core.events import StepStarted
        registry = make_registry()
        config = TaskConfig(instruction="test")
        validator = ValidatorModule(registry=registry, config=config)

        event = StepStarted(timestamp=time.time(), step=0, title="x")
        events = [e async for e in validator.process(event)]
        assert events == []
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement `src/maker/validator/validator.py`**

```python
from maker.core.module import Module
from maker.core.events import PlanCreated, ValidationPassed, ValidationFailed
from maker.core.models import TaskConfig
from maker.validator.deterministic import run_all_deterministic_checks
from maker.validator.quality import QualityChecker
from maker.tools.registry import ToolRegistry
from typing import AsyncIterator
import time


class ValidatorModule(Module):
    def __init__(self, registry: ToolRegistry, config: TaskConfig):
        self._registry = registry
        self._config = config
        self._quality_checker = QualityChecker()

    async def process(self, event) -> AsyncIterator:
        if not isinstance(event, PlanCreated):
            return

        # Layer 1: Deterministic checks (always)
        results = run_all_deterministic_checks(event.plan, self._registry)
        failures = [r for r in results if not r.passed]

        if failures:
            yield ValidationFailed(
                timestamp=time.time(),
                errors=[{"check": r.name, "message": r.message} for r in failures],
            )
            return

        # Layer 2: Quality checks (optional)
        if self._config.enable_quality_checks:
            quality_results = await self._quality_checker.run_all(event.plan)
            # ... handle quality scoring

        yield ValidationPassed(
            timestamp=time.time(),
            checks_passed=len(results),
        )
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/validator/validator.py tests/test_validator/test_validator.py
git commit -m "feat: add validator module orchestrating checks"
```

---

## Definition of Done

- [ ] `uv run pytest tests/test_validator/ -v` — all tests pass
- [ ] Each deterministic check tested independently with valid and invalid inputs
- [ ] `check_required_fields` validates all 12 required fields
- [ ] `check_step_numbering` catches gaps, non-zero starts
- [ ] `check_task_type_valid` rejects unknown types
- [ ] `check_tools_mutually_exclusive` catches overlap
- [ ] `check_tools_are_valid` validates against registry
- [ ] `check_conditional_step_no_tools` enforces empty tools on conditionals
- [ ] `check_next_step_valid` catches dangling references
- [ ] `check_no_orphan_steps` catches unreachable steps
- [ ] `check_output_schema_exists` catches empty schemas
- [ ] `run_all_deterministic_checks` aggregates all results
- [ ] `ValidatorModule` emits `ValidationPassed` for valid plans
- [ ] `ValidatorModule` emits `ValidationFailed` with error details for invalid plans
- [ ] Quality checks can be enabled/disabled via config
- [ ] Quality prompts use `{plan_yaml}` for plan-level checks, `{step_yaml}` for per-step checks
- [ ] All code committed
