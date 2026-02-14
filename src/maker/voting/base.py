from abc import ABC, abstractmethod
from maker.core.models import PlanStep, VoteResult, TaskConfig
from maker.executor.agent_runner import AgentRunner


class Voter(ABC):
    @abstractmethod
    async def vote(self, step: PlanStep, context: str, config: TaskConfig) -> VoteResult:
        """Run agent(s) and return the winning output."""
        ...
