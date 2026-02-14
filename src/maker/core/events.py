from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, fields, asdict
from typing import AsyncIterator, Any

from maker.core.models import TaskConfig, Plan, VotingSummary


# --- Event types ---


@dataclass
class TaskSubmitted:
    timestamp: float
    instruction: str
    config: TaskConfig
    type: str = field(init=False, default="task_submitted")


@dataclass
class PlanCreated:
    timestamp: float
    plan: Plan
    type: str = field(init=False, default="plan_created")


@dataclass
class ValidationPassed:
    timestamp: float
    checks_passed: int
    type: str = field(init=False, default="validation_passed")


@dataclass
class ValidationFailed:
    timestamp: float
    errors: list[dict]
    type: str = field(init=False, default="validation_failed")


@dataclass
class StepStarted:
    timestamp: float
    step: int
    title: str
    type: str = field(init=False, default="step_started")


@dataclass
class AgentSampleCompleted:
    timestamp: float
    step: int
    sample_index: int
    output: dict
    cost_usd: float
    duration_ms: int
    type: str = field(init=False, default="agent_sample_completed")


@dataclass
class AgentSampleRedFlagged:
    timestamp: float
    step: int
    sample_index: int
    reason: str
    type: str = field(init=False, default="agent_sample_red_flagged")


@dataclass
class VoteCompleted:
    timestamp: float
    step: int
    winner: dict
    total_samples: int
    red_flagged: int
    type: str = field(init=False, default="vote_completed")


@dataclass
class StepCompleted:
    timestamp: float
    step: int
    title: str
    output: dict
    voting_summary: VotingSummary
    cost_usd: float
    duration_ms: int
    type: str = field(init=False, default="step_completed")


@dataclass
class StepFailed:
    timestamp: float
    step: int
    title: str
    error: str
    type: str = field(init=False, default="step_failed")


@dataclass
class TaskCompleted:
    timestamp: float
    result: dict
    total_cost_usd: float
    total_duration_ms: int
    type: str = field(init=False, default="task_completed")


@dataclass
class TaskFailed:
    timestamp: float
    error: str
    step: int
    type: str = field(init=False, default="task_failed")


# --- Event serialization ---


def _is_dataclass_instance(obj: Any) -> bool:
    return hasattr(obj, "__dataclass_fields__")


def event_to_dict(event: Any) -> dict:
    """Recursively convert a dataclass event to a plain dict."""
    result = {}
    for f in fields(event):
        value = getattr(event, f.name)
        if _is_dataclass_instance(value):
            value = event_to_dict(value)
        elif isinstance(value, list):
            value = [
                event_to_dict(item) if _is_dataclass_instance(item) else item
                for item in value
            ]
        result[f.name] = value
    return result


# --- Event Bus ---


_SENTINEL = None


class EventBus:
    """Async broadcast bus. Multiple subscribers each get every event."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue] = []

    async def emit(self, event: Any) -> None:
        """Put event into every subscriber's queue."""
        await asyncio.sleep(0)  # yield control so pending subscribers can register
        for queue in self._subscribers:
            await queue.put(event)

    async def subscribe(self) -> AsyncIterator:
        """Yield events as they arrive. Stops on shutdown sentinel."""
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        try:
            while True:
                event = await queue.get()
                if event is _SENTINEL:
                    break
                yield event
        finally:
            self._subscribers.remove(queue)

    async def shutdown(self) -> None:
        """Signal all subscribers to stop."""
        for queue in self._subscribers:
            await queue.put(_SENTINEL)
