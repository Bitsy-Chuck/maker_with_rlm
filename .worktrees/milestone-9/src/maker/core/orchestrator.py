from maker.core.models import TaskConfig, Plan
from maker.core.events import (
    TaskSubmitted, PlanCreated, ValidationPassed, ValidationFailed,
    TaskFailed,
)
from maker.planner.planner import PlannerModule
from maker.validator.validator import ValidatorModule
from maker.executor.executor import ExecutorModule
from maker.executor.agent_runner import AgentRunner
from maker.red_flag.red_flagger import RedFlagger
from maker.voting.factory import create_voter
from maker.tools.registry import ToolRegistry
from typing import AsyncIterator
import time


class Orchestrator:
    def __init__(self, config: TaskConfig, registry: ToolRegistry):
        self._config = config
        self._registry = registry
        self._planner = PlannerModule(registry=registry)
        self._validator = ValidatorModule(registry=registry, config=config)
        # Placeholder executor — replaced with real one after plan is validated
        self._executor = ExecutorModule(
            config=config,
            plan=Plan(reasoning="", steps=[]),
        )

    async def run(self) -> AsyncIterator:
        """Drive the full pipeline. Yields all events."""
        # 1. Emit TaskSubmitted
        task_event = TaskSubmitted(
            timestamp=time.time(),
            instruction=self._config.instruction,
            config=self._config,
        )
        yield task_event

        # 2. Plan → Validate loop (with retries)
        plan = None
        plan_event = None
        for attempt in range(self._config.max_planner_retries + 1):
            # Run planner
            async for event in self._planner.process(task_event):
                yield event
                if isinstance(event, PlanCreated):
                    plan_event = event

            if plan_event is None:
                yield TaskFailed(
                    timestamp=time.time(),
                    error="Planner produced no plan",
                    step=-1,
                )
                return

            # Run validator
            validated = False
            async for event in self._validator.process(plan_event):
                yield event
                if isinstance(event, ValidationPassed):
                    plan = plan_event.plan
                    validated = True
                elif isinstance(event, ValidationFailed):
                    pass  # will retry on next loop iteration

            if validated:
                break

        if not plan:
            yield TaskFailed(
                timestamp=time.time(),
                error=f"Plan validation failed after {self._config.max_planner_retries + 1} attempts",
                step=-1,
            )
            return

        # 3. Configure executor with validated plan and wire up voter
        self._executor._plan = plan
        self._executor._config = self._config
        if self._executor._voter is None:
            runner = AgentRunner()
            red_flagger = RedFlagger()
            self._executor._voter = create_voter(
                self._config.voting_strategy, runner, red_flagger,
            )

        # 4. Execute
        validation_event = ValidationPassed(timestamp=time.time(), checks_passed=0)
        async for event in self._executor.process(validation_event):
            yield event
