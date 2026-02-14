# Milestone 7: Voting System

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the output canonicalization and three voting strategies: NoVoter (single agent), MajorityVoter (N agents, majority wins), FirstToKVoter (leader - runner_up >= K).

**Architecture:** `Voter` ABC with three implementations. All voters use `Canonicalizer` for output comparison and `RedFlagger` for sample filtering. Voters own the loop of calling `AgentRunner` and collecting samples.

**Tech Stack:** Python 3.11+, `pytest`, `pytest-asyncio`

**Depends On:** M1 (models, events), M6 (AgentRunner, RedFlagger)

---

## Task 1: Canonicalizer

**Files:**
- Create: `src/maker/voting/__init__.py`
- Create: `src/maker/voting/canonicalizer.py`
- Create: `tests/test_voting/__init__.py`
- Create: `tests/test_voting/test_canonicalizer.py`

**Step 1: Write tests**

```python
# tests/test_voting/test_canonicalizer.py
import pytest
from maker.voting.canonicalizer import Canonicalizer


class TestCanonicalize:
    def test_sorts_keys(self):
        canon = Canonicalizer()
        d1 = {"b": 1, "a": 2}
        d2 = {"a": 2, "b": 1}
        assert canon.canonicalize(d1) == canon.canonicalize(d2)

    def test_nested_keys_sorted(self):
        canon = Canonicalizer()
        d1 = {"outer": {"z": 1, "a": 2}}
        d2 = {"outer": {"a": 2, "z": 1}}
        assert canon.canonicalize(d1) == canon.canonicalize(d2)

    def test_deeply_nested_keys_sorted(self):
        canon = Canonicalizer()
        d1 = {"a": {"b": {"d": 1, "c": 2}}}
        d2 = {"a": {"b": {"c": 2, "d": 1}}}
        assert canon.canonicalize(d1) == canon.canonicalize(d2)

    def test_different_values_differ(self):
        canon = Canonicalizer()
        d1 = {"key": "value1"}
        d2 = {"key": "value2"}
        assert canon.canonicalize(d1) != canon.canonicalize(d2)

    def test_different_keys_differ(self):
        canon = Canonicalizer()
        d1 = {"a": 1}
        d2 = {"b": 1}
        assert canon.canonicalize(d1) != canon.canonicalize(d2)

    def test_extra_key_differs(self):
        canon = Canonicalizer()
        d1 = {"a": 1}
        d2 = {"a": 1, "b": 2}
        assert canon.canonicalize(d1) != canon.canonicalize(d2)

    def test_whitespace_in_strings_preserved(self):
        """String values with different whitespace should be different."""
        canon = Canonicalizer()
        d1 = {"text": "hello world"}
        d2 = {"text": "hello  world"}
        assert canon.canonicalize(d1) != canon.canonicalize(d2)

    def test_list_order_preserved(self):
        """Lists are NOT sorted — order matters."""
        canon = Canonicalizer()
        d1 = {"items": [1, 2, 3]}
        d2 = {"items": [3, 2, 1]}
        assert canon.canonicalize(d1) != canon.canonicalize(d2)

    def test_list_with_dicts_sorted_keys(self):
        canon = Canonicalizer()
        d1 = {"items": [{"b": 1, "a": 2}]}
        d2 = {"items": [{"a": 2, "b": 1}]}
        assert canon.canonicalize(d1) == canon.canonicalize(d2)

    def test_none_values(self):
        canon = Canonicalizer()
        d1 = {"key": None}
        d2 = {"key": None}
        assert canon.canonicalize(d1) == canon.canonicalize(d2)

    def test_boolean_values(self):
        canon = Canonicalizer()
        d1 = {"flag": True}
        d2 = {"flag": True}
        assert canon.canonicalize(d1) == canon.canonicalize(d2)
        assert canon.canonicalize(d1) != canon.canonicalize({"flag": False})

    def test_numeric_types(self):
        canon = Canonicalizer()
        d1 = {"count": 42}
        d2 = {"count": 42}
        assert canon.canonicalize(d1) == canon.canonicalize(d2)

    def test_empty_dict(self):
        canon = Canonicalizer()
        assert canon.canonicalize({}) == canon.canonicalize({})

    def test_returns_string(self):
        canon = Canonicalizer()
        result = canon.canonicalize({"key": "value"})
        assert isinstance(result, str)


class TestCanonicalHash:
    def test_same_content_same_hash(self):
        canon = Canonicalizer()
        d1 = {"b": 1, "a": 2}
        d2 = {"a": 2, "b": 1}
        assert canon.hash(d1) == canon.hash(d2)

    def test_different_content_different_hash(self):
        canon = Canonicalizer()
        assert canon.hash({"a": 1}) != canon.hash({"a": 2})

    def test_hash_is_string(self):
        canon = Canonicalizer()
        assert isinstance(canon.hash({"a": 1}), str)
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement `src/maker/voting/canonicalizer.py`**

```python
import json
import hashlib


