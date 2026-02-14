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
