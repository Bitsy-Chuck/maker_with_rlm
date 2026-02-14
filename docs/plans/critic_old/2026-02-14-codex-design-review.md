# MAKER Design Review — Codex Analysis

> Reviewed by: OpenAI Codex (gpt-5.3-codex) via `codex exec`
> Date: 2026-02-14
> Files reviewed: `docs/plans/2026-02-14-maker-design.md`, `SPEC.md`, `CLAUDE_AGENT_SDK_REFERENCE.md`

---

## 1. Completeness

**Verdict: Strong baseline, 5 gaps to close.**

The design covers the main MAKER loop (planner → validator → executor → voting → result) and is clearly decomposed (`§4.1`, `§5.4`–`§5.10`).

### Missing Pieces (relative to SPEC.md)

| # | Gap | Design Sections | Severity |
|---|-----|-----------------|----------|
| 1 | **Plan schema mismatch** — SPEC requires `reasoning` + `plan` list at top level, but design model uses `Plan.steps` (`§6.3`). No explicit mapping rule (`plan` → `steps`), making parser/validator contract ambiguous. | `§6.3` | Medium |
| 2 | **Tier-3 tool semantics missing** — `human_input_tool`/`ask_duckie` implicit availability and "check previous outputs first" behavior are not represented in executor logic or validation checks. | `§5.5`, `§5.6`, `§5.7` | High |
| 3 | **User-instruction fidelity not validated** — Preserving user-provided URLs/IDs/endpoints, no hallucinated references, and explicit propagation are absent from deterministic checks. | `§5.5` | High |
| 4 | **Output-chaining validation incomplete** — No check that every field referenced in `task_description` is present in `input_variables`. No check that schemas avoid ellipsis/implicit fields. | `§5.5`, `§6.2` | Medium |
| 5 | **Operational controls underspecified** — Step timeouts, per-step retry limits, and max voting attempts are referenced behaviorally (`§9`) but missing from `TaskConfig` (`§6.1`). | `§6.1`, `§9` | Medium |

---

## 2. Feasibility (Claude Agent SDK)

**Verdict: Buildable, but 4 API mismatches need correction.**

| # | Issue | Detail |
|---|-------|--------|
| 1 | **MCP tool discovery not in SDK** | `ToolRegistry.register_mcp_server(... discovers tools on registration)` (`§5.2`) is not directly supported by documented SDK APIs. SDK shows passing MCP configs and explicit tool names, not discovery enumeration. |
| 2 | **Tool naming mismatch** | Design assumes `human_input_tool`/`ask_duckie`; SDK built-in is `AskUserQuestion`, and `ask_duckie` is not built-in. Need explicit aliasing or MCP provisioning. |
| 3 | **AgentRunner output parsing underspecified** | SDK `query()` yields message streams (assistant/tool/result blocks). `§5.7` needs a deterministic rule for extracting the final YAML payload from the stream. |
| 4 | **No concurrency throttling** | Voting fan-out is feasible but rate-limit/cost sensitive; no throttling specified for parallel agent calls (`§5.9`). |

Core `query()` + `allowed_tools` + `permission_mode` + `mcp_servers` usage is confirmed feasible.

---

## 3. Architecture

**Verdict: Good choice. 4 concerns to address.**

Event-driven + pluggable modules is the right pattern for maintainability and future UI integration.

| # | Concern | Detail |
|---|---------|--------|
| 1 | **Module interface too rigid** | `async process(event) -> list[Event]` (`§4.2`) is tight for long-running streaming work (agent samples, retries, intermediate vote state). An `AsyncIterator[Event]` interface would work better. |
| 2 | **Orchestrator vs bus roles blurred** | (`§4.1`, `§4.4`) — who owns routing decisions vs pure pub/sub emission should be explicit. |
| 3 | **Weak event typing** | `Event.data: dict` (`§6.4`) weakens type safety. Typed payload dataclasses per event type are preferable. |
| 4 | **Executor state unmodeled** | Executor has heavy hidden state (step outputs, vote counters, retry state) but state ownership/lifecycle is not modeled explicitly (`§5.6`, `§5.9`). |

---

## 4. Data Flow

**Verdict: Good intent, 5 gaps.**

| # | Gap | Detail |
|---|-----|--------|
| 1 | **Path grammar undefined** | Dot notation for arrays/indexing and escaped keys is not formalized. SPEC examples use indexed paths like `step_2_output.signals[0]`. `context_resolver` behavior needs a spec. |
| 2 | **`output_schema` is free-form string** | Brittle for red-flagging and voter canonicalization (`§5.8`, `§5.9`). Should be machine-readable (JSON Schema or Pydantic). |
| 3 | **No `task_description` ↔ `input_variables` cross-check** | No deterministic validation that references in task_description match declared input_variables. |
| 4 | **Conditional branching contract vague** | Runtime source of next step for `conditional_step` isn't fully defined (`§5.6`). How does the executor extract the integer from the conditional agent's output? |
| 5 | **No policy for large intermediate outputs** | When injecting prior step outputs into step prompts, no policy for prompt bloat/token limits (`§5.6`, `§5.7`). |

---

## 5. YAML Cleaner

**Verdict: Strong practical base. 5 edge cases to handle.**

