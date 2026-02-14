# Milestone 3: Tool Registry + Prompts System

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the tool management system (builtin + MCP registration, validation, listing) and centralized prompt loading system.

**Architecture:** `ToolRegistry` class managing all tool metadata. Prompts as Python string constants in `src/maker/prompts/`, loaded via `load_prompt()` with template substitution.

**Tech Stack:** Python 3.11+, `pytest`

**Depends On:** Milestone 1 (data models for `ToolInfo`, `MCPServerConfig`)

---

## Task 1: Tool Registry

**Files:**
- Create: `src/maker/tools/__init__.py`
- Create: `src/maker/tools/registry.py`
- Create: `src/maker/tools/builtin.py`
- Create: `tests/test_tools/__init__.py`
- Create: `tests/test_tools/test_registry.py`

**Step 1: Write tests**

```python
# tests/test_tools/test_registry.py
import pytest
from maker.tools.registry import ToolRegistry
from maker.core.models import ToolInfo, MCPServerConfig


class TestBuiltinRegistration:
    def test_register_builtin(self):
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")
        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "Read"
        assert tools[0].source == "builtin"

    def test_register_multiple_builtins(self):
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")
        registry.register_builtin("Write", "Write files")
        assert len(registry.list_tools()) == 2

    def test_duplicate_builtin_raises(self):
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")
        with pytest.raises(ValueError, match="already registered"):
            registry.register_builtin("Read", "Read files again")


class TestMCPRegistration:
    def test_register_mcp_server(self):
        registry = ToolRegistry()
        config = MCPServerConfig(command="npx", args=["-y", "server"])
        tools = [
            ToolInfo(name="mcp__gh__list_issues", description="List issues", source="mcp", server_name="gh"),
            ToolInfo(name="mcp__gh__create_issue", description="Create issue", source="mcp", server_name="gh"),
        ]
        registry.register_mcp_server("gh", config, tools)

        all_tools = registry.list_tools()
        assert len(all_tools) == 2
        assert all_tools[0].server_name == "gh"

    def test_unregister_mcp_server(self):
        registry = ToolRegistry()
        config = MCPServerConfig(command="npx", args=["server"])
        tools = [ToolInfo(name="mcp__gh__list", description="List", source="mcp", server_name="gh")]
        registry.register_mcp_server("gh", config, tools)
        assert len(registry.list_tools()) == 1

        registry.unregister_mcp_server("gh")
        assert len(registry.list_tools()) == 0

    def test_unregister_nonexistent_server_raises(self):
        registry = ToolRegistry()
        with pytest.raises(ValueError, match="not registered"):
            registry.unregister_mcp_server("nonexistent")

    def test_duplicate_mcp_server_raises(self):
        registry = ToolRegistry()
        config = MCPServerConfig(command="npx", args=["server"])
        tools = [ToolInfo(name="mcp__gh__list", description="List", source="mcp", server_name="gh")]
        registry.register_mcp_server("gh", config, tools)
        with pytest.raises(ValueError, match="already registered"):
            registry.register_mcp_server("gh", config, tools)

    def test_mcp_tool_name_conflict_with_builtin_raises(self):
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")
        config = MCPServerConfig(command="npx", args=["server"])
        tools = [ToolInfo(name="Read", description="Conflict", source="mcp", server_name="bad")]
        with pytest.raises(ValueError, match="already registered"):
            registry.register_mcp_server("bad", config, tools)


class TestToolListing:
    def test_list_tools(self):
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")
        registry.register_builtin("Bash", "Run commands")
        tools = registry.list_tools()
        names = [t.name for t in tools]
        assert "Read" in names
        assert "Bash" in names

    def test_get_tool_names(self):
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")
        registry.register_builtin("Bash", "Run commands")
        names = registry.get_tool_names()
        assert names == ["Bash", "Read"]  # sorted

    def test_empty_registry(self):
        registry = ToolRegistry()
        assert registry.list_tools() == []
        assert registry.get_tool_names() == []


class TestToolValidation:
    def test_validate_existing_tool(self):
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")
        assert registry.validate_tool_name("Read") is True

    def test_validate_nonexistent_tool(self):
        registry = ToolRegistry()
        registry.register_builtin("Read", "Read files")
        assert registry.validate_tool_name("FakeTool") is False

    def test_validate_mcp_tool(self):
        registry = ToolRegistry()
        config = MCPServerConfig(command="npx", args=["server"])
        tools = [ToolInfo(name="mcp__gh__list", description="List", source="mcp", server_name="gh")]
        registry.register_mcp_server("gh", config, tools)
        assert registry.validate_tool_name("mcp__gh__list") is True
        assert registry.validate_tool_name("mcp__gh__fake") is False


class TestMCPServerConfigs:
    def test_get_mcp_server_configs(self):
        registry = ToolRegistry()
        config = MCPServerConfig(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_TOKEN": "abc"},
        )
        tools = [ToolInfo(name="mcp__gh__list", description="List", source="mcp", server_name="gh")]
        registry.register_mcp_server("gh", config, tools)

        configs = registry.get_mcp_server_configs()
        assert "gh" in configs
        assert configs["gh"]["command"] == "npx"
        assert configs["gh"]["env"]["GITHUB_TOKEN"] == "abc"

    def test_get_mcp_configs_empty(self):
        registry = ToolRegistry()
        assert registry.get_mcp_server_configs() == {}


class TestDefaultBuiltins:
    def test_with_defaults_loads_builtins(self):
        """ToolRegistry.with_defaults() should pre-register Claude Code builtins."""
        registry = ToolRegistry.with_defaults()
        names = registry.get_tool_names()
        assert "Read" in names
        assert "Write" in names
        assert "Edit" in names
        assert "Bash" in names
        assert "Glob" in names
        assert "Grep" in names
        assert "WebSearch" in names
        assert "WebFetch" in names
        assert "AskUserQuestion" in names
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement**

Key interfaces for `src/maker/tools/registry.py`:

```python
from maker.core.models import ToolInfo, MCPServerConfig


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolInfo] = {}           # name → ToolInfo
        self._mcp_servers: dict[str, MCPServerConfig] = {}  # server_name → config
        self._mcp_server_tools: dict[str, list[str]] = {}  # server_name → tool names

    @classmethod
    def with_defaults(cls) -> "ToolRegistry":
        """Create registry with built-in Claude Code tools pre-registered."""
        ...

    def register_builtin(self, tool_name: str, description: str) -> None: ...
    def register_mcp_server(self, server_name: str, server_config: MCPServerConfig, tools: list[ToolInfo]) -> None: ...
    def unregister_mcp_server(self, server_name: str) -> None: ...
    def list_tools(self) -> list[ToolInfo]: ...
    def get_tool_names(self) -> list[str]: ...
    def validate_tool_name(self, name: str) -> bool: ...
    def get_mcp_server_configs(self) -> dict: ...
