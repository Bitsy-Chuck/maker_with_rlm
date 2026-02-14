import pytest
from unittest.mock import MagicMock
from maker.voting.factory import create_voter
from maker.voting.no_voter import NoVoter
from maker.voting.majority_voter import MajorityVoter
from maker.voting.first_to_k_voter import FirstToKVoter
from maker.core.models import TaskConfig
from maker.executor.agent_runner import AgentRunner
from maker.red_flag.red_flagger import RedFlagger


class TestCreateVoter:
    def test_none_strategy(self):
        runner = MagicMock(spec=AgentRunner)
        voter = create_voter("none", runner, RedFlagger())
        assert isinstance(voter, NoVoter)

    def test_majority_strategy(self):
        runner = MagicMock(spec=AgentRunner)
        voter = create_voter("majority", runner, RedFlagger())
        assert isinstance(voter, MajorityVoter)

    def test_first_to_k_strategy(self):
        runner = MagicMock(spec=AgentRunner)
        voter = create_voter("first_to_k", runner, RedFlagger())
        assert isinstance(voter, FirstToKVoter)

    def test_invalid_strategy_raises(self):
        runner = MagicMock(spec=AgentRunner)
        with pytest.raises(ValueError, match="Unknown voting strategy"):
            create_voter("invalid", runner, RedFlagger())
