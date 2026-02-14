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
