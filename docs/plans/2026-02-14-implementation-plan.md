# MAKER Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the MAKER system as a modular Python pipeline that takes a user task, decomposes it into atomic steps via a Planner Agent, validates the plan, and executes each step via isolated microagents with configurable voting and red-flagging.

**Architecture:** Event-driven pipeline with pluggable modules communicating via a typed event bus. Each concern (planning, validation, execution, voting, red-flagging, YAML cleaning, tool registry) is an independent module implementing a common `AsyncIterator`-based interface. Built on `claude-agent-sdk`.

**Tech Stack:** Python 3.11+, `claude-agent-sdk`, `pyyaml`, `pytest`, `pytest-asyncio`

---

## Milestone Overview

| # | Milestone | Ships | Depends On |
|---|-----------|-------|------------|
| 1 | [Project Foundation](milestones/milestone-01-foundation.md) | Installable package, all data models, typed events, event bus, module ABC | — |
| 2 | [YAML Cleaner](milestones/milestone-02-yaml-cleaner.md) | 3-stage YAML parsing with deterministic fixes + LLM repair fallback | M1 |
| 3 | [Tool Registry + Prompts](milestones/milestone-03-tools-and-prompts.md) | Tool management (builtin + MCP), centralized prompt loading | M1 |
| 4 | [Planner Module](milestones/milestone-04-planner.md) | Plan generation from task + tools via SDK | M1, M2, M3 |
| 5 | [Validator Module](milestones/milestone-05-validator.md) | Deterministic plan checks + optional LLM quality checks | M1, M3 |
| 6 | [Agent Runner + Red Flagger + Context Builder](milestones/milestone-06-agent-runner.md) | Single-step execution core: SDK call, output extraction, validation, context injection | M1, M2 |
| 7 | [Voting System](milestones/milestone-07-voting.md) | Output canonicalization + 3 voting strategies (none, majority, first-to-K) | M1, M6 |
| 8 | [Executor + Result Collector](milestones/milestone-08-executor.md) | Full step orchestration: sequential execution, conditional routing, result aggregation | M1, M6, M7 |
| 9 | [Orchestrator + CLI](milestones/milestone-09-orchestrator-cli.md) | End-to-end pipeline, CLI entry point, public API (`run_task`) | All |

## Dependency Graph

```
M1 (Foundation)
├── M2 (YAML Cleaner)
├── M3 (Tool Registry + Prompts)
│   ├── M4 (Planner) ← also M2
│   └── M5 (Validator)
├── M6 (Agent Runner) ← also M2
│   └── M7 (Voting)
│       └── M8 (Executor)
└── M9 (Orchestrator + CLI) ← all milestones
```

## Conventions

- **Package:** `src/maker/` with `pyproject.toml` using `[project.scripts]` for CLI
- **Tests:** `tests/` mirroring `src/maker/` structure, using `pytest` + `pytest-asyncio`
- **TDD:** Write failing tests first, then implement
- **Commits:** One commit per meaningful unit (test + implementation together is fine)
- **Mocking:** All SDK calls mocked in tests via `unittest.mock.AsyncMock`. No real API calls in tests.
- **Python:** 3.11+, type hints everywhere, dataclasses for models
