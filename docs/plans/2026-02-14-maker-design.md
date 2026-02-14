# MAKER System Design

## 1. What We're Building

A generic implementation of the MAKER paper ("Solving a Million-Step LLM Task with Zero Errors") as a Python system that:

- Takes a user task + available tools as input
- Uses a **Planner Agent** to produce a maximally decomposed YAML plan (k=1, each step = 1 tool call)
- Validates the plan via **static checks** (deterministic + optional LLM quality checks)
- Uses an **Executor** to run each step via isolated microagents with configurable **voting** and **red-flagging**
- Emits structured **events** throughout, consumable by CLI now and WebSocket/UI later

Built on top of `claude-agent-sdk` (Python).

---

## 2. Decisions

| Decision | Choice |
|----------|--------|
| Language | Python (`claude-agent-sdk`) |
| Tools | Built-in Claude Code tools + user-registered MCP tools (explicit registration, no auto-discovery) |
| Voting | Configurable per task (none / majority / first-to-ahead-by-K) |
| Interface | CLI + programmatic library (v1), WebSocket for UI (v2) |
| Re-planning | Plan once, then execute |
| Static checks | Deterministic always on, LLM quality checks optional (off by default) |
| Red-flagging | Yes, as a pluggable module. Loose validation — output must be valid YAML + dict, no rigid schema enforcement |
| Architecture | Composable — every concern in its own module, plug-and-play |
| Model | Single model configurable at task level, same model for all executor steps |
| Context passing | Pass whole step outputs to agents, no path resolution. LLM extracts what it needs |
| Tier-3 tools | `AskUserQuestion` is the implicit fallback tool (replaces SPEC's `human_input_tool`). `ask_duckie` dropped (domain-specific) |

---

## 3. Approaches Considered

### Approach A: Monolithic Pipeline

One class that does planning, validation, execution, and voting in sequence. Simple to build but tightly coupled. Swapping voting strategies or adding WebSocket later requires touching core logic. **Rejected — contradicts composability requirement.**

### Approach B: Event-Driven Pipeline with Pluggable Modules (Selected)

Lightweight orchestrator manages a pipeline of independent modules communicating via a shared event bus. Each module is a Python class with a simple interface. Events flow through an async queue that any consumer (CLI, WebSocket, logger) can read from. **Selected — right level of complexity, naturally maps to both CLI and future WebSocket.**

### Approach C: Actor-Based (Ray / Dramatiq)

Each module as an independent actor/process. True parallelism and distribution but massive complexity — message brokers, serialization, coordination. **Rejected — overkill for 100-user scale.**

---

## 4. Architecture

### 4.1 High-Level Flow

```
User Task + Config
       |
       v
+------------------+
|   Orchestrator    |  (manages pipeline, routes events)
+------------------+
       |
       v
+------------------+
|  Planner Module   |  → emits: PlanCreated
+------------------+
       |
       v
+------------------+
| Validator Module  |  → emits: ValidationPassed / ValidationFailed
+------------------+     (deterministic checks always, LLM quality checks optional)
       |
       v
+------------------+
| Executor Module   |  (iterates steps sequentially)
|                  |
|  Per step:       |
|  +--------------+|
|  | Agent Runner ||  → runs isolated claude-agent-sdk query()
|  +--------------+|
|        |         |
|  +--------------+|
|  | Red-Flagger  ||  → checks output is valid YAML + dict, discards malformed
|  +--------------+|
|        |         |
|  +--------------+|
|  |    Voter     ||  → applies voting strategy (none / majority / first-to-K)
|  +--------------+|
|        |         |
|  emits: StepStarted, StepCompleted, StepFailed
+------------------+
       |
       v
+------------------+
| Result Collector  |  → emits: TaskCompleted / TaskFailed
+------------------+
       |
       v
  Event Bus (async queue)
       |
  +----+----+
  |         |
  v         v
 CLI    WebSocket (v2)
```

### 4.2 Module Interface

Every module implements the same contract:

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator

class Module(ABC):
    @abstractmethod
    async def process(self, event: Event) -> AsyncIterator[Event]:
        """Receive an event, yield zero or more events as they occur."""
        ...
```

Uses `AsyncIterator` instead of returning a list so long-running modules (executor, voters) can emit intermediate events as they stream.

This makes every module:
- **Independently testable** — feed events in, assert on events out
- **Swappable** — replace `MajorityVoter` with `FirstToKVoter`, nothing else changes
- **Composable** — chain modules in any order the orchestrator defines

### 4.3 Event System

Events are typed dataclasses with typed payloads (not `dict`) that flow through the system:

```
TaskSubmitted          — user submits a task
PlanCreated            — planner produces YAML plan
ValidationPassed       — all static checks pass
ValidationFailed       — one or more checks fail (with details)
StepStarted            — executor begins a step
AgentSampleCompleted   — one agent run finishes (for voting)
AgentSampleRedFlagged  — one agent run discarded (malformed output)
VoteCompleted          — voting resolves for a step
StepCompleted          — step finished with accepted output
StepFailed             — step failed after all retries/votes
TaskCompleted          — all steps done, final result
TaskFailed             — task failed (unrecoverable step failure)
```

Each event type is its own dataclass with a typed payload:

```python
@dataclass
class StepCompleted:
    type: str = "step_completed"
    timestamp: float
    step: int
    title: str
    output: dict
    voting_summary: VotingSummary
    cost_usd: float
    duration_ms: int
```

All events are serializable (dataclass → dict → JSON) so they can be:
- Printed by CLI
- Sent over WebSocket
- Logged / persisted

### 4.4 Event Bus

A simple async queue that the orchestrator writes to and consumers read from:

```python
class EventBus:
    async def emit(self, event: Event) -> None: ...
    async def subscribe(self) -> AsyncIterator[Event]: ...
```

Multiple consumers can subscribe. The CLI consumer prints formatted output. The future WebSocket consumer serializes and sends to clients.

---

## 5. Components Detail

### 5.1 Prompts (Centralized)

All LLM prompts live in `src/maker/prompts/` as Python string constants. No prompt is ever inlined in module code. Every module that calls an LLM loads its prompt from this central location.

```
prompts/
├── __init__.py              # load_prompt() helper
├── planner_system.py        # full planner system prompt (from SPEC.md)
├── planner_user.py          # user message template (instruction + tools list)
├── yaml_fixer.py            # prompt for LLM-based YAML repair
├── quality_single_purpose.py
├── quality_self_contained.py
├── quality_max_k_tools.py
├── quality_non_overlapping.py
├── quality_maximally_decomposed.py
├── quality_appropriately_merged.py
└── executor_step.py         # template for constructing step agent prompts
```

**Why centralized:**
- Single place to audit, version, and iterate on all prompts
- Prompt changes don't require touching module logic
- Easy to A/B test prompt variants
- Enables future prompt versioning / drift tracking

**Loading convention:**
```python
# src/maker/prompts/__init__.py
def load_prompt(name: str, **kwargs) -> str:
    """Load a prompt by name, optionally formatting with kwargs."""
    ...
```

All modules call `load_prompt("planner_system", tools=tools_list)` instead of embedding prompt strings.

**Planner prompt adaptation:**
The planner prompt from SPEC.md is used as-is with the following changes:
- `human_input_tool` → `AskUserQuestion` (SDK's actual tool name)
- `ask_duckie` → removed entirely (domain-specific, not relevant to our generic system)
- Tier-3 references updated to say `AskUserQuestion` is the implicit last-resort tool

### 5.2 Tool Registry

A central registry that manages all available tools (built-in + MCP). Users **explicitly register** MCP tools with name and description — no auto-discovery (SDK doesn't support it).

```python
class ToolRegistry:
    def register_builtin(self, tool_name: str, description: str) -> None:
        """Register a built-in Claude Code tool."""
        ...

    def register_mcp_server(
        self,
        server_name: str,
        server_config: MCPServerConfig,
        tools: list[ToolInfo]
    ) -> None:
        """Register an MCP server with its tools. User provides tool list explicitly."""
        ...

    def unregister_mcp_server(self, server_name: str) -> None:
        """Remove an MCP server and all its tools."""
        ...

    def list_tools(self) -> list[ToolInfo]:
        """Return all registered tools with names and descriptions."""
        ...

    def get_tool_names(self) -> list[str]:
        """Return flat list of tool names for planner consumption."""
        ...

    def validate_tool_name(self, name: str) -> bool:
        """Check if a tool name exists in the registry."""
        ...

    def get_mcp_server_configs(self) -> dict:
        """Return MCP server configs for passing to claude-agent-sdk query()."""
        ...
```

**ToolInfo structure:**
```python
@dataclass
class ToolInfo:
    name: str               # e.g. "Read" or "mcp__github__list_issues"
    description: str        # what the tool does
    source: str             # "builtin" | "mcp"
    server_name: str | None # MCP server name, None for built-in
```

**MCPServerConfig structure:**
```python
@dataclass
class MCPServerConfig:
    command: str             # e.g. "npx"
    args: list[str]          # e.g. ["-y", "@modelcontextprotocol/server-github"]
    env: dict[str, str] = field(default_factory=dict)  # e.g. {"GITHUB_TOKEN": "..."}
```

**How it's used:**
1. At startup, the registry auto-registers built-in Claude Code tools (Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, AskUserQuestion)
2. User registers MCP servers via `TaskConfig.mcp_servers` or programmatic API, providing tool names explicitly
3. The planner receives `registry.list_tools()` so it knows what's available when generating the plan
4. The validator uses `registry.validate_tool_name()` for the `tools_are_valid` check
5. The executor uses `registry.get_mcp_server_configs()` when constructing `claude-agent-sdk` query options

**Example MCP registration:**
```python
registry.register_mcp_server(
    server_name="github",
    server_config=MCPServerConfig(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_TOKEN": os.environ["GITHUB_TOKEN"]}
    ),
    tools=[
        ToolInfo(name="mcp__github__list_issues", description="List GitHub issues", source="mcp", server_name="github"),
        ToolInfo(name="mcp__github__create_issue", description="Create a GitHub issue", source="mcp", server_name="github"),
    ]
)
```

### 5.3 YAML Output Cleaner

All LLM output in the system is YAML. The output cleaner is a robust parser with LLM-fallback repair.

```python
class YAMLCleaner:
    async def parse(self, raw_output: str) -> tuple[dict | list, bool]:
        """
        Parse YAML output. Returns (parsed_data, was_repaired).

        Pipeline:
        1. Strip markdown fences (```yaml ... ```)
        2. Attempt yaml.safe_load()
        3. If fails → attempt common fixes (see below)
        4. If still fails → LLM repair call
        5. If still fails → raise YAMLParseError with details
        """
        ...

    def _strip_fences(self, raw: str) -> str:
        """Remove ```yaml and ``` markdown wrappers. Handles extra prose,
        multiple fenced blocks, and partial wrappers."""
        ...

    def _attempt_common_fixes(self, raw: str, error: str) -> str | None:
        """Try deterministic fixes before calling LLM."""
        ...

    async def _llm_repair(self, raw: str, error: str) -> str:
        """Call a cheap/fast LLM to fix the YAML."""
        ...
```

**Deterministic fix attempts (before LLM):**
- Strip markdown code fences (handles extra prose, multiple blocks, partial wrappers)
- Fix unquoted special characters (`:`, `#`, `{`, `}` in values)
- Fix incorrect indentation (tabs → spaces)
- Fix missing `|` or `>` for multiline strings
- Fix trailing commas
- Fix unescaped quotes inside quoted strings

**LLM repair (if deterministic fixes fail):**
- Uses cheapest available model (haiku)
- Prompt loaded from `prompts/yaml_fixer.py`
- Single retry — if LLM repair also fails, raise `YAMLParseError`

**Where it's used:**
- Planner output → `YAMLCleaner.parse()` before validation
- Executor agent output → `YAMLCleaner.parse()` before red-flag check
- Quality check LLM responses → `YAMLCleaner.parse()`

### 5.4 Planner Module

- **Input:** `TaskSubmitted` event containing user instruction + available tools list
- **Mechanism:** Single `claude-agent-sdk` `query()` call with the planner prompt loaded from `prompts/planner_system.py`
- **System prompt:** Loaded via `load_prompt("planner_system")` (adapted from SPEC.md with tool name fixes)
- **Output parsing:** Raw LLM output → `YAMLCleaner.parse()` → map `plan` key to `steps` → `Plan` dataclass
- **Output:** `PlanCreated` event containing the parsed plan
- **Model:** Uses the task-level configured model

The planner receives the tool catalog from `ToolRegistry.list_tools()` so it can assign appropriate tools to each step.

### 5.5 Validator Module

Two layers, run in sequence:

**Layer 1: Deterministic Checks (always on)**

| Category | Checks |
|----------|--------|
| Schema & Structure | valid_yaml, required_fields_present, step_numbering, task_type_valid, reasoning_present |
| Tool Set Integrity | tools_mutually_exclusive, tools_are_valid (against registry), conditional_step_no_tools, conditional_step_no_instructions |
| Sequencing & Flow | next_step_valid, conditional_returns_minus_2, final_step_returns_minus_1, no_orphan_steps |
| Output Schema | output_schema_exists (non-empty string for every step) |

Each check returns Pass/Fail. Any Fail → `ValidationFailed` event.

**Layer 2: LLM Quality Checks (optional, off by default)**

| Check | What it scores |
|-------|----------------|
| single_purpose | Each step has ONE clear purpose |
| self_contained | Task description complete enough for isolated agent |
| max_k_tool_calls | Step completable with ≤k tool calls |
| non_overlapping | No two steps fetch redundant information |
| maximally_decomposed | Step cannot be meaningfully split further |
| appropriately_merged | Steps that should be merged ARE merged |

Each check returns 0.0–1.0 score via a cheap LLM call (haiku). Scores are aggregated into a weighted quality score.

If validation fails, the plan is rejected. The orchestrator re-runs the planner up to `max_planner_retries` times, passing validation errors as feedback.

### 5.6 Executor Module

Iterates through plan steps sequentially, following `next_step_sequence_number` for flow control.

For each step:

1. **Build context** — collect full output dicts for all steps referenced in `input_variables` (extract step name only, e.g., `step_0_output` from `step_0_output.user_id`)
2. **Construct agent prompt** — step's `task_description` + full outputs of referenced steps injected as YAML blocks
3. **Run agent(s)** — depending on voting config:
   - `none`: run 1 agent (up to `step_max_retries` on failure)
   - `majority`: run N agents (default N=3)
   - `first_to_k`: keep running agents until one answer leads by K (capped at `max_voting_samples`)
4. **Red-flag check** — each agent output must be valid YAML and a dict; malformed outputs discarded
5. **Vote** — apply voting strategy to non-red-flagged outputs using canonicalized comparison
6. **Store output** — winning output stored as `step_N_output` for downstream steps
7. **Route** — follow `next_step_sequence_number`, or for conditional steps parse `next_step` from output

**Conditional step routing:**
- Conditional steps must output `{next_step: int, reason: string}`
- Executor parses this via `YAMLCleaner`, reads `next_step` field, routes accordingly
- If `next_step` is missing or invalid → `StepFailed`

Each agent run is an isolated `claude-agent-sdk` `query()` call with:
- The step's `task_description` as prompt + context from previous steps
- The step's `primary_tools` / `fallback_tools` as `allowed_tools`
- `permission_mode="bypassPermissions"` (agents are autonomous)
- Configured MCP servers if step uses custom tools

### 5.7 Agent Runner

Wraps a single `claude-agent-sdk` `query()` call:

```python
class AgentRunner:
    async def run(self, step: PlanStep, context: dict, config: AgentConfig) -> AgentResult:
        """Run one isolated agent for one step. Returns structured output."""
        ...
```

**SDK message stream extraction rule:**
1. Iterate over all messages from `query()`
2. Collect `AssistantMessage` objects
3. From the final `AssistantMessage`, take the last `TextBlock` content
4. Pass through `YAMLCleaner.parse()` to get structured output
5. If any `ResultMessage` has `subtype == "error"`, treat as agent failure

Returns `AgentResult` with:
- `output: dict` — parsed YAML output
- `raw_response: str` — raw text from the agent
- `was_repaired: bool` — whether YAMLCleaner had to fix the output
- `tokens: int` — total tokens used
- `cost_usd: float` — cost of this run
- `duration_ms: int` — wall clock time

### 5.8 Red-Flag Module

Checks each `AgentResult` before it enters the voting pool:

```python
class RedFlagger:
    def check(self, result: AgentResult) -> bool:
        """Returns True if the result should be discarded."""
        ...
```

Discard conditions (loose validation):
- Output could not be parsed as YAML at all (even after YAMLCleaner)
- Output is not a dict/object (e.g., raw string, list, number)
- Agent produced an error/exception

**Not** checked (intentionally loose):
- Specific field presence against `output_schema` — schema is a hint, not a contract
- Extra/unexpected fields — allowed
- Field types — not enforced

`output_schema` is passed to the agent in its prompt to guide output shape, but the red-flagger only gates on "is it valid YAML and a dict." This keeps the system flexible across different use cases.

Red-flagged samples are logged (for debugging) but excluded from voting.

### 5.9 Voter Module

Three implementations behind a common interface:

```python
class Voter(ABC):
    @abstractmethod
    async def vote(self, step: PlanStep, runner: AgentRunner, context: dict) -> VoteResult:
        """Run agents and return the winning output."""
        ...
```

**Vote canonicalization (used by all voters):**
Before comparing outputs, canonicalize each one:
1. Parse YAML to dict (already done by AgentRunner)
2. Recursively sort all dict keys
3. Normalize whitespace and formatting
4. Serialize to a canonical JSON string
5. Compare canonical strings for equality

This prevents semantically identical outputs with different key ordering or formatting from splitting votes.

**NoVoter** — runs 1 agent, returns its output directly.

**MajorityVoter** — runs N agents in parallel, takes the output that appears most frequently (by canonical comparison). If no majority, runs additional agents until majority emerges or `max_voting_samples` reached.

**FirstToKVoter** — paper's approach. Keeps running agents. Tracks vote counts per unique canonical output. Winner is declared when `leader_count - runner_up_count >= K`. Configurable K (default K=2). Hard cap at `max_voting_samples` to prevent infinite loops.

All voters use the Red-Flag module to filter bad samples before counting votes.

### 5.10 Result Collector

Aggregates all step outputs into a final result:

```python
{
    "task": "original user instruction",
    "status": "completed" | "failed",
    "steps": [
        {
            "step": 0,
            "title": "...",
            "output": { ... },
            "voting": { "strategy": "majority", "samples": 3, "red_flagged": 0 },
            "cost_usd": 0.002,
            "duration_ms": 1200
        },
        ...
    ],
    "total_cost_usd": 0.05,
    "total_duration_ms": 15000
}
```

---

## 6. Data Models

### 6.1 Task Configuration

```python
@dataclass
class TaskConfig:
    instruction: str                          # user's task
    model: str = "claude-sonnet-4-5"          # model for all agents
    voting_strategy: str = "none"             # "none" | "majority" | "first_to_k"
    voting_n: int = 3                         # number of samples for majority
    voting_k: int = 2                         # K for first-to-ahead-by-K
    max_voting_samples: int = 10              # hard cap on total samples per step (prevents infinite loops)
    step_max_retries: int = 2                 # retries per step before escalating to voting/failure
    enable_quality_checks: bool = False       # LLM quality checks on plan
    max_planner_retries: int = 2              # retries if validation fails
    mcp_servers: dict = field(default_factory=dict)  # custom MCP tool servers
    allowed_builtin_tools: list[str] = None   # subset of built-in tools (None = all)
```

### 6.2 Plan Step (parsed from YAML)

```python
@dataclass
class PlanStep:
    step: int
    task_type: str                    # "action_step" | "conditional_step"
    title: str
    task_description: str
    primary_tools: list[str]
    fallback_tools: list[str]
    primary_tool_instructions: str
    fallback_tool_instructions: str
    input_variables: list[str]
    output_variable: str
    output_schema: str                # free-form hint string, not enforced as contract
    next_step_sequence_number: int
```

### 6.3 Plan (parsed from YAML)

```python
@dataclass
class Plan:
    reasoning: str
    steps: list[PlanStep]    # mapped from YAML key "plan" → "steps"
```

**Parser note:** The planner's YAML output uses `plan` as the top-level key for the step list. The parser maps `plan` → `steps` when constructing the `Plan` dataclass.

### 6.4 Events

Each event type is its own typed dataclass:

```python
@dataclass
class TaskSubmitted:
    type: str = "task_submitted"
    timestamp: float
    instruction: str
    config: TaskConfig

@dataclass
class StepStarted:
    type: str = "step_started"
    timestamp: float
    step: int
    title: str

@dataclass
class StepCompleted:
    type: str = "step_completed"
    timestamp: float
    step: int
    title: str
    output: dict
    voting_summary: VotingSummary
    cost_usd: float
    duration_ms: int

# ... etc for each event type
```

### 6.5 Agent Result

```python
@dataclass
class AgentResult:
    output: dict              # parsed YAML output
    raw_response: str         # raw text from the agent
    was_repaired: bool        # whether YAMLCleaner had to fix the output
    tokens: int               # total tokens used
    cost_usd: float           # cost of this run
    duration_ms: int          # wall clock time
    error: str | None = None  # error message if agent failed
```

### 6.6 Vote Result

```python
@dataclass
class VoteResult:
    winner: dict                  # the winning output
    canonical_hash: str           # canonical string used for comparison
    total_samples: int            # total agents run
    red_flagged: int              # samples discarded by red-flagger
    vote_counts: dict[str, int]   # canonical_hash → count for each unique output
```

---

## 7. Project Structure

```
maker/
├── pyproject.toml
├── SPEC.md
├── CLAUDE_AGENT_SDK_REFERENCE.md
├── docs/
│   └── plans/
│       ├── 2026-02-14-maker-design.md
│       ├── 2026-02-14-codex-design-review.md
│       └── 2026-02-14-mvp-fixes.md
├── src/
│   └── maker/
│       ├── __init__.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── orchestrator.py      # pipeline orchestrator
│       │   ├── events.py            # typed event dataclasses + event bus
│       │   └── models.py            # data models (TaskConfig, Plan, PlanStep, AgentResult, etc.)
│       ├── prompts/
│       │   ├── __init__.py              # load_prompt() helper
│       │   ├── planner_system.py        # full planner system prompt (adapted from SPEC.md)
│       │   ├── planner_user.py          # user message template (instruction + tools list)
│       │   ├── yaml_fixer.py            # prompt for LLM-based YAML repair
│       │   ├── quality_single_purpose.py
│       │   ├── quality_self_contained.py
│       │   ├── quality_max_k_tools.py
│       │   ├── quality_non_overlapping.py
│       │   ├── quality_maximally_decomposed.py
│       │   ├── quality_appropriately_merged.py
│       │   └── executor_step.py         # template for constructing step agent prompts
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── registry.py             # ToolRegistry class (explicit registration)
│       │   ├── builtin.py              # built-in Claude Code tool definitions
│       │   └── models.py               # ToolInfo, MCPServerConfig dataclasses
│       ├── yaml_cleaner/
│       │   ├── __init__.py
│       │   ├── cleaner.py              # YAMLCleaner class (parse + repair pipeline)
│       │   └── fixes.py                # deterministic fix functions
│       ├── planner/
│       │   ├── __init__.py
│       │   └── planner.py              # planner module (calls claude-agent-sdk)
│       ├── validator/
│       │   ├── __init__.py
│       │   ├── validator.py            # validator module (orchestrates checks)
│       │   ├── deterministic.py        # schema, tools, sequencing checks
│       │   └── quality.py              # LLM-based quality checks
│       ├── executor/
│       │   ├── __init__.py
│       │   ├── executor.py             # executor module (iterates steps)
│       │   ├── agent_runner.py          # single agent run wrapper (SDK stream extraction)
│       │   ├── context_builder.py       # builds context by injecting full step outputs
│       │   └── result_collector.py      # aggregates step outputs
│       ├── voting/
│       │   ├── __init__.py
│       │   ├── base.py                 # Voter ABC
│       │   ├── canonicalizer.py        # output canonicalization (sort keys, normalize)
│       │   ├── no_voter.py             # single agent, no voting
│       │   ├── majority_voter.py       # majority voting
│       │   └── first_to_k_voter.py     # first-to-ahead-by-K voting
│       ├── red_flag/
│       │   ├── __init__.py
│       │   └── red_flagger.py          # loose validation: valid YAML + dict check
│       └── cli/
│           ├── __init__.py
│           └── main.py                 # CLI entry point
└── tests/
    ├── test_prompts/
    ├── test_tools/
    ├── test_yaml_cleaner/
    ├── test_planner/
    ├── test_validator/
    ├── test_executor/
    ├── test_voting/
    └── test_red_flag/
```

---

## 8. Interface

### 8.1 Programmatic API

```python
from maker import run_task, TaskConfig

config = TaskConfig(
    instruction="Find all Python files with TODO comments and create a summary",
    model="claude-sonnet-4-5",
    voting_strategy="majority",
    voting_n=3,
    max_voting_samples=10,
    enable_quality_checks=False,
)

# Streaming — yields events as they happen
async for event in run_task(config):
    print(event)

# Or get final result
result = await run_task_sync(config)
print(result.status)
```

### 8.2 CLI

```bash
# Basic usage
maker "Find all Python files with TODO comments and create a summary"

# With options
maker "Deploy the staging environment" \
  --model claude-sonnet-4-5 \
  --voting majority \
  --voting-n 5 \
  --max-voting-samples 15 \
  --quality-checks
```

### 8.3 Future: WebSocket (v2)

```python
# WebSocket server wraps the same run_task() API
async def handle_ws(websocket):
    task = await websocket.recv()
    config = TaskConfig(**json.loads(task))
    async for event in run_task(config):
        await websocket.send(event.to_json())
```

---

## 9. Error Handling

| Scenario | Behavior |
|----------|----------|
| Planner produces invalid YAML | `YAMLCleaner` attempts deterministic fixes → LLM repair → if still fails, retry planner up to `max_planner_retries` times |
| Plan fails deterministic validation | Retry planner with validation errors as feedback |
| Executor agent produces invalid YAML | `YAMLCleaner` attempts deterministic fixes → LLM repair → if still fails, red-flag the sample |
| Agent output is not a dict | Red-flag the sample (loose validation) |
| Agent run errors | Red-flag the sample, continue voting with remaining samples |
| All samples for a step are red-flagged | `StepFailed` event, `TaskFailed` |
| Voting can't resolve (no majority, no K-lead) | Run additional samples up to `max_voting_samples`, then fail the step |
| Conditional step missing `next_step` field | `StepFailed` event, `TaskFailed` |
| Conditional step returns invalid `next_step` | `StepFailed` event, `TaskFailed` |
| MCP server fails to connect | `ToolRegistry` marks server as unavailable, planner warned in tool catalog |

---

## 10. What's NOT in v1

- Re-planning on failure (plan once, execute)
- Per-step model assignment (single model for all)
- WebSocket / UI integration (CLI only)
- Parallel step execution (sequential only)
- Plan persistence / resumption across restarts
- Cost budgets / spending limits
- Authentication / multi-tenancy
- Event persistence / replay
- Cancellation / pause / resume APIs
- MCP server health-checks / auto-reconnect
- Correlated error mitigation (temperature/prompt variation across voting samples)
