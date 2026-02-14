import pytest
from maker.red_flag.red_flagger import RedFlagger
from maker.core.models import AgentResult


def make_result(**overrides):
    defaults = {
        "output": {"key": "value"},
        "raw_response": "key: value",
        "was_repaired": False,
        "tokens": 100,
        "cost_usd": 0.001,
        "duration_ms": 500,
        "error": None,
    }
    defaults.update(overrides)
    return AgentResult(**defaults)


class TestRedFlagger:
    def test_valid_dict_passes(self):
        flagger = RedFlagger()
        result = make_result(output={"key": "value"})
        assert flagger.check(result) is False  # not flagged

    def test_nested_dict_passes(self):
        flagger = RedFlagger()
        result = make_result(output={"outer": {"inner": 42}})
        assert flagger.check(result) is False

    def test_empty_dict_passes(self):
        """Empty dict is valid -- maybe step just confirms something."""
        flagger = RedFlagger()
        result = make_result(output={})
        assert flagger.check(result) is False

    def test_list_output_flagged(self):
        flagger = RedFlagger()
        result = make_result(output=["a", "b"])
        assert flagger.check(result) is True  # flagged

    def test_string_output_flagged(self):
        flagger = RedFlagger()
        result = make_result(output="just a string")
        assert flagger.check(result) is True

    def test_number_output_flagged(self):
        flagger = RedFlagger()
        result = make_result(output=42)
        assert flagger.check(result) is True

    def test_none_output_flagged(self):
        flagger = RedFlagger()
        result = make_result(output=None)
        assert flagger.check(result) is True

    def test_agent_error_flagged(self):
        flagger = RedFlagger()
        result = make_result(error="Agent crashed")
        assert flagger.check(result) is True

    def test_reason_for_flagging(self):
        """Red flagger should explain why it flagged."""
        flagger = RedFlagger()

        result = make_result(output="string")
        flagged, reason = flagger.check_with_reason(result)
        assert flagged is True
        assert "dict" in reason.lower()

        result = make_result(error="crash")
        flagged, reason = flagger.check_with_reason(result)
        assert flagged is True
        assert "error" in reason.lower()

    def test_dict_with_extra_fields_passes(self):
        """Extra fields beyond output_schema are allowed (loose validation)."""
        flagger = RedFlagger()
        result = make_result(output={"expected": "val", "bonus": "extra"})
        assert flagger.check(result) is False

    def test_dict_with_error_key_passes(self):
        """A dict containing an 'error' key is still valid output."""
        flagger = RedFlagger()
        result = make_result(output={"error": "something went wrong"})
        assert flagger.check(result) is False  # it's still a dict
