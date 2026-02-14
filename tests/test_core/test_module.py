import pytest
from maker.core.module import Module
from maker.core.events import StepStarted, StepCompleted
from maker.core.models import VotingSummary


class TestModuleABC:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            Module()

    async def test_concrete_implementation(self):
        class EchoModule(Module):
            async def process(self, event):
                if isinstance(event, StepStarted):
                    summary = VotingSummary(
                        strategy="none", total_samples=1,
                        red_flagged=0, winning_votes=1,
                    )
                    yield StepCompleted(
                        timestamp=event.timestamp,
                        step=event.step,
                        title=event.title,
                        output={"echo": True},
                        voting_summary=summary,
                        cost_usd=0.0,
                        duration_ms=0,
                    )

        mod = EchoModule()
        event = StepStarted(timestamp=1000.0, step=0, title="test")
        results = [e async for e in mod.process(event)]
        assert len(results) == 1
        assert isinstance(results[0], StepCompleted)

    async def test_process_can_yield_nothing(self):
        class IgnoreModule(Module):
            async def process(self, event):
                return  # yields nothing
                yield  # make it a generator

        mod = IgnoreModule()
        event = StepStarted(timestamp=1000.0, step=0, title="test")
        results = [e async for e in mod.process(event)]
        assert results == []
