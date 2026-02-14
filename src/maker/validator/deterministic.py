from dataclasses import dataclass, fields
from maker.core.models import Plan
from maker.tools.registry import ToolRegistry

VALID_TASK_TYPES = {"action_step", "conditional_step"}


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str


def check_required_fields(plan: Plan) -> CheckResult:
    """Check that all required fields exist on each PlanStep (dataclass field presence)."""
    required = {f.name for f in fields(plan.steps[0].__class__)}
    for step in plan.steps:
        for field_name in required:
            if not hasattr(step, field_name):
                return CheckResult(
                    name="required_fields",
                    passed=False,
                    message=f"Step {step.step} missing field '{field_name}'",
                )
    return CheckResult(name="required_fields", passed=True, message="All required fields present")


def check_step_numbering(plan: Plan) -> CheckResult:
    """Check steps are numbered sequentially starting at 0 with no gaps."""
    step_numbers = sorted(s.step for s in plan.steps)
    expected = list(range(len(plan.steps)))
    if step_numbers != expected:
        if step_numbers and step_numbers[0] != 0:
            return CheckResult(
                name="step_numbering",
                passed=False,
                message=f"Steps must start at 0, got {step_numbers[0]}",
            )
        return CheckResult(
            name="step_numbering",
            passed=False,
            message=f"Steps not sequential — expected {expected}, got {step_numbers}. Gap in numbering.",
        )
    return CheckResult(name="step_numbering", passed=True, message="Step numbering is sequential")


def check_task_type_valid(plan: Plan) -> CheckResult:
    """Check all steps have a valid task_type."""
    for step in plan.steps:
        if step.task_type not in VALID_TASK_TYPES:
            return CheckResult(
                name="task_type_valid",
                passed=False,
                message=f"Step {step.step} has invalid task_type '{step.task_type}'",
            )
    return CheckResult(name="task_type_valid", passed=True, message="All task types valid")


def check_reasoning_present(plan: Plan) -> CheckResult:
    """Check that the plan has non-empty reasoning."""
    if not plan.reasoning or not plan.reasoning.strip():
        return CheckResult(
            name="reasoning_present",
            passed=False,
            message="Plan reasoning is empty",
        )
    return CheckResult(name="reasoning_present", passed=True, message="Reasoning present")


def check_tools_mutually_exclusive(plan: Plan) -> CheckResult:
    """Check primary_tools and fallback_tools don't overlap within each step."""
    for step in plan.steps:
        overlap = set(step.primary_tools) & set(step.fallback_tools)
        if overlap:
            return CheckResult(
                name="tools_mutually_exclusive",
                passed=False,
                message=f"Step {step.step} has tools in both primary and fallback: {overlap}",
            )
    return CheckResult(
        name="tools_mutually_exclusive", passed=True, message="Tools are mutually exclusive"
    )


def check_tools_are_valid(plan: Plan, registry: ToolRegistry) -> CheckResult:
    """Check all referenced tools exist in the registry."""
    for step in plan.steps:
        all_tools = step.primary_tools + step.fallback_tools
        for tool in all_tools:
            if not registry.validate_tool_name(tool):
                return CheckResult(
                    name="tools_are_valid",
                    passed=False,
                    message=f"Step {step.step} references unknown tool '{tool}'",
                )
    return CheckResult(name="tools_are_valid", passed=True, message="All tools are valid")


def check_conditional_step_no_tools(plan: Plan) -> CheckResult:
    """Check conditional steps have no tools."""
    for step in plan.steps:
        if step.task_type == "conditional_step":
            if step.primary_tools or step.fallback_tools:
                return CheckResult(
                    name="conditional_step_no_tools",
                    passed=False,
                    message=f"Conditional step {step.step} must not have tools",
                )
    return CheckResult(
        name="conditional_step_no_tools", passed=True, message="Conditional steps have no tools"
    )


def check_conditional_step_no_instructions(plan: Plan) -> CheckResult:
    """Check conditional steps have no tool instructions."""
    for step in plan.steps:
        if step.task_type == "conditional_step":
            if step.primary_tool_instructions or step.fallback_tool_instructions:
                return CheckResult(
                    name="conditional_step_no_instructions",
                    passed=False,
                    message=f"Conditional step {step.step} must not have tool instructions",
                )
    return CheckResult(
        name="conditional_step_no_instructions",
        passed=True,
        message="Conditional steps have no instructions",
    )