```

Key content of `src/maker/tools/builtin.py`:

```python
BUILTIN_TOOLS = [
    ("Read", "Read files (text, images, PDFs, notebooks)"),
    ("Write", "Write files"),
    ("Edit", "Edit file content"),
    ("Bash", "Execute shell commands"),
    ("Glob", "File pattern matching"),
    ("Grep", "Search with regex"),
    ("WebSearch", "Search the web"),
    ("WebFetch", "Fetch and analyze web content"),
    ("AskUserQuestion", "Get user input (Tier-3 implicit tool)"),
]
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/tools/ tests/test_tools/
git commit -m "feat: add tool registry with builtin and MCP support"
```

---

## Task 2: Prompts System

**Files:**
- Modify: `src/maker/prompts/__init__.py` (expand from M2's minimal version)
- Create: `src/maker/prompts/planner_system.py`
- Create: `src/maker/prompts/planner_user.py`
- Create: `src/maker/prompts/executor_step.py`
- Create: `src/maker/prompts/quality_single_purpose.py`
- Create: `src/maker/prompts/quality_self_contained.py`
- Create: `src/maker/prompts/quality_max_k_tools.py`
- Create: `src/maker/prompts/quality_non_overlapping.py`
- Create: `src/maker/prompts/quality_maximally_decomposed.py`
- Create: `src/maker/prompts/quality_appropriately_merged.py`
- Create: `tests/test_prompts/__init__.py`
- Create: `tests/test_prompts/test_prompts.py`

**Step 1: Write tests**

```python
# tests/test_prompts/test_prompts.py
import pytest
from maker.prompts import load_prompt