| # | Risk | Detail |
|---|------|--------|
| 1 | **Deterministic fixes can change semantics** | Quoting/special-character rewrites may alter meaning (`§5.3`). |
| 2 | **Fence stripping fragile** | Needs to handle extra prose, multiple fenced blocks, and partial YAML wrappers. |
| 3 | **Single LLM repair attempt may be insufficient** | One try on cheapest model may not fix complex malformed outputs. |
| 4 | **No post-repair semantic guardrail** | Field names/types may silently drift after LLM repair. |
| 5 | **Return type too loose** | `parse()` returns `dict | list` but planner/executor need stricter expected structures. |

---

## 6. Tool Registry

**Verdict: Right pattern, 5 issues to fix.**

| # | Issue | Detail |
|---|-------|--------|
| 1 | **MCP discovery not implementable** | "Discover tools on registration" is not supported by documented SDK surface. Need explicit registration or preflight probe. |
| 2 | **No alias mapping** | Tool catalog must include canonical runtime names exactly as passed to `allowed_tools`. `human_input_tool` → `AskUserQuestion` alias is undefined. |
| 3 | **Tier-3 handling inconsistent** | Tier-3 tools (implicit in every step per SPEC) are inconsistent with step-level `allowed_tools` filtering. |
| 4 | **No health-check/reconnect** | No strategy for flaky MCP servers beyond "mark unavailable" (`§9`). |
| 5 | **Secret handling** | MCP env vars (tokens, keys) need log redaction rules. |

---

## 7. Voting Strategies

**Verdict: Good shape, 4 problems.**

| # | Problem | Detail |
|---|---------|--------|
| 1 | **Exact match too strict** | Semantically identical outputs with different ordering/formatting will split votes (`§5.9`). Need structural canonicalization before comparing. |
| 2 | **First-to-K underspecified** | "Over all others" is ambiguous and can stall. Define as `leader_count - runner_up_count >= K`. |
| 3 | **Missing config knobs** | No `max_samples`, `max_parallel`, or confidence fallback path in `TaskConfig` (`§6.1`). |
| 4 | **Correlated errors** | All samples use same model/prompt/tool policy — errors may be correlated, reducing voting effectiveness. |

---

## 8. Scalability for v2 (WebSocket/UI)

**Verdict: Good foundation, needs 5 additions now.**

| # | Gap | Detail |
|---|-----|--------|
| 1 | **EventBus fanout undefined** | `subscribe()` semantics for multi-consumer broadcast not specified (`§4.4`). |
| 2 | **No correlation IDs** | Events lack `task_id`/`session_id`/`run_id`, making multi-task multiplexing impossible (`§6.4`). |
| 3 | **No cancellation/pause/resume** | UI workflows need these; not even interface-level definitions exist. |
| 4 | **No event persistence/replay** | Reconnecting WebSocket clients can't catch up on missed events. |
| 5 | **In-memory only** | Single-process limitation unless refactored. |

---

## 9. Top 5 Risks (Highest First)

| Rank | Risk | Impact | Design Sections |
|------|------|--------|-----------------|
| 1 | **MCP tool discovery + naming mismatch** — Planner/executor reference tools that cannot actually be invoked | Plan generates, execution crashes | `§5.2`, `§5.6` |
| 2 | **Data-flow contract ambiguity** — `output_schema` strings + loose path grammar cause runtime breakage in chaining/red-flag/voting | Silent data corruption, wrong votes | `§5.6`, `§5.8`, `§6.2` |
| 3 | **Tier-3 SPEC behavior not enforceable** — Implicit tool availability and "check previous outputs first" not in validator/executor | SPEC compliance failure | `§5.5`, `§5.6` |
| 4 | **Voting non-termination** — Strict equality + no sample limits = potential infinite loop | Cost explosion, hang | `§5.9`, `§9` |
| 5 | **WebSocket v2 will require refactoring** — Missing event metadata/fanout/persistence | Architectural rework later | `§4.4`, `§6.4`, `§8.3` |

---

## 10. Recommendations

### R1: Add formal schema contract
- Replace `output_schema: str` with JSON Schema or Pydantic model references
- Define `input_variables` path grammar (dot + index syntax) and validate deterministically

### R2: Close SPEC coverage gaps in validator (`§5.5`)
- Add checks for user-instruction fidelity preservation
- Add checks for explicit `input_variables` vs `task_description` field references
- Add checks that tool sets exclude implicit Tier-3 tools
- Add checks that `output_schema` has no ellipsis

### R3: Fix tool model/runtime parity
- Define explicit alias map (`human_input_tool` → `AskUserQuestion`, `ask_duckie` → specific MCP tool name)
- Replace "discover tools on registration" with explicit registration or preflight probe

### R4: Harden AgentRunner protocol
- Specify exactly how to extract final assistant YAML from SDK message stream
- Add per-step `timeout`, `retry_limit`, and `budget` knobs in `TaskConfig`

### R5: Improve voting robustness
- Canonicalize outputs structurally (sort keys, normalize whitespace) before counting votes
- Define First-to-K formally as `leader_count - second_count >= K`
- Add `max_samples` and deterministic failure behavior to config

### R6: Future-proof v2 now
- Add `task_id`, `run_id`, `step_id`, and `sequence` fields to all events
- Clarify EventBus as true broadcast fanout with multiple subscribers
- Define cancellation interface and optional event persistence early
