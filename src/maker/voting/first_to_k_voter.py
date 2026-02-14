from collections import Counter
from maker.voting.base import Voter
from maker.core.models import PlanStep, VoteResult, TaskConfig
from maker.executor.agent_runner import AgentRunner
from maker.red_flag.red_flagger import RedFlagger
from maker.voting.canonicalizer import Canonicalizer


class FirstToKVoter(Voter):
    """Paper's approach: keep running agents until leader_count - runner_up_count >= K."""

    def __init__(self, runner: AgentRunner, red_flagger: RedFlagger):
        self._runner = runner
        self._red_flagger = red_flagger
        self._canonicalizer = Canonicalizer()

    async def vote(self, step: PlanStep, context: str, config: TaskConfig) -> VoteResult:
        """Run agents one at a time. Track vote counts per canonical hash.
        Winner when leader_count - runner_up_count >= K.
        Fail if max_voting_samples reached."""
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

            # Check if leader is ahead by K
            ranked = vote_counts.most_common()
            leader_hash, leader_count = ranked[0]
            runner_up_count = ranked[1][1] if len(ranked) > 1 else 0

            if leader_count - runner_up_count >= config.voting_k:
                return VoteResult(
                    winner=hash_to_output[leader_hash],
                    canonical_hash=leader_hash,
                    total_samples=total_samples,
                    red_flagged=red_flagged,
                    vote_counts=dict(vote_counts),
                )

        raise RuntimeError(
            f"Reached max_voting_samples ({config.max_voting_samples}) without "
            f"K={config.voting_k} lead for step {step.step}"
        )
