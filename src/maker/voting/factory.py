from maker.voting.base import Voter
from maker.voting.no_voter import NoVoter
from maker.voting.majority_voter import MajorityVoter
from maker.voting.first_to_k_voter import FirstToKVoter
from maker.executor.agent_runner import AgentRunner
from maker.red_flag.red_flagger import RedFlagger


def create_voter(strategy: str, runner: AgentRunner, red_flagger: RedFlagger) -> Voter:
    if strategy == "none":
        return NoVoter(runner=runner, red_flagger=red_flagger)
    elif strategy == "majority":
        return MajorityVoter(runner=runner, red_flagger=red_flagger)
    elif strategy == "first_to_k":
        return FirstToKVoter(runner=runner, red_flagger=red_flagger)
    else:
        raise ValueError(f"Unknown voting strategy: {strategy}")