class Canonicalizer:
    def canonicalize(self, data: dict) -> str:
        """Convert dict to canonical JSON string with sorted keys."""
        normalized = self._sort_keys_recursive(data)
        return json.dumps(normalized, sort_keys=True, ensure_ascii=True, separators=(",", ":"))

    def hash(self, data: dict) -> str:
        """Return a hash of the canonical representation."""
        canonical = self.canonicalize(data)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def _sort_keys_recursive(self, obj):
        """Recursively sort dict keys. Lists maintain order but dicts inside them are sorted."""
        if isinstance(obj, dict):
            return {k: self._sort_keys_recursive(v) for k, v in sorted(obj.items())}
        elif isinstance(obj, list):
            return [self._sort_keys_recursive(item) for item in obj]
        return obj
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/voting/ tests/test_voting/
git commit -m "feat: add output canonicalizer for vote comparison"
```

---

## Task 2: Voter ABC + NoVoter

**Files:**
- Create: `src/maker/voting/base.py`
- Create: `src/maker/voting/no_voter.py`
- Create: `tests/test_voting/test_no_voter.py`

**Step 1: Write tests**

```python
# tests/test_voting/test_no_voter.py
import pytest
from unittest.mock import AsyncMock
from maker.voting.no_voter import NoVoter
from maker.core.models import AgentResult, PlanStep, TaskConfig, VoteResult
from maker.executor.agent_runner import AgentRunner
from maker.red_flag.red_flagger import RedFlagger


def make_step():
    return PlanStep(
        step=0, task_type="action_step", title="test",
        task_description="Do", primary_tools=["Read"], fallback_tools=[],
        primary_tool_instructions="", fallback_tool_instructions="",
        input_variables=[], output_variable="step_0_output",
        output_schema="{r: string}", next_step_sequence_number=-1,
    )


def make_config():
    return TaskConfig(instruction="test", step_max_retries=2)


def make_agent_result(output=None, error=None):
    return AgentResult(
        output=output or {"result": "ok"},
        raw_response="result: ok",
        was_repaired=False, tokens=100,
        cost_usd=0.001, duration_ms=500,
        error=error,
    )


class TestNoVoter:
    async def test_returns_single_result(self):
        runner = AsyncMock(spec=AgentRunner)
        runner.run = AsyncMock(return_value=make_agent_result())

        voter = NoVoter(runner=runner, red_flagger=RedFlagger())
        result = await voter.vote(make_step(), context="", config=make_config())

        assert isinstance(result, VoteResult)
        assert result.winner == {"result": "ok"}
        assert result.total_samples == 1
        assert result.red_flagged == 0

    async def test_retries_on_red_flag(self):
        runner = AsyncMock(spec=AgentRunner)
        runner.run = AsyncMock(side_effect=[
            make_agent_result(output="not a dict"),  # red-flagged
            make_agent_result(output={"result": "ok"}),  # valid
        ])

        voter = NoVoter(runner=runner, red_flagger=RedFlagger())
        result = await voter.vote(make_step(), context="", config=make_config())

        assert result.winner == {"result": "ok"}
        assert result.total_samples == 2
        assert result.red_flagged == 1

    async def test_fails_after_max_retries(self):
        runner = AsyncMock(spec=AgentRunner)
        runner.run = AsyncMock(return_value=make_agent_result(error="crash"))

        config = make_config()
        config.step_max_retries = 2

        voter = NoVoter(runner=runner, red_flagger=RedFlagger())

        with pytest.raises(RuntimeError, match="retries"):
            await voter.vote(make_step(), context="", config=config)

    async def test_retries_on_error(self):
        runner = AsyncMock(spec=AgentRunner)
        runner.run = AsyncMock(side_effect=[
            make_agent_result(error="transient error"),
            make_agent_result(output={"result": "ok"}),
        ])

        voter = NoVoter(runner=runner, red_flagger=RedFlagger())
        result = await voter.vote(make_step(), context="", config=make_config())

        assert result.winner == {"result": "ok"}
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement**