class TestLoadPrompt:
    def test_load_existing_prompt(self):
        prompt = load_prompt("planner_system")
        assert isinstance(prompt, str)
        assert len(prompt) > 100  # planner prompt is substantial

    def test_load_with_kwargs(self):
        prompt = load_prompt("planner_user", instruction="Do X", tools_list="Read, Write")
        assert "Do X" in prompt
        assert "Read, Write" in prompt

    def test_load_nonexistent_raises(self):
        with pytest.raises(KeyError):
            load_prompt("nonexistent_prompt")

    def test_yaml_fixer_prompt(self):
        prompt = load_prompt("yaml_fixer", raw_yaml="bad: [", error="expected ]")
        assert "bad: [" in prompt
        assert "expected ]" in prompt

    def test_executor_step_prompt(self):
        prompt = load_prompt(
            "executor_step",
            task_description="Fetch data",
            context="step_0_output:\n  key: value",
            output_schema="{data: string}",
        )
        assert "Fetch data" in prompt
        assert "step_0_output" in prompt

    def test_all_quality_prompts_load(self):
        quality_prompts = [
            "quality_single_purpose",
            "quality_self_contained",
            "quality_max_k_tools",
            "quality_non_overlapping",
            "quality_maximally_decomposed",
            "quality_appropriately_merged",
        ]
        for name in quality_prompts:
            prompt = load_prompt(name)
            assert isinstance(prompt, str)
            assert len(prompt) > 20

    def test_planner_system_contains_key_sections(self):
        """Planner prompt should contain adapted SPEC content."""
        prompt = load_prompt("planner_system")
        assert "AskUserQuestion" in prompt  # adapted from human_input_tool
        assert "ask_duckie" not in prompt   # dropped per design
        assert "Maximal Task Decomposition" in prompt
        assert "output_schema" in prompt

    def test_planner_system_no_human_input_tool(self):
        """Planner prompt should NOT reference human_input_tool (replaced)."""
        prompt = load_prompt("planner_system")
        assert "human_input_tool" not in prompt
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement**

`src/maker/prompts/__init__.py`:

```python
from maker.prompts.planner_system import PLANNER_SYSTEM_PROMPT
from maker.prompts.planner_user import PLANNER_USER_PROMPT
from maker.prompts.yaml_fixer import YAML_FIXER_PROMPT
from maker.prompts.executor_step import EXECUTOR_STEP_PROMPT
from maker.prompts.quality_single_purpose import QUALITY_SINGLE_PURPOSE_PROMPT
# ... etc

_PROMPTS = {
    "planner_system": PLANNER_SYSTEM_PROMPT,
    "planner_user": PLANNER_USER_PROMPT,
    "yaml_fixer": YAML_FIXER_PROMPT,
    "executor_step": EXECUTOR_STEP_PROMPT,
    "quality_single_purpose": QUALITY_SINGLE_PURPOSE_PROMPT,
    # ... etc
}

def load_prompt(name: str, **kwargs) -> str:
    """Load a prompt by name, optionally format with kwargs."""
    if name not in _PROMPTS:
        raise KeyError(f"Prompt '{name}' not found. Available: {list(_PROMPTS.keys())}")
    prompt = _PROMPTS[name]
    if kwargs:
        prompt = prompt.format(**kwargs)
    return prompt
```

For `planner_system.py`: Copy the full planner prompt from `SPEC.md` with these adaptations:
- Replace all instances of `human_input_tool` with `AskUserQuestion`
- Remove all references to `ask_duckie` (Tier 3 becomes just `AskUserQuestion`)
- Keep all other content exactly as-is

For `planner_user.py`:
```python
PLANNER_USER_PROMPT = """User Instruction:
{instruction}

Available Tools:
{tools_list}

Generate the execution plan as YAML."""
```

For `executor_step.py`:
```python
EXECUTOR_STEP_PROMPT = """You are an autonomous agent executing a single task. You have ZERO knowledge of the overall plan or objective. You only know what is described below.

## Task
{task_description}

## Context from Previous Steps
{context}

## Expected Output Schema
{output_schema}

## Instructions
1. Execute the task described above using the available tools
2. Produce output matching the expected schema as YAML
3. Output ONLY valid YAML — no markdown fences, no commentary
4. If you cannot complete the task, output: {{error: "description of what went wrong"}}"""
```

Each quality prompt is a short template that asks a cheap LLM to score a plan step on a 0-1 scale for that dimension. Keep them simple.

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/maker/prompts/ tests/test_prompts/
git commit -m "feat: add centralized prompts system with all prompt templates"
```

---

## Definition of Done

- [ ] `uv run pytest tests/test_tools/ tests/test_prompts/ -v` — all tests pass
- [ ] ToolRegistry registers/unregisters builtin and MCP tools
- [ ] Duplicate names raise errors
- [ ] `ToolRegistry.with_defaults()` pre-registers all Claude Code builtins
- [ ] `validate_tool_name()` works for builtin and MCP tools
- [ ] `get_mcp_server_configs()` returns configs in SDK-compatible format
- [ ] `load_prompt()` loads all prompts with optional kwarg formatting
- [ ] Planner prompt adapted from SPEC (AskUserQuestion, no ask_duckie)
- [ ] All quality prompts loadable
- [ ] All code committed
