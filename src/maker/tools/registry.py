from maker.core.models import ToolInfo, MCPServerConfig
from maker.tools.builtin import BUILTIN_TOOLS


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolInfo] = {}
        self._mcp_servers: dict[str, MCPServerConfig] = {}
        self._mcp_server_tools: dict[str, list[str]] = {}

    @classmethod
    def with_defaults(cls) -> "ToolRegistry":
        """Create registry with built-in Claude Code tools pre-registered."""
        registry = cls()
        for name, description in BUILTIN_TOOLS:
            registry.register_builtin(name, description)
        return registry

    def register_builtin(self, tool_name: str, description: str) -> None:
        if tool_name in self._tools:
            raise ValueError(f"Tool '{tool_name}' already registered")
        self._tools[tool_name] = ToolInfo(
            name=tool_name, description=description, source="builtin"
        )

    def register_mcp_server(
        self, server_name: str, server_config: MCPServerConfig, tools: list[ToolInfo]
    ) -> None:
        if server_name in self._mcp_servers:
            raise ValueError(f"MCP server '{server_name}' already registered")
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"Tool '{tool.name}' already registered")
        self._mcp_servers[server_name] = server_config
        self._mcp_server_tools[server_name] = [t.name for t in tools]
        for tool in tools:
            self._tools[tool.name] = tool

    def unregister_mcp_server(self, server_name: str) -> None:
        if server_name not in self._mcp_servers:
            raise ValueError(f"MCP server '{server_name}' not registered")
        for tool_name in self._mcp_server_tools[server_name]:
            del self._tools[tool_name]
        del self._mcp_servers[server_name]
        del self._mcp_server_tools[server_name]

    def list_tools(self) -> list[ToolInfo]:
        return list(self._tools.values())

    def get_tool_names(self) -> list[str]:
        return sorted(self._tools.keys())

    def validate_tool_name(self, name: str) -> bool:
        return name in self._tools

    def get_mcp_server_configs(self) -> dict:
        return {
            name: {
                "command": config.command,
                "args": config.args,
                "env": config.env,
            }
            for name, config in self._mcp_servers.items()
        }