`src/maker/voting/base.py`:
```python
from abc import ABC, abstractmethod
from maker.core.models import PlanStep, VoteResult, TaskConfig
from maker.executor.agent_runner import AgentRunner


class Voter(ABC):
    @abstractmethod
    async def vote(self, step: PlanStep, context: str, config: TaskConfig) -> VoteResult:
        """Run agent(s) and return the winning output."""
        ...
```

`src/maker/voting/no_voter.py`:
```python
from maker.voting.base import Voter
from maker.core.models import PlanStep, VoteResult, TaskConfig
from maker.executor.agent_runner import AgentRunner
from maker.red_flag.red_flagger import RedFlagger
from maker.voting.canonicalizer import Canonicalizer


class NoVoter(Voter):
    def __init__(self, runner: AgentRunner, red_flagger: RedFlagger):
        self._runner = runner
        self._red_flagger = red_flagger
        self._canonicalizer = Canonicalizer()

    async def vote(self, step: PlanStep, context: str, config: TaskConfig) -> VoteResult:
        """Run 1 agent with retries. No voting — just get one valid result."""
        ...
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/voting/base.py src/maker/voting/no_voter.py tests/test_voting/test_no_voter.py
git commit -m "feat: add Voter ABC and NoVoter (single-agent strategy)"
```

---

## Task 3: MajorityVoter

**Files:**
- Create: `src/maker/voting/majority_voter.py`
- Create: `tests/test_voting/test_majority_voter.py`

**Step 1: Write tests**

```python
# tests/test_voting/test_majority_voter.py
import pytest
from unittest.mock import AsyncMock
from maker.voting.majority_voter import MajorityVoter
from maker.core.models import AgentResult, PlanStep, TaskConfig, VoteResult
from maker.executor.agent_runner import AgentRunner
from maker.red_flag.red_flagger import RedFlagger


def make_step():
    return PlanStep(
        step=0, task_type="action_step", title="test",
        task_description="Do", primary_tools=["Read"], fallback_tools=[],
        primary_tool_instructions="", fallback_tool_instructions="",
        input_variables=[], output_variable="step_0_output",
        output_schema="{r: string}", next_step_sequence_number=-1,
    )


def make_config(voting_n=3, max_voting_samples=10):
    return TaskConfig(
        instruction="test", voting_strategy="majority",
        voting_n=voting_n, max_voting_samples=max_voting_samples,
    )


def make_result(output):
    return AgentResult(
        output=output, raw_response="", was_repaired=False,
        tokens=100, cost_usd=0.001, duration_ms=500,
    )


class TestMajorityVoter:
    async def test_unanimous_agreement(self):
        runner = AsyncMock(spec=AgentRunner)
        runner.run = AsyncMock(return_value=make_result({"answer": 42}))

        voter = MajorityVoter(runner=runner, red_flagger=RedFlagger())
        result = await voter.vote(make_step(), context="", config=make_config(voting_n=3))

        assert result.winner == {"answer": 42}
        assert result.total_samples == 3
        assert result.red_flagged == 0

    async def test_two_vs_one_majority(self):
        runner = AsyncMock(spec=AgentRunner)
        runner.run = AsyncMock(side_effect=[
            make_result({"answer": 42}),
            make_result({"answer": 42}),
            make_result({"answer": 99}),
        ])

        voter = MajorityVoter(runner=runner, red_flagger=RedFlagger())
        result = await voter.vote(make_step(), context="", config=make_config(voting_n=3))

        assert result.winner == {"answer": 42}

    async def test_key_order_doesnt_split_votes(self):
        """Canonicalization: same content, different key order = same vote."""
        runner = AsyncMock(spec=AgentRunner)
        runner.run = AsyncMock(side_effect=[
            make_result({"b": 2, "a": 1}),
            make_result({"a": 1, "b": 2}),  # same content, different order
            make_result({"c": 3}),           # different
        ])

        voter = MajorityVoter(runner=runner, red_flagger=RedFlagger())
        result = await voter.vote(make_step(), context="", config=make_config(voting_n=3))

        assert result.winner == {"a": 1, "b": 2}  # or {"b": 2, "a": 1}
        assert result.vote_counts  # should show 2 vs 1

    async def test_no_majority_runs_more_samples(self):
        """If initial N has no majority, run more until one emerges."""
        call_count = 0

        async def run_agent(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                # 3-way split
                return make_result({"v": call_count})
            else:
                # Eventually converge
                return make_result({"v": 1})

        runner = AsyncMock(spec=AgentRunner)
        runner.run = AsyncMock(side_effect=run_agent)

        voter = MajorityVoter(runner=runner, red_flagger=RedFlagger())
        result = await voter.vote(make_step(), context="", config=make_config(voting_n=3))

        assert result.winner == {"v": 1}
        assert result.total_samples > 3

    async def test_respects_max_voting_samples(self):
        """If max_voting_samples reached without majority, fail."""
        call_count = 0

        async def run_agent(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return make_result({"v": call_count})  # all different

        runner = AsyncMock(spec=AgentRunner)
        runner.run = AsyncMock(side_effect=run_agent)

        voter = MajorityVoter(runner=runner, red_flagger=RedFlagger())
        config = make_config(voting_n=3, max_voting_samples=5)

        with pytest.raises(RuntimeError, match="no majority"):
            await voter.vote(make_step(), context="", config=config)

    async def test_red_flagged_samples_excluded(self):
        runner = AsyncMock(spec=AgentRunner)
        runner.run = AsyncMock(side_effect=[
            make_result("not a dict"),        # red-flagged
            make_result({"answer": 42}),      # valid
            make_result({"answer": 42}),      # valid
            make_result({"answer": 42}),      # valid (replacing red-flagged)
        ])

        voter = MajorityVoter(runner=runner, red_flagger=RedFlagger())
        result = await voter.vote(make_step(), context="", config=make_config(voting_n=3))

        assert result.winner == {"answer": 42}
        assert result.red_flagged >= 1
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement `src/maker/voting/majority_voter.py`**

```python
from maker.voting.base import Voter
from maker.core.models import PlanStep, VoteResult, TaskConfig
from maker.executor.agent_runner import AgentRunner
from maker.red_flag.red_flagger import RedFlagger
from maker.voting.canonicalizer import Canonicalizer


