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
