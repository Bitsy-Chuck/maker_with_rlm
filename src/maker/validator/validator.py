from maker.core.module import Module
from maker.core.events import PlanCreated, ValidationPassed, ValidationFailed
from maker.core.models import TaskConfig
from maker.validator.deterministic import run_all_deterministic_checks
from maker.validator.quality import QualityChecker
from maker.tools.registry import ToolRegistry
from typing import AsyncIterator
import time


class ValidatorModule(Module):
    def __init__(self, registry: ToolRegistry, config: TaskConfig):
        self._registry = registry
        self._config = config
        self._quality_checker = QualityChecker()

    async def process(self, event) -> AsyncIterator:
        if not isinstance(event, PlanCreated):
            return

        # Layer 1: Deterministic checks (always)
        results = run_all_deterministic_checks(event.plan, self._registry)
        failures = [r for r in results if not r.passed]

        if failures:
            yield ValidationFailed(
                timestamp=time.time(),
                errors=[{"check": r.name, "message": r.message} for r in failures],
            )
            return

        # Layer 2: Quality checks (optional)
        if self._config.enable_quality_checks:
            quality_results = await self._quality_checker.run_all(event.plan)
            # Quality scores are informational; deterministic checks gate pass/fail

        yield ValidationPassed(
            timestamp=time.time(),
            checks_passed=len(results),
        )
