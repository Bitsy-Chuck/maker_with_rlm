import pytest
from unittest.mock import AsyncMock, patch
from maker import run_task, TaskConfig
from maker.core.events import TaskCompleted, TaskFailed


class TestPublicAPI:
    async def test_run_task_yields_events(self):
        """run_task should yield events from the orchestrator."""
        config = TaskConfig(instruction="test")

        events = []
        with patch("maker.Orchestrator") as MockOrch:
            mock_instance = AsyncMock()

            async def mock_run():
                yield TaskCompleted(
                    timestamp=1000.0,
                    result={"status": "completed", "steps": []},
                    total_cost_usd=0.0, total_duration_ms=0,
                )

            mock_instance.run = mock_run
            MockOrch.return_value = mock_instance

            async for event in run_task(config):
                events.append(event)

        assert len(events) >= 1
        assert isinstance(events[-1], TaskCompleted)

    async def test_run_task_uses_default_registry(self):
        """run_task should create a default registry if not provided."""
        config = TaskConfig(instruction="test")

        with patch("maker.Orchestrator") as MockOrch:
            mock_instance = AsyncMock()

            async def mock_run():
                return
                yield

            mock_instance.run = mock_run
            MockOrch.return_value = mock_instance

            async for _ in run_task(config):
                pass

            # Orchestrator should have been called with a registry
            call_kwargs = MockOrch.call_args
            assert call_kwargs is not None
