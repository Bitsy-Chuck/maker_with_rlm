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
