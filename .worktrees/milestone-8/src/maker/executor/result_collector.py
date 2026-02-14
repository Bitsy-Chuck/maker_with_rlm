from maker.core.models import VotingSummary


class ResultCollector:
    def __init__(self, instruction: str):
        self._instruction = instruction
        self._steps: list[dict] = []
        self._total_cost = 0.0
        self._total_duration = 0

    def add_step(self, step: int, title: str, output: dict,
                 voting_summary: VotingSummary, cost_usd: float, duration_ms: int) -> None:
        self._steps.append({
            "step": step,
            "title": title,
            "output": output,
            "voting": {
                "strategy": voting_summary.strategy,
                "samples": voting_summary.total_samples,
                "red_flagged": voting_summary.red_flagged,
                "winning_votes": voting_summary.winning_votes,
            },
            "cost_usd": cost_usd,
            "duration_ms": duration_ms,
        })
        self._total_cost += cost_usd
        self._total_duration += duration_ms

    def finalize(self, status: str = "completed") -> dict:
        return {
            "task": self._instruction,
            "status": status,
            "steps": self._steps,
            "total_cost_usd": self._total_cost,
            "total_duration_ms": self._total_duration,
        }
