from maker.prompts.planner_system import PLANNER_SYSTEM_PROMPT
from maker.prompts.planner_user import PLANNER_USER_PROMPT
from maker.prompts.yaml_fixer import YAML_FIXER_PROMPT
from maker.prompts.executor_step import EXECUTOR_STEP_PROMPT
from maker.prompts.quality_single_purpose import QUALITY_SINGLE_PURPOSE_PROMPT
from maker.prompts.quality_self_contained import QUALITY_SELF_CONTAINED_PROMPT
from maker.prompts.quality_max_k_tools import QUALITY_MAX_K_TOOLS_PROMPT
from maker.prompts.quality_non_overlapping import QUALITY_NON_OVERLAPPING_PROMPT
from maker.prompts.quality_maximally_decomposed import QUALITY_MAXIMALLY_DECOMPOSED_PROMPT
from maker.prompts.quality_appropriately_merged import QUALITY_APPROPRIATELY_MERGED_PROMPT

_PROMPTS = {
    "planner_system": PLANNER_SYSTEM_PROMPT,
    "planner_user": PLANNER_USER_PROMPT,
    "yaml_fixer": YAML_FIXER_PROMPT,
    "executor_step": EXECUTOR_STEP_PROMPT,
    "quality_single_purpose": QUALITY_SINGLE_PURPOSE_PROMPT,
    "quality_self_contained": QUALITY_SELF_CONTAINED_PROMPT,
    "quality_max_k_tools": QUALITY_MAX_K_TOOLS_PROMPT,
    "quality_non_overlapping": QUALITY_NON_OVERLAPPING_PROMPT,
    "quality_maximally_decomposed": QUALITY_MAXIMALLY_DECOMPOSED_PROMPT,
    "quality_appropriately_merged": QUALITY_APPROPRIATELY_MERGED_PROMPT,
}


def load_prompt(name: str, **kwargs) -> str:
    """Load a prompt by name, optionally format with kwargs."""
    if name not in _PROMPTS:
        raise KeyError(f"Prompt '{name}' not found. Available: {list(_PROMPTS.keys())}")
    prompt = _PROMPTS[name]
    if kwargs:
        prompt = prompt.format(**kwargs)
    return prompt
