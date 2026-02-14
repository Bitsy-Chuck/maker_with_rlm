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
