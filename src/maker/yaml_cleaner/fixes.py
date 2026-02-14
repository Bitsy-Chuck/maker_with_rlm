import re

import yaml


def strip_fences(raw: str) -> str:
    """Remove markdown code fences. Handles prose, multiple blocks, partial fences.
    Returns content of first fenced block, or raw input if no fences found."""
    # Match ```yaml or ``` opening fence
    pattern = r"```(?:yaml|yml)?\s*\n(.*?)(?:\n```|$)"
    match = re.search(pattern, raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    return raw


def fix_tabs(raw: str) -> str:
    """Replace leading tabs with 2 spaces."""
    lines = raw.split("\n")
    fixed = []
    for line in lines:
        # Count leading tabs and replace with 2 spaces each
        stripped = line.lstrip("\t")
        tab_count = len(line) - len(stripped)
        fixed.append("  " * tab_count + stripped)
    return "\n".join(fixed)


def fix_trailing_commas(raw: str) -> str:
    """Remove trailing commas from values."""
    # Match lines where value ends with a comma (but not inside quotes)
    return re.sub(r",\s*$", "", raw, flags=re.MULTILINE)


def attempt_deterministic_fixes(raw: str, error: str) -> str | None:
    """Try common fixes: tabs->spaces, trailing commas, unquoted special chars.
    Returns fixed string or None if no fix worked."""
    fixes = [fix_tabs, fix_trailing_commas]

    for fix_fn in fixes:
        fixed = fix_fn(raw)
        if fixed != raw:
            try:
                yaml.safe_load(fixed)
                return fixed
            except yaml.YAMLError:
                # This fix didn't help, try next
                raw = fixed  # Keep accumulated fixes

    # Try all fixes applied together
    try:
        yaml.safe_load(raw)
        return raw
    except yaml.YAMLError:
        return None
