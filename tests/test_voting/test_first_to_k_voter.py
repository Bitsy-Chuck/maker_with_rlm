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
        Two identical results with 0 for any other -> 2-0 >= 2 -> win."""
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
        assert result.total_samples == 4  # A:3, B:1 -> 3-1 >= 2

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
        # Both should count as the same answer -> 2-0 >= 2
