from maker.core.models import AgentResult


class RedFlagger:
    def check(self, result: AgentResult) -> bool:
        """Returns True if the result should be discarded (red-flagged)."""
        flagged, _ = self.check_with_reason(result)
        return flagged

    def check_with_reason(self, result: AgentResult) -> tuple[bool, str]:
        """Returns (is_flagged, reason)."""
        if result.error:
            return True, f"Agent error: {result.error}"
        if not isinstance(result.output, dict):
            return True, f"Output is not a dict (got {type(result.output).__name__})"
        return False, ""
