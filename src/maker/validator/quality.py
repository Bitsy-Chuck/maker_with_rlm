from dataclasses import dataclass
from maker.core.models import Plan, PlanStep
from maker.prompts import load_prompt


DEFAULT_MAX_K = 5

# Checks that evaluate the whole plan (use {plan_yaml})
_PLAN_LEVEL_CHECKS = {"non_overlapping", "appropriately_merged"}

# Checks that need extra kwargs
_EXTRA_KWARGS = {"max_k_tools": {"max_k": DEFAULT_MAX_K}}


@dataclass
class QualityResult:
    name: str
    score: float  # 0.0 - 1.0
    details: str


class QualityChecker:
    CHECKS = [
        "single_purpose",
        "self_contained",
        "max_k_tools",
        "non_overlapping",
        "maximally_decomposed",
        "appropriately_merged",
    ]

    async def run_all(self, plan: Plan) -> list[QualityResult]:
        """Run all quality checks and return results."""
        results = []
        for check_name in self.CHECKS:
            prompt = _build_prompt(check_name, plan)
            score = await self._call_llm_for_score(prompt)
            results.append(QualityResult(
                name=check_name,
                score=score,
                details=f"Score: {score}",
            ))
        return results

    def aggregate_score(self, results: list[QualityResult]) -> float:
        """Compute equally-weighted average of all quality scores."""
        if not results:
            return 0.0
        return sum(r.score for r in results) / len(results)

    async def _call_llm_for_score(self, prompt: str) -> float:
        """Call LLM to get a quality score. Override in tests."""
        raise NotImplementedError("LLM scoring not yet wired up")


def _build_prompt(check_name: str, plan: Plan) -> str:
    """Build the appropriate prompt for a quality check."""
    extra = _EXTRA_KWARGS.get(check_name, {})
    plan_text = _plan_to_text(plan)

    if check_name in _PLAN_LEVEL_CHECKS:
        return load_prompt(f"quality_{check_name}", plan_yaml=plan_text, **extra)
    else:
        return load_prompt(f"quality_{check_name}", step_yaml=plan_text, **extra)


def _plan_to_text(plan: Plan) -> str:
    """Convert plan to a text representation for LLM prompts."""
    lines = [f"Reasoning: {plan.reasoning}"]
    for step in plan.steps:
        lines.append(_step_to_text(step))
    return "\n".join(lines)


def _step_to_text(step: PlanStep) -> str:
    """Convert a single step to text for LLM prompts."""
    return (
        f"Step {step.step}: [{step.task_type}] {step.title}\n"
        f"  Description: {step.task_description}\n"
        f"  Tools: {step.primary_tools} (fallback: {step.fallback_tools})\n"
        f"  Output: {step.output_variable} ({step.output_schema})"
    )
