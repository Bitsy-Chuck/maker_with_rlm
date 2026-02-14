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
        max_attempts = config.step_max_retries + 1
        total_samples = 0
        red_flagged = 0

        for _ in range(max_attempts):
            result = await self._runner.run(step, context, config)
            total_samples += 1

            if self._red_flagger.check(result):
                red_flagged += 1
                continue

            return VoteResult(
                winner=result.output,
                canonical_hash=self._canonicalizer.hash(result.output),
                total_samples=total_samples,
                red_flagged=red_flagged,
                vote_counts={self._canonicalizer.hash(result.output): 1},
            )

        raise RuntimeError(
            f"All {max_attempts} retries exhausted for step {step.step}"
        )
