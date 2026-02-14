from maker.core.models import Plan, PlanStep


def parse_plan(raw: dict) -> Plan:
    """Parse a raw YAML dict into a Plan dataclass.

    Handles the YAML key mapping: 'plan' -> 'steps'.
    Validates required fields exist.
    """
    if not isinstance(raw, dict):
        raise ValueError("Plan must be a dict")

    if "reasoning" not in raw:
        raise ValueError("Plan must have 'reasoning' field")

    # Map 'plan' -> 'steps'
    step_list = raw.get("plan") or raw.get("steps")
    if step_list is None:
        raise ValueError("Plan must have 'plan' or 'steps' field")
    if not isinstance(step_list, list):
        raise ValueError("'plan'/'steps' must be a list")

    steps = [_parse_step(s) for s in step_list]
    return Plan(reasoning=raw["reasoning"], steps=steps)


def _parse_step(raw_step: dict) -> PlanStep:
    """Parse a raw step dict into a PlanStep dataclass."""
    return PlanStep(
        step=raw_step["step"],
        task_type=raw_step["task_type"],
        title=raw_step["title"],
        task_description=raw_step["task_description"],
        primary_tools=raw_step["primary_tools"],
        fallback_tools=raw_step["fallback_tools"],
        primary_tool_instructions=raw_step["primary_tool_instructions"],
        fallback_tool_instructions=raw_step["fallback_tool_instructions"],
        input_variables=raw_step["input_variables"],
        output_variable=raw_step["output_variable"],
        output_schema=raw_step["output_schema"],
        next_step_sequence_number=raw_step["next_step_sequence_number"],
    )
