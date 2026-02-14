# Claude Agent SDK Reference

> Formerly "Claude Code SDK" — renamed to **Claude Agent SDK**.

## Installation

**Python:**
```bash
uv init && uv add claude-agent-sdk
# or
pip install claude-agent-sdk
```

**TypeScript:**
```bash
npm install @anthropic-ai/claude-agent-sdk
```

**Environment:**
```bash
export ANTHROPIC_API_KEY=your-api-key
```

---

## Core API: `query()`

### Python

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def main():
    async for message in query(
        prompt="Review utils.py for bugs and fix them",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Edit", "Glob"],
            permission_mode="acceptEdits",
        ),
    ):
        print(message)

asyncio.run(main())
```

### TypeScript

```typescript
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Review utils.py for bugs and fix them",
  options: {
    allowedTools: ["Read", "Edit", "Glob"],
    permissionMode: "acceptEdits"
  }
})) {
  console.log(message);
}
```

---

## Session-Based Conversations

### Multi-Turn with ClaudeSDKClient (Python)

```python
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
)

async def main():
    async with ClaudeSDKClient() as client:
        await client.query("What's the capital of France?")
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"Claude: {block.text}")

        # Follow-up — Claude remembers context
        await client.query("What's the population of that city?")
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"Claude: {block.text}")

asyncio.run(main())
```

### Session Resumption (Python)

```python
from claude_agent_sdk import query, ClaudeAgentOptions, SystemMessage

session_id = None

async for message in query(
    prompt="Design a REST API",
    options=ClaudeAgentOptions(model="claude-opus-4-6"),
):
    if isinstance(message, SystemMessage) and message.subtype == "init":
        session_id = message.data.get("session_id")
    print(message)

# Resume same session later
async for message in query(
    prompt="Add authentication to the API",
    options=ClaudeAgentOptions(resume=session_id),
):
    print(message)
```

---

## Permission Modes

| Mode | Behavior |
|------|----------|
| `default` | No auto-approvals; calls `canUseTool` callback |
| `acceptEdits` | Auto-approve file edits (Edit, Write) |
| `bypassPermissions` | Auto-approve all tools (use with caution) |
| `plan` | No execution, planning only |

### Custom Permission Handler (Python)

```python
async def can_use_tool(tool_name, input_data, context):
    if tool_name == "Bash" and "rm -rf" in str(input_data):
        return PermissionResultDeny(message="Dangerous command blocked")
    return PermissionResultAllow(updated_input=input_data)

options = ClaudeAgentOptions(
    can_use_tool=can_use_tool,
    permission_mode="default"
)
```

---

## Built-in Tools

- `Read` — Read files (text, images, PDFs, notebooks)
- `Write` — Write files
- `Edit` — Edit file content
- `Bash` — Execute commands
- `Glob` — File pattern matching
- `Grep` — Search with regex
- `WebSearch` — Search the web
- `WebFetch` — Fetch and analyze web content
- `Task` — Invoke subagents
- `AskUserQuestion` — Get user input
- `NotebookEdit` — Edit Jupyter notebooks
- `TodoWrite` — Manage task lists

---

## Custom Tools via MCP

### Python

```python
from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeAgentOptions
from typing import Any

@tool("add", "Add two numbers", {"a": float, "b": float})
async def add(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": f"Sum: {args['a'] + args['b']}"}]
    }

calculator = create_sdk_mcp_server(
    name="calculator",
    version="1.0.0",
    tools=[add]
)

options = ClaudeAgentOptions(
    mcp_servers={"calc": calculator},
    allowed_tools=["mcp__calc__add"]
)
```

### TypeScript

```typescript
import { query, tool, createSdkMcpServer } from "@anthropic-ai/claude-agent-sdk";
import { z } from "zod";

const calculator = createSdkMcpServer({
  name: "calculator",
  version: "1.0.0",
  tools: [
    tool(
      "add",
      "Add two numbers",
      { a: z.number(), b: z.number() },
      async (args) => ({
        content: [{ type: "text", text: `Sum: ${args.a + args.b}` }]
      })
    )
  ]
});

for await (const message of query({
  prompt: generateMessages(),
  options: {
    mcpServers: { calc: calculator },
    allowedTools: ["mcp__calc__add"]
  }
})) {
  console.log(message);
}
```

**MCP Tool Naming Convention:** `mcp__{server-name}__{tool-name}`

---

## External MCP Servers

```python
options = ClaudeAgentOptions(
    mcp_servers={
        "github": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_TOKEN": os.environ["GITHUB_TOKEN"]}
        }
    },
    allowed_tools=["mcp__github__list_issues"]
)
```

---

## Subagents / Multi-Agent

### Python

```python
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