class MajorityVoter(Voter):
    def __init__(self, runner: AgentRunner, red_flagger: RedFlagger):
        self._runner = runner
        self._red_flagger = red_flagger
        self._canonicalizer = Canonicalizer()

    async def vote(self, step: PlanStep, context: str, config: TaskConfig) -> VoteResult:
        """Run N agents, take majority. If no majority, run more up to max_voting_samples."""
        ...
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/voting/majority_voter.py tests/test_voting/test_majority_voter.py
git commit -m "feat: add MajorityVoter with canonicalized comparison"
```

---

## Task 4: FirstToKVoter

**Files:**
- Create: `src/maker/voting/first_to_k_voter.py`
- Create: `tests/test_voting/test_first_to_k_voter.py`

**Step 1: Write tests**

```python
# tests/test_voting/test_first_to_k_voter.py
import pytest
from unittest.mock import AsyncMock
from maker.voting.first_to_k_voter import FirstToKVoter
from maker.core.models import AgentResult, PlanStep, TaskConfig, VoteResult
from maker.executor.agent_runner import AgentRunner
from maker.red_flag.red_flagger import RedFlagger


def make_step():
    return PlanStep(
        step=0, task_type="action_step", title="test",
        task_description="Do", primary_tools=["Read"], fallback_tools=[],
        primary_tool_instructions="", fallback_tool_instructions="",
        input_variables=[], output_variable="step_0_output",
        output_schema="{r: string}", next_step_sequence_number=-1,
    )


def make_config(voting_k=2, max_voting_samples=10):
    return TaskConfig(
        instruction="test", voting_strategy="first_to_k",
        voting_k=voting_k, max_voting_samples=max_voting_samples,
    )


def make_result(output):
    return AgentResult(
        output=output, raw_response="", was_repaired=False,
        tokens=100, cost_usd=0.001, duration_ms=500,
    )


