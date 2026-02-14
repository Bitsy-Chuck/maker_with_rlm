from collections import Counter
from maker.voting.base import Voter
from maker.core.models import PlanStep, VoteResult, TaskConfig
from maker.executor.agent_runner import AgentRunner
from maker.red_flag.red_flagger import RedFlagger
from maker.voting.canonicalizer import Canonicalizer


class MajorityVoter(Voter):
    def __init__(self, runner: AgentRunner, red_flagger: RedFlagger):
        self._runner = runner
        self._red_flagger = red_flagger
        self._canonicalizer = Canonicalizer()

    async def vote(self, step: PlanStep, context: str, config: TaskConfig) -> VoteResult:
        """Run N agents, take majority. If no majority, run more up to max_voting_samples."""
        vote_counts: Counter[str] = Counter()
        hash_to_output: dict[str, dict] = {}
        total_samples = 0
        red_flagged = 0

        while total_samples < config.max_voting_samples:
            result = await self._runner.run(step, context, config)
            total_samples += 1

            if self._red_flagger.check(result):
                red_flagged += 1
                continue

            h = self._canonicalizer.hash(result.output)
            vote_counts[h] += 1
            if h not in hash_to_output:
                hash_to_output[h] = result.output

            # Check for majority after collecting at least voting_n valid samples
            valid_samples = sum(vote_counts.values())
            if valid_samples >= config.voting_n:
                leader_hash, leader_count = vote_counts.most_common(1)[0]
                if leader_count > valid_samples / 2:
                    return VoteResult(
                        winner=hash_to_output[leader_hash],
                        canonical_hash=leader_hash,
                        total_samples=total_samples,
                        red_flagged=red_flagged,
                        vote_counts=dict(vote_counts),
                    )

        raise RuntimeError(
            f"Reached max_voting_samples ({config.max_voting_samples}) with no majority "
            f"for step {step.step}"
        )
