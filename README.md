# MAKER

**Maximal Agentic Decomposition with Error Correction and Red-flagging**

A framework that breaks complex instructions into validated, executable plans using Claude agents. Inspired by the MAKER paper — each task is decomposed into atomic steps, validated, and executed with optional multi-agent voting for robustness.

## How It Works

```
Instruction → Planner → Validator → Executor → Result
                ↑           |
                └───────────┘  (retry with feedback on failure)
```

1. **Planner** generates a multi-step plan from your instruction and available tools
2. **Validator** runs deterministic checks (step ordering, tool validity, reachability) and optional LLM quality checks
3. **Executor** runs each step as an isolated agent, chaining outputs between steps
4. **Voting** (optional) runs multiple agents per step and picks the consensus answer

## Install

```bash
pip install -e ".[dev]"
```

Requires `claude-agent-sdk` and Python 3.11+.

## Usage

### CLI

```bash
maker "Write a Python function to validate email addresses"

# With majority voting (3 samples per step)
maker "Analyze this CSV file" --voting majority --voting-n 5

# With first-to-K voting
maker "Refactor auth module" --voting first_to_k --voting-k 2

# With LLM quality checks on the plan
maker "Build a REST API" --quality-checks
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--model` | `claude-sonnet-4-5` | Claude model to use |
| `--voting` | `none` | Voting strategy: `none`, `majority`, `first_to_k` |
| `--voting-n` | `3` | Samples for majority voting |
| `--voting-k` | `2` | Lead required for first-to-K |
| `--max-voting-samples` | `10` | Max samples before giving up |
| `--quality-checks` | off | Enable LLM plan quality checks |

### Python API

```python
from maker import run_task
from maker.core.models import TaskConfig

config = TaskConfig(
    instruction="Your task here",
    voting_strategy="majority",
    voting_n=3,
)

async for event in run_task(config):
    print(event)
```

## Architecture

```
src/maker/
├── core/           # Models, events, orchestrator
├── planner/        # Plan generation via Claude
├── validator/      # Deterministic + LLM quality checks
├── executor/       # Step-by-step execution, context chaining
├── voting/         # NoVoter, MajorityVoter, FirstToKVoter
├── red_flag/       # Output filtering (non-dict, errors)
├── yaml_cleaner/   # 3-stage YAML repair pipeline
├── tools/          # Tool registry (builtin + MCP)
├── prompts/        # System prompts for all modules
└── cli/            # Command-line interface
```

### Voting Strategies

- **NoVoter** — Single agent, retry on failure/red-flag
- **MajorityVoter** — Run N agents, take majority (canonicalized comparison). Runs more if no majority emerges.
- **FirstToKVoter** — Keep running agents until one answer leads by K votes over the runner-up

All voters use canonical hashing so equivalent outputs with different key ordering count as the same vote.

## Tests

```bash
uv run pytest -v          # 252 tests
uv run pytest tests/test_voting/ -v  # just voting tests
```