class TestFirstToKVoter:
    async def test_quick_consensus_k2(self):
        """With K=2, need leader_count - runner_up_count >= 2.
        Two identical results with 0 for any other → 2-0 >= 2 → win."""
        runner = AsyncMock(spec=AgentRunner)
        runner.run = AsyncMock(return_value=make_result({"answer": 42}))

        voter = FirstToKVoter(runner=runner, red_flagger=RedFlagger())
        result = await voter.vote(make_step(), context="", config=make_config(voting_k=2))

        assert result.winner == {"answer": 42}
        assert result.total_samples == 2  # 2-0 >= 2

    async def test_competing_answers_need_more_samples(self):
        """Two competing answers: need K-ahead to declare winner."""
        call_count = 0

        async def run_agent(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count in [1, 3, 4]:
                return make_result({"answer": "A"})
            else:
                return make_result({"answer": "B"})

        runner = AsyncMock(spec=AgentRunner)
        runner.run = AsyncMock(side_effect=run_agent)

        voter = FirstToKVoter(runner=runner, red_flagger=RedFlagger())
        result = await voter.vote(make_step(), context="", config=make_config(voting_k=2))

        assert result.winner == {"answer": "A"}
        assert result.total_samples == 4  # A:3, B:1 → 3-1 >= 2

    async def test_respects_max_voting_samples(self):
        """If max_voting_samples reached without K-lead, fail."""
        call_count = 0

        async def run_agent(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Alternating — never reaches K=2 lead
            if call_count % 2 == 1:
                return make_result({"answer": "A"})
            else:
                return make_result({"answer": "B"})

        runner = AsyncMock(spec=AgentRunner)
        runner.run = AsyncMock(side_effect=run_agent)

        voter = FirstToKVoter(runner=runner, red_flagger=RedFlagger())
        config = make_config(voting_k=2, max_voting_samples=6)

        with pytest.raises(RuntimeError, match="max_voting_samples"):
            await voter.vote(make_step(), context="", config=config)

    async def test_k1_wins_immediately(self):
        """K=1 means first valid result wins."""
        runner = AsyncMock(spec=AgentRunner)
        runner.run = AsyncMock(return_value=make_result({"fast": True}))

        voter = FirstToKVoter(runner=runner, red_flagger=RedFlagger())
        result = await voter.vote(make_step(), context="", config=make_config(voting_k=1))

        assert result.winner == {"fast": True}
        assert result.total_samples == 1

    async def test_red_flagged_excluded_from_counts(self):
        call_count = 0

        async def run_agent(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return make_result("not a dict")  # red-flagged
            return make_result({"answer": 42})

        runner = AsyncMock(spec=AgentRunner)
        runner.run = AsyncMock(side_effect=run_agent)

        voter = FirstToKVoter(runner=runner, red_flagger=RedFlagger())
        result = await voter.vote(make_step(), context="", config=make_config(voting_k=2))

        assert result.winner == {"answer": 42}
        assert result.red_flagged == 1

    async def test_canonicalization_groups_votes(self):
        """Same content with different key order should be same vote."""
        runner = AsyncMock(spec=AgentRunner)
        runner.run = AsyncMock(side_effect=[
            make_result({"b": 2, "a": 1}),
            make_result({"a": 1, "b": 2}),  # same content
        ])

        voter = FirstToKVoter(runner=runner, red_flagger=RedFlagger())
        result = await voter.vote(make_step(), context="", config=make_config(voting_k=2))

        assert result.total_samples == 2
        # Both should count as the same answer → 2-0 >= 2
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement `src/maker/voting/first_to_k_voter.py`**

```python
from maker.voting.base import Voter
from maker.core.models import PlanStep, VoteResult, TaskConfig
from maker.executor.agent_runner import AgentRunner
from maker.red_flag.red_flagger import RedFlagger
from maker.voting.canonicalizer import Canonicalizer


class FirstToKVoter(Voter):
    """Paper's approach: keep running agents until leader_count - runner_up_count >= K."""

    def __init__(self, runner: AgentRunner, red_flagger: RedFlagger):
        self._runner = runner
        self._red_flagger = red_flagger
        self._canonicalizer = Canonicalizer()

    async def vote(self, step: PlanStep, context: str, config: TaskConfig) -> VoteResult:
        """Run agents one at a time. Track vote counts per canonical hash.
        Winner when leader_count - runner_up_count >= K.
        Fail if max_voting_samples reached."""
        ...
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/voting/first_to_k_voter.py tests/test_voting/test_first_to_k_voter.py
git commit -m "feat: add FirstToKVoter with ahead-by-K consensus"
```

---

## Definition of Done

- [ ] `uv run pytest tests/test_voting/ -v` — all tests pass
- [ ] Canonicalizer produces same hash for semantically identical dicts (different key order)
- [ ] Canonicalizer preserves list order
- [ ] Canonicalizer handles nested dicts/lists
- [ ] NoVoter returns single agent result with retries
- [ ] NoVoter respects step_max_retries
- [ ] MajorityVoter takes majority from N samples
- [ ] MajorityVoter runs additional samples if no initial majority
- [ ] MajorityVoter respects max_voting_samples
- [ ] MajorityVoter excludes red-flagged samples
- [ ] FirstToKVoter declares winner when leader - runner_up >= K
- [ ] FirstToKVoter respects max_voting_samples
- [ ] FirstToKVoter excludes red-flagged samples
- [ ] Canonicalization prevents vote-splitting on equivalent outputs
- [ ] All code committed
