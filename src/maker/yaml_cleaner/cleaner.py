import yaml

from maker.yaml_cleaner.fixes import attempt_deterministic_fixes, strip_fences


class YAMLParseError(Exception):
    """Raised when YAML cannot be parsed even after repair attempts."""
    pass


class YAMLCleaner:
    async def parse(self, raw_output: str) -> tuple[dict | list, bool]:
        """
        Parse YAML with 3-stage repair pipeline.
        Returns (parsed_data, was_repaired).

        Pipeline:
        1. Strip markdown fences
        2. yaml.safe_load() — if succeeds, return (data, False)
        3. Deterministic fixes — if succeeds, return (data, True)
        4. LLM repair — if succeeds, return (data, True)
        5. Raise YAMLParseError
        """
        # Reject empty/whitespace-only input
        if not raw_output or not raw_output.strip():
            raise YAMLParseError("Empty or whitespace-only input")

        # Stage 1: Strip markdown fences
        stripped = strip_fences(raw_output)

        # Stage 2: Try direct parse
        first_error_msg = ""
        try:
            data = yaml.safe_load(stripped)
            if data is None and stripped.strip() not in ("null", "~", ""):
                raise YAMLParseError("YAML parsed to None unexpectedly")
            return data, False
        except yaml.YAMLError as e:
            first_error_msg = str(e)

        # Stage 3: Deterministic fixes
        fixed = attempt_deterministic_fixes(stripped, first_error_msg)
        if fixed is not None:
            data = yaml.safe_load(fixed)
            return data, True

        # Stage 4: LLM repair
        try:
            repaired_yaml = await self._llm_repair(stripped, first_error_msg)
            data = yaml.safe_load(repaired_yaml)
            return data, True
        except (yaml.YAMLError, YAMLParseError) as e:
            raise YAMLParseError(
                f"All repair attempts failed. Original error: {first_error_msg}"
            ) from e

    async def _llm_repair(self, raw: str, error: str) -> str:
        """Call cheap LLM to fix YAML. Returns repaired YAML string.
        Placeholder — real implementation in Milestone 3."""
        raise YAMLParseError(f"LLM repair not implemented: {error}")