def check_next_step_valid(plan: Plan) -> CheckResult:
    """Check next_step_sequence_number points to an existing step or is -1/-2."""
    step_numbers = {s.step for s in plan.steps}
    for step in plan.steps:
        nsn = step.next_step_sequence_number
        if nsn not in (-1, -2) and nsn not in step_numbers:
            return CheckResult(
                name="next_step_valid",
                passed=False,
                message=f"Step {step.step} points to nonexistent step {nsn}",
            )
    return CheckResult(name="next_step_valid", passed=True, message="All next_step references valid")


def check_conditional_returns_minus_2(plan: Plan) -> CheckResult:
    """Check conditional steps have next_step_sequence_number == -2."""
    for step in plan.steps:
        if step.task_type == "conditional_step" and step.next_step_sequence_number != -2:
            return CheckResult(
                name="conditional_returns_minus_2",
                passed=False,
                message=f"Conditional step {step.step} must have next_step_sequence_number=-2, got {step.next_step_sequence_number}",
            )
    return CheckResult(
        name="conditional_returns_minus_2",
        passed=True,
        message="Conditional steps return -2",
    )


def check_final_step_returns_minus_1(plan: Plan) -> CheckResult:
    """Check the last step has next_step_sequence_number == -1 (conditional steps exempt)."""
    if not plan.steps:
        return CheckResult(
            name="final_step_returns_minus_1", passed=True, message="No steps to check"
        )
    last_step = max(plan.steps, key=lambda s: s.step)
    if last_step.task_type == "conditional_step":
        return CheckResult(
            name="final_step_returns_minus_1",
            passed=True,
            message="Final step is conditional (exempt)",
        )
    if last_step.next_step_sequence_number != -1:
        return CheckResult(
            name="final_step_returns_minus_1",
            passed=False,
            message=f"Final step {last_step.step} must have next_step_sequence_number=-1",
        )
    return CheckResult(
        name="final_step_returns_minus_1", passed=True, message="Final step returns -1"
    )


def check_no_orphan_steps(plan: Plan) -> CheckResult:
    """Check all steps are reachable from step 0 via next_step_sequence_number chain."""
    if len(plan.steps) <= 1:
        return CheckResult(name="no_orphan_steps", passed=True, message="No orphan steps")

    reachable = {0}
    step_map = {s.step: s for s in plan.steps}
    queue = [0]
    while queue:
        current = queue.pop(0)
        step = step_map.get(current)
        if step is None:
            continue
        nsn = step.next_step_sequence_number
        if nsn >= 0 and nsn not in reachable:
            reachable.add(nsn)
            queue.append(nsn)

    all_steps = {s.step for s in plan.steps}
    orphans = all_steps - reachable
    if orphans:
        return CheckResult(
            name="no_orphan_steps",
            passed=False,
            message=f"Orphan steps not reachable from step 0: {sorted(orphans)}",
        )
    return CheckResult(name="no_orphan_steps", passed=True, message="No orphan steps")


def check_output_schema_exists(plan: Plan) -> CheckResult:
    """Check every step has a non-empty output_schema."""
    for step in plan.steps:
        if not step.output_schema or not step.output_schema.strip():
            return CheckResult(
                name="output_schema_exists",
                passed=False,
                message=f"Step {step.step} has empty output_schema",
            )
    return CheckResult(
        name="output_schema_exists", passed=True, message="All steps have output schemas"
    )


def run_all_deterministic_checks(plan: Plan, registry: ToolRegistry) -> list[CheckResult]:
    """Run all deterministic checks and return results."""
    return [
        check_required_fields(plan),
        check_step_numbering(plan),
        check_task_type_valid(plan),
        check_reasoning_present(plan),
        check_tools_mutually_exclusive(plan),
        check_tools_are_valid(plan, registry),
        check_conditional_step_no_tools(plan),
        check_conditional_step_no_instructions(plan),
        check_next_step_valid(plan),
        check_conditional_returns_minus_2(plan),
        check_final_step_returns_minus_1(plan),
        check_no_orphan_steps(plan),
        check_output_schema_exists(plan),
    ]
