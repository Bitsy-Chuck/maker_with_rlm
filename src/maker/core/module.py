from abc import ABC, abstractmethod
from typing import AsyncIterator


class Module(ABC):
    @abstractmethod
    async def process(self, event) -> AsyncIterator:
        """Receive an event, yield zero or more events."""
        ...
