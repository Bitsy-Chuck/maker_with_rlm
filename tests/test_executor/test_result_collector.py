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
