from dataclasses import dataclass, field


@dataclass
class MCPServerConfig:
    command: str
    args: list[str]
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class ToolInfo:
    name: str
    description: str
    source: str  # "builtin" | "mcp"
    server_name: str | None = None


@dataclass
class TaskConfig:
    instruction: str
    model: str = "claude-sonnet-4-5"
    voting_strategy: str = "none"  # "none" | "majority" | "first_to_k"
    voting_n: int = 3
    voting_k: int = 2
    max_voting_samples: int = 10
    step_max_retries: int = 2
    enable_quality_checks: bool = False
    max_planner_retries: int = 2
    mcp_servers: dict = field(default_factory=dict)
    allowed_builtin_tools: list[str] | None = None


@dataclass
class PlanStep:
    step: int
    task_type: str  # "action_step" | "conditional_step"
    title: str
    task_description: str
    primary_tools: list[str]
    fallback_tools: list[str]
    primary_tool_instructions: str
    fallback_tool_instructions: str
    input_variables: list[str]
    output_variable: str
    output_schema: str
    next_step_sequence_number: int


@dataclass
class Plan:
    reasoning: str
    steps: list[PlanStep]


@dataclass
class AgentResult:
    output: dict
    raw_response: str
    was_repaired: bool
    tokens: int
    cost_usd: float
    duration_ms: int
    error: str | None = None


@dataclass
class VotingSummary:
    strategy: str
    total_samples: int
    red_flagged: int
    winning_votes: int


@dataclass
class VoteResult:
    winner: dict
    canonical_hash: str
    total_samples: int
    red_flagged: int
    vote_counts: dict[str, int]
