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
