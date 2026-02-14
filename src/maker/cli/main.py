import argparse
import asyncio
import json
from maker import run_task
from maker.core.models import TaskConfig
from maker.core.events import (
    TaskSubmitted, PlanCreated, ValidationPassed, ValidationFailed,
    StepStarted, StepCompleted, StepFailed, TaskCompleted, TaskFailed,
)


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MAKER: Maximal Agentic Decomposition")
    parser.add_argument("instruction", help="The task to execute")
    parser.add_argument("--model", default="claude-sonnet-4-5", help="Model to use")
    parser.add_argument("--voting", default="none", choices=["none", "majority", "first_to_k"])
    parser.add_argument("--voting-n", type=int, default=3, help="Samples for majority voting")
    parser.add_argument("--voting-k", type=int, default=2, help="K for first-to-K voting")
    parser.add_argument("--max-voting-samples", type=int, default=10, help="Max voting samples per step")
    parser.add_argument("--quality-checks", action="store_true", help="Enable LLM quality checks")
    return parser.parse_args(argv)


def format_event(event) -> str:
    """Format an event for CLI display."""
    if isinstance(event, TaskSubmitted):
        return f"Task submitted: {event.instruction}"
    elif isinstance(event, PlanCreated):
        n_steps = len(event.plan.steps)
        return f"Plan created: {n_steps} steps"
    elif isinstance(event, ValidationPassed):
        return f"Validation passed: {event.checks_passed} checks passed"
    elif isinstance(event, ValidationFailed):
        errors = "; ".join(e["message"] for e in event.errors)
        return f"Validation failed: {errors}"
    elif isinstance(event, StepStarted):
        return f"Step {event.step} started: {event.title}"
    elif isinstance(event, StepCompleted):
        output_str = json.dumps(event.output, indent=2) if isinstance(event.output, dict) else str(event.output)
        return f"Step {event.step} completed: {event.title}\n  Output: {output_str}"
    elif isinstance(event, StepFailed):
        return f"Step {event.step} failed: {event.error}"
    elif isinstance(event, TaskCompleted):
        cost = event.total_cost_usd
        duration_s = event.total_duration_ms / 1000
        # Show final step outputs
        steps = event.result.get("steps", [])
        final_output = steps[-1]["output"] if steps else {}
        result_str = json.dumps(final_output, indent=2) if isinstance(final_output, dict) else str(final_output)
        return f"Task completed | Cost: ${cost:.2f} | Duration: {duration_s:.1f}s\n\nResult:\n{result_str}"
    elif isinstance(event, TaskFailed):
        return f"Task failed at step {event.step}: {event.error}"
    else:
        return f"[{type(event).__name__}]"


def cli():
    args = parse_args()
    config = TaskConfig(
        instruction=args.instruction,
        model=args.model,
        voting_strategy=args.voting,
        voting_n=args.voting_n,
        voting_k=args.voting_k,
        max_voting_samples=args.max_voting_samples,
        enable_quality_checks=args.quality_checks,
    )

    async def _run():
        async for event in run_task(config):
            print(format_event(event))

    asyncio.run(_run())


if __name__ == "__main__":
    cli()
