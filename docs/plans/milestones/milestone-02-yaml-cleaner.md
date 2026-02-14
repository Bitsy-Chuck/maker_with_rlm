# Milestone 2: YAML Cleaner

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standalone 3-stage YAML parsing utility with deterministic fixes and LLM repair fallback. Used by every module that processes LLM output.

**Architecture:** `YAMLCleaner` class with a pipeline: strip fences → `yaml.safe_load()` → deterministic fixes → LLM repair → raise. Each stage is isolated and testable.

**Tech Stack:** Python 3.11+, `pyyaml`, `pytest`, `pytest-asyncio`

**Depends On:** Milestone 1 (project setup)

---

## Task 1: YAMLCleaner Core + Fence Stripping

**Files:**
- Create: `src/maker/yaml_cleaner/__init__.py`
- Create: `src/maker/yaml_cleaner/cleaner.py`
- Create: `src/maker/yaml_cleaner/fixes.py`
- Create: `tests/test_yaml_cleaner/__init__.py`
- Create: `tests/test_yaml_cleaner/test_cleaner.py`

**Step 1: Write tests**

```python
# tests/test_yaml_cleaner/test_cleaner.py
import pytest
from maker.yaml_cleaner.cleaner import YAMLCleaner, YAMLParseError


class TestCleanYAML:
    """YAML that should parse on the first try with no repair."""

    async def test_simple_dict(self):
        cleaner = YAMLCleaner()
        result, repaired = await cleaner.parse("key: value")
        assert result == {"key": "value"}
        assert repaired is False

    async def test_nested_dict(self):
        cleaner = YAMLCleaner()
        raw = "outer:\n  inner: 42\n  list:\n    - a\n    - b"
        result, repaired = await cleaner.parse(raw)
        assert result == {"outer": {"inner": 42, "list": ["a", "b"]}}
        assert repaired is False

    async def test_list_output(self):
        cleaner = YAMLCleaner()
        result, repaired = await cleaner.parse("- one\n- two\n- three")
        assert result == ["one", "two", "three"]
        assert repaired is False

    async def test_multiline_strings(self):
        cleaner = YAMLCleaner()
        raw = "description: |\n  line one\n  line two"
        result, repaired = await cleaner.parse(raw)
        assert "line one" in result["description"]
        assert repaired is False


class TestFenceStripping:
    """YAML wrapped in markdown code fences."""

    async def test_yaml_fence(self):
        cleaner = YAMLCleaner()
        raw = "```yaml\nkey: value\n```"
        result, repaired = await cleaner.parse(raw)
        assert result == {"key": "value"}
        assert repaired is False

    async def test_plain_fence(self):
        cleaner = YAMLCleaner()
        raw = "```\nkey: value\n```"
        result, repaired = await cleaner.parse(raw)
        assert result == {"key": "value"}
        assert repaired is False

    async def test_fence_with_prose_before(self):
        cleaner = YAMLCleaner()
        raw = "Here is the plan:\n\n```yaml\nkey: value\n```"
        result, repaired = await cleaner.parse(raw)
        assert result == {"key": "value"}
        assert repaired is False

    async def test_fence_with_prose_after(self):
        cleaner = YAMLCleaner()
        raw = "```yaml\nkey: value\n```\n\nLet me know if this looks good."
        result, repaired = await cleaner.parse(raw)
        assert result == {"key": "value"}
        assert repaired is False

    async def test_multiple_fences_takes_first(self):
        cleaner = YAMLCleaner()
        raw = "```yaml\nfirst: true\n```\n\nAnother block:\n```yaml\nsecond: true\n```"
        result, repaired = await cleaner.parse(raw)
        assert result == {"first": True}

    async def test_partial_fence_opening_only(self):
        cleaner = YAMLCleaner()
        raw = "```yaml\nkey: value"
        result, repaired = await cleaner.parse(raw)
        assert result == {"key": "value"}

    async def test_no_fences_returns_raw(self):
        cleaner = YAMLCleaner()
        raw = "key: value"
        result, repaired = await cleaner.parse(raw)
        assert result == {"key": "value"}


class TestDeterministicFixes:
    """YAML with common issues that deterministic fixes can handle."""

    async def test_tabs_to_spaces(self):
        cleaner = YAMLCleaner()
        raw = "outer:\n\tinner: value"
        result, repaired = await cleaner.parse(raw)
        assert result == {"outer": {"inner": "value"}}
        assert repaired is True

    async def test_trailing_comma_in_list(self):
        """Trailing comma after a value: `key: value,`"""
        cleaner = YAMLCleaner()
        raw = "items:\n  - first,\n  - second"
        # This may or may not need fixing depending on YAML parser behavior
        # The test validates the cleaner handles it without error
        result, repaired = await cleaner.parse(raw)
        assert isinstance(result, dict)

    async def test_unquoted_colon_in_value(self):
        """Values with colons that confuse the parser."""
        cleaner = YAMLCleaner()
        raw = 'url: https://example.com:8080/path'
        result, repaired = await cleaner.parse(raw)
        assert "example.com" in str(result["url"])


