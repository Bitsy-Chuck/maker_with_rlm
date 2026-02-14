import yaml
from maker.core.models import PlanStep


class ContextBuilder:
    def build(self, step: PlanStep, step_outputs: dict[str, dict]) -> str:
        """Build context string by injecting full outputs of referenced steps.

        From each input_variable, extracts the step name (everything before first '.'),
        then injects the full output dict of that step as YAML.

        Returns empty string if no input_variables.
        """
        if not step.input_variables:
            return ""

        # Extract unique step names
        step_names = set()
        for var in step.input_variables:
            step_name = var.split(".")[0]
            step_names.add(step_name)

        # Build context dict
        context = {}
        for name in sorted(step_names):
            if name not in step_outputs:
                raise KeyError(f"Step output '{name}' not found. Available: {list(step_outputs.keys())}")
            context[name] = step_outputs[name]

        return yaml.dump(context, default_flow_style=False)
