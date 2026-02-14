from maker.core.module import Module
from maker.core.events import (
    ValidationPassed, StepStarted, StepCompleted, StepFailed,
    TaskCompleted, TaskFailed,
)
from maker.core.models import Plan, TaskConfig, VotingSummary
from maker.executor.context_builder import ContextBuilder
from maker.executor.result_collector import ResultCollector
from maker.voting.base import Voter
from typing import AsyncIterator
import time


class ExecutorModule(Module):
    def __init__(self, config: TaskConfig, plan: Plan):
        self._config = config
        self._plan = plan
        self._context_builder = ContextBuilder()
        self._step_outputs: dict[str, dict] = {}
        self._voter: Voter = None  # set externally or via factory

    async def process(self, event) -> AsyncIterator:
        if not isinstance(event, ValidationPassed):
            return

        collector = ResultCollector(instruction=self._config.instruction)
        step_map = {s.step: s for s in self._plan.steps}
        current_step_num = 0

        while current_step_num >= 0:
            step = step_map.get(current_step_num)
            if step is None:
                yield StepFailed(
                    timestamp=time.time(),
                    step=current_step_num,
                    title="unknown",
                    error=f"Step {current_step_num} not found in plan",
                )
                yield TaskFailed(
                    timestamp=time.time(),
                    error=f"Step {current_step_num} not found in plan",
                    step=current_step_num,
                )
                return

            yield StepStarted(timestamp=time.time(), step=step.step, title=step.title)

            try:
                start = time.time()
                context = self._context_builder.build(step, self._step_outputs)
                vote_result = await self._voter.vote(step, context, self._config)
                duration_ms = int((time.time() - start) * 1000)

                self._step_outputs[step.output_variable] = vote_result.winner

                # Build voting summary
                summary = VotingSummary(
                    strategy=self._config.voting_strategy,
                    total_samples=vote_result.total_samples,
                    red_flagged=vote_result.red_flagged,
                    winning_votes=vote_result.vote_counts.get(vote_result.canonical_hash, 1),
                )

                # Handle conditional routing
                if step.task_type == "conditional_step":
                    next_step = vote_result.winner.get("next_step")
                    if next_step is None:
                        yield StepFailed(
                            timestamp=time.time(),
                            step=step.step,
                            title=step.title,
                            error="Conditional step output missing 'next_step' field",
                        )
                        yield TaskFailed(
                            timestamp=time.time(),
                            error="Conditional step output missing 'next_step' field",
                            step=step.step,
                        )
                        return
                    current_step_num = next_step
                else:
                    current_step_num = step.next_step_sequence_number

                yield StepCompleted(
                    timestamp=time.time(),
                    step=step.step,
                    title=step.title,
                    output=vote_result.winner,
                    voting_summary=summary,
                    cost_usd=0.0,
                    duration_ms=duration_ms,
                )
                collector.add_step(
                    step=step.step,
                    title=step.title,
                    output=vote_result.winner,
                    voting_summary=summary,
                    cost_usd=0.0,
                    duration_ms=duration_ms,
                )

            except Exception as e:
                yield StepFailed(
                    timestamp=time.time(),
                    step=step.step,
                    title=step.title,
                    error=str(e),
                )
                yield TaskFailed(
                    timestamp=time.time(),
                    error=str(e),
                    step=step.step,
                )
                return

        result = collector.finalize()
        yield TaskCompleted(
            timestamp=time.time(),
            result=result,
            total_cost_usd=result["total_cost_usd"],
            total_duration_ms=result["total_duration_ms"],
        )