class TestLLMRepair:
    """Test the LLM repair fallback path (mocked)."""

    async def test_llm_repair_called_on_unparseable(self):
        """When deterministic fixes fail, LLM repair is attempted."""
        cleaner = YAMLCleaner()

        # Track whether _llm_repair was called
        repair_called = False
        original_repair = cleaner._llm_repair

        async def mock_repair(raw, error):
            nonlocal repair_called
            repair_called = True
            return "key: fixed_by_llm"

        cleaner._llm_repair = mock_repair

        # Severely malformed YAML that deterministic fixes can't handle
        raw = "{{{{not yaml at all}}}}"
        result, repaired = await cleaner.parse(raw)
        assert repair_called
        assert result == {"key": "fixed_by_llm"}
        assert repaired is True

    async def test_llm_repair_fails_raises_error(self):
        """When LLM repair also fails, YAMLParseError is raised."""
        cleaner = YAMLCleaner()

        async def failing_repair(raw, error):
            raise YAMLParseError(f"LLM repair failed: {error}")

        cleaner._llm_repair = failing_repair

        raw = "{{{{not yaml at all}}}}"
        with pytest.raises(YAMLParseError):
            await cleaner.parse(raw)

    async def test_was_repaired_flag_true_for_deterministic_fix(self):
        """If deterministic fixes were needed, was_repaired is True."""
        cleaner = YAMLCleaner()
        raw = "```yaml\nouter:\n\tinner: value\n```"
        result, repaired = await cleaner.parse(raw)
        assert result == {"outer": {"inner": "value"}}
        # Fence stripping alone doesn't count as repair,
        # but tab fix does
        assert repaired is True

    async def test_was_repaired_flag_false_for_clean(self):
        cleaner = YAMLCleaner()
        result, repaired = await cleaner.parse("key: value")
        assert repaired is False


class TestEdgeCases:
    async def test_empty_string_raises(self):
        cleaner = YAMLCleaner()
        with pytest.raises(YAMLParseError):
            await cleaner.parse("")

    async def test_whitespace_only_raises(self):
        cleaner = YAMLCleaner()
        with pytest.raises(YAMLParseError):
            await cleaner.parse("   \n\n  ")

    async def test_none_yaml_value(self):
        """YAML `null` should parse but may need special handling."""
        cleaner = YAMLCleaner()
        result, repaired = await cleaner.parse("key: null")
        assert result == {"key": None}

    async def test_boolean_yaml_values(self):
        cleaner = YAMLCleaner()
        result, _ = await cleaner.parse("flag: true\nother: false")
        assert result == {"flag": True, "other": False}

    async def test_numeric_yaml_values(self):
        cleaner = YAMLCleaner()
        result, _ = await cleaner.parse("count: 42\nprice: 3.14")
        assert result == {"count": 42, "price": 3.14}
```

**Step 2: Run tests — expect FAIL**

Run: `cd /Users/air/Dropbox/air/projects/maker && uv run pytest tests/test_yaml_cleaner/ -v`

**Step 3: Implement**

Key interfaces for `src/maker/yaml_cleaner/cleaner.py`:

```python
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
        ...

    async def _llm_repair(self, raw: str, error: str) -> str:
        """Call cheap LLM to fix YAML. Returns repaired YAML string."""
        ...
```

Key interfaces for `src/maker/yaml_cleaner/fixes.py`:

```python
def strip_fences(raw: str) -> str:
    """Remove markdown code fences. Handles prose, multiple blocks, partial fences.
    Returns content of first fenced block, or raw input if no fences found."""
    ...

def attempt_deterministic_fixes(raw: str, error: str) -> str | None:
    """Try common fixes: tabs→spaces, trailing commas, unquoted special chars.
    Returns fixed string or None if no fix worked."""
    ...

def fix_tabs(raw: str) -> str:
    """Replace leading tabs with 2 spaces."""
    ...

def fix_trailing_commas(raw: str) -> str:
    """Remove trailing commas from values."""
    ...
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/yaml_cleaner/ tests/test_yaml_cleaner/
git commit -m "feat: add YAML cleaner with 3-stage repair pipeline"
```

---

## Task 2: YAML Fixer Prompt

**Files:**
- Create: `src/maker/prompts/__init__.py`
- Create: `src/maker/prompts/yaml_fixer.py`

**Note:** The full prompts system is in Milestone 3, but the YAML cleaner needs the fixer prompt. Create just the minimal `load_prompt()` and `yaml_fixer.py` here. Milestone 3 will expand the prompts system.

**Step 1: Create `src/maker/prompts/yaml_fixer.py`**

```python
YAML_FIXER_PROMPT = """You are a YAML repair tool. You receive malformed YAML and the error message from the parser.

Your job: fix the YAML so it parses correctly. Return ONLY the fixed YAML with no explanation, no markdown fences, no commentary.

Rules:
- Preserve the original meaning and structure as much as possible
- Fix indentation, quoting, special characters, and syntax errors
- Do not add or remove fields
- Do not change values unless necessary to fix syntax
- Output raw YAML only — no ```yaml fences, no prose

Malformed YAML:
{raw_yaml}

Parser error:
{error}

Fixed YAML:"""
```

**Step 2: Create minimal `src/maker/prompts/__init__.py`**

```python
def load_prompt(name: str, **kwargs) -> str:
    """Load a prompt by name, format with kwargs."""
    ...
```

**Step 3: Commit**

```bash
git add src/maker/prompts/
git commit -m "feat: add YAML fixer prompt and minimal prompt loader"
```

---

## Definition of Done

- [ ] `uv run pytest tests/test_yaml_cleaner/ -v` — all tests pass
- [ ] Clean YAML passes through without repair
- [ ] Markdown fences stripped (all variants: yaml, plain, prose before/after, multiple blocks, partial)
- [ ] Deterministic fixes handle tabs, trailing commas, common issues
- [ ] LLM repair path is called when deterministic fixes fail (mocked in tests)
- [ ] `YAMLParseError` raised when all repair attempts fail
- [ ] `was_repaired` flag correctly reflects whether repair was needed
- [ ] Edge cases handled: empty string, whitespace, null values, booleans, numbers
- [ ] All code committed