async for message in query(
    prompt="Review this code for security issues",
    options=ClaudeAgentOptions(
        allowed_tools=["Read", "Grep", "Glob", "Task"],
        agents={
            "code-reviewer": AgentDefinition(
                description="Expert code review specialist",
                prompt="You are a security code reviewer...",
                tools=["Read", "Grep", "Glob"],
                model="sonnet"
            ),
            "test-runner": AgentDefinition(
                description="Runs test suites",
                prompt="You are a test execution specialist.",
                tools=["Bash", "Read", "Grep"]
            )
        }
    )
):
    print(message)
```

### TypeScript

```typescript
for await (const message of query({
  prompt: "Review this code for security issues",
  options: {
    allowedTools: ["Read", "Grep", "Glob", "Task"],
    agents: {
      "code-reviewer": {
        description: "Expert code review specialist",
        prompt: "You are a security code reviewer...",
        tools: ["Read", "Grep", "Glob"],
        model: "sonnet"
      }
    }
  }
})) {
  console.log(message);
}
```

---

## Custom System Prompt

```python
options = ClaudeAgentOptions(
    system_prompt="You are a Python coding specialist..."
)

# OR extend the default Claude Code prompt:
options = ClaudeAgentOptions(
    system_prompt={
        "type": "preset",
        "preset": "claude_code",
        "append": "Extra instructions here"
    }
)
```

---

## Full ClaudeAgentOptions (Python)

```python
options = ClaudeAgentOptions(
    # Tools and permissions
    allowed_tools=["Read", "Edit", "Bash", "Glob"],
    disallowed_tools=["WebSearch"],
    permission_mode="acceptEdits",
    can_use_tool=async_permission_handler,

    # Model and system prompt
    model="claude-opus-4-6",
    system_prompt="...",

    # MCP and custom tools
    mcp_servers={"github": {...}},
    agents={"code-reviewer": AgentDefinition(...)},

    # Session management
    resume="session-id",
    fork_session=False,
    continue_conversation=False,

    # Control
    max_turns=10,
    max_budget_usd=5.0,
    max_thinking_tokens=10000,

    # Environment
    cwd="/path/to/project",
    env={"DEBUG": "1"},
    add_dirs=["/path/to/extra"],

    # Settings
    setting_sources=["project"],  # Load CLAUDE.md

    # Hooks
    hooks={
        "PreToolUse": [
            HookMatcher(
                matcher="Bash",
                hooks=[pre_bash_handler],
                timeout=120
            )
        ]
    }
)
```

---

## Message Types

```python
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    ToolUseBlock,
    TextBlock,
)

async for message in query(prompt="...", options=options):
    if isinstance(message, SystemMessage) and message.subtype == "init":
        print(f"Session ID: {message.data.get('session_id')}")
    elif isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                print(f"Text: {block.text}")
            elif isinstance(block, ToolUseBlock):
                print(f"Tool: {block.name} with {block.input}")
    elif isinstance(message, ResultMessage):
        print(f"Cost: ${message.total_cost_usd}, Duration: {message.duration_ms}ms")
```

---

## Available Models

- `claude-opus-4-6` (most capable)
- `claude-sonnet-4-5`
- `claude-haiku-4-5` (fastest)

---

## Official Documentation

- Overview: https://platform.claude.com/docs/en/agent-sdk/overview
- Quickstart: https://platform.claude.com/docs/en/agent-sdk/quickstart
- Python Reference: https://platform.claude.com/docs/en/agent-sdk/python
- TypeScript Reference: https://platform.claude.com/docs/en/agent-sdk/typescript
- Sessions: https://platform.claude.com/docs/en/agent-sdk/sessions
- MCP Integration: https://platform.claude.com/docs/en/agent-sdk/mcp
- Permissions: https://platform.claude.com/docs/en/agent-sdk/permissions
- Subagents: https://platform.claude.com/docs/en/agent-sdk/subagents
- Custom Tools: https://platform.claude.com/docs/en/agent-sdk/custom-tools
- Streaming: https://platform.claude.com/docs/en/agent-sdk/streaming-vs-single-mode
- GitHub (Python): https://github.com/anthropics/claude-agent-sdk-python
- GitHub (TypeScript): https://github.com/anthropics/claude-agent-sdk-typescript
- npm: https://www.npmjs.com/package/@anthropic-ai/claude-agent-sdk
