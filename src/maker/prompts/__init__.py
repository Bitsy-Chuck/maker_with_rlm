from importlib import import_module


def load_prompt(name: str, **kwargs) -> str:
    """Load a prompt by name, format with kwargs."""
    module = import_module(f"maker.prompts.{name}")
    prompt_attr = f"{name.upper()}_PROMPT"
    template = getattr(module, prompt_attr)
    if kwargs:
        return template.format(**kwargs)
    return template
