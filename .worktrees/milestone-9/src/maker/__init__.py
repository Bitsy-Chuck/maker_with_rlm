"""MAKER: Maximal Agentic Decomposition with Error Correction and Red-flagging."""

from maker.core.models import TaskConfig
from maker.core.orchestrator import Orchestrator
from maker.tools.registry import ToolRegistry
from typing import AsyncIterator


async def run_task(config: TaskConfig, registry: ToolRegistry | None = None) -> AsyncIterator:
    """Run a MAKER task. Yields events as they occur."""
    if registry is None:
        registry = ToolRegistry.with_defaults()

    orchestrator = Orchestrator(config=config, registry=registry)
    async for event in orchestrator.run():
        yield event
