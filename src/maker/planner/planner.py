from maker.core.module import Module
from maker.core.events import TaskSubmitted, PlanCreated
from maker.planner.parser import parse_plan
from maker.yaml_cleaner.cleaner import YAMLCleaner
from maker.prompts import load_prompt
from maker.tools.registry import ToolRegistry
from typing import AsyncIterator
import time


class PlannerModule(Module):
    def __init__(self, registry: ToolRegistry):
        self._registry = registry
        self._yaml_cleaner = YAMLCleaner()

    async def process(self, event) -> AsyncIterator:
        if not isinstance(event, TaskSubmitted):
            return

        # 1. Build prompt with tools
        tools_list = self._format_tools()
        system_prompt = load_prompt("planner_system")
        user_prompt = load_prompt(
            "planner_user",
            instruction=event.instruction,
            tools_list=tools_list,
        )

        # 2. Call SDK
        raw_output = await self._call_sdk(user_prompt, system_prompt=system_prompt, config=event.config)

        # 3. Parse through YAML cleaner
        parsed, _ = await self._yaml_cleaner.parse(raw_output)

        # 4. Parse into Plan (maps 'plan' -> 'steps')
        plan = parse_plan(parsed)

        yield PlanCreated(timestamp=time.time(), plan=plan)

    async def _call_sdk(self, prompt: str, **kwargs) -> str:
        """Call claude-agent-sdk query() and extract final text output.

        Extraction rule:
        1. Iterate all messages from query()
        2. Collect AssistantMessage objects
        3. From final AssistantMessage, take last TextBlock content
        4. If no text found, raise
        """
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

        config = kwargs.get("config")
        system_prompt = kwargs.get("system_prompt", "")

        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            model=config.model if config else "claude-sonnet-4-5",
        )

        last_assistant = None
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                last_assistant = message

        if last_assistant is None:
            raise RuntimeError("No AssistantMessage received from SDK")

        # Extract text from last AssistantMessage
        for block in reversed(last_assistant.content):
            if isinstance(block, TextBlock):
                return block.text

        raise RuntimeError("No TextBlock found in final AssistantMessage")

    def _format_tools(self) -> str:
        """Format tool list for insertion into planner prompt."""
        tools = self._registry.list_tools()
        lines = []
        for tool in sorted(tools, key=lambda t: t.name):
            source_info = f" (MCP: {tool.server_name})" if tool.server_name else ""
            lines.append(f"- {tool.name}: {tool.description}{source_info}")
        return "\n".join(lines)
