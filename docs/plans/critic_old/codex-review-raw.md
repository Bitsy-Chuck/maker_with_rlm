## 1. Completeness

Strong baseline: the design covers the main MAKER loop (planner → validator → executor → voting → result) and is clearly decomposed (`§4.1`, `§5.4`-`§5.10`).

Key missing pieces relative to `SPEC.md`:

- Top-level plan schema mismatch: `SPEC.md` requires `reasoning` + `plan` list, but the design model uses `Plan.steps` (`§6.3`). You need an explicit mapping rule (`plan` → `steps`) or the parser/validator contract is ambiguous.
- Tier-3 tool semantics from SPEC are not fully implemented: `human_input_tool`/`ask_duckie` implicit availability and “check previous outputs first” behavior are not represented in executor logic (`§5.6`, `§5.7`) or validation checks (`§5.5`).
- Critical SPEC fidelity rules are not validated: preserving user-provided URLs/IDs/endpoints, no hallucinated references, and explicit propagation are absent from deterministic checks (`§5.5`).
- Output-chaining validation is incomplete: no check that every field referenced in `task_description` is present in `input_variables`, and no check that schemas avoid ellipsis/implicit fields (`§5.5`, `§6.2`).
- Operational controls are underspecified: step timeouts, per-step retry limits, and max voting attempts are referenced behaviorally (`§9`) but missing in config (`§6.1`).

## 2. Feasibility (Claude Agent SDK)

Buildable overall, but a few API mismatches need correction:

- `query()` + `allowed_tools` + `permission_mode` + `mcp_servers` usage is feasible (`§5.6`, `§5.7` aligns with SDK reference).
- **Inference from SDK reference:** `ToolRegistry.register_mcp_server(... discovers tools on registration)` (`§5.2`) is not directly supported by documented SDK APIs. SDK shows passing MCP configs and explicit tool names, not discovery enumeration.
- Tool naming mismatch risk: design assumes `human_input_tool`/`ask_duckie`; SDK built-in is `AskUserQuestion`, and `ask_duckie` is not built-in. You need explicit aliasing or MCP provisioning (`§5.2`, `§5.6`).
- AgentRunner output parsing is underspecified: SDK `query()` yields message streams (assistant/tool/result blocks). `§5.7` needs a deterministic rule for extracting the final YAML payload.
- Voting fan-out is feasible but rate-limit/cost sensitive; no concurrency throttling is specified (`§5.9`).

## 3. Architecture

Event-driven + pluggable modules is a good choice for maintainability and future UI integration (`§3`, `§4.1`).

Architecture concerns:

- `async process(event) -> list[Event]` (`§4.2`) is tight for long-running streaming work (agent samples, retries, intermediate vote state). An async event emitter or `AsyncIterator[Event]` interface will work better in practice.
- Orchestrator vs bus responsibilities are blurred (`§4.1`, `§4.4`): who owns routing decisions vs pure pub/sub emission should be explicit.
- `Event.data: dict` (`§6.4`) weakens type safety for a system relying on strict data flow; typed payload classes per event are preferable.
- Executor has heavy hidden state (step outputs, vote counters, retry state), but state ownership/lifecycle is not modeled explicitly (`§5.6`, `§5.9`).

## 4. Data Flow

Good intent: explicit `output_variable` and dot-notation chaining (`§5.6`, `§6.2`).

Gaps:

- Dot notation grammar is undefined for arrays/indexing and escaped keys, but SPEC examples use indexed paths. `context_resolver` behavior should be formalized (`§7` mentions file, no spec in `§5.6`).
- `output_schema` as free-form string (`§6.2`) is brittle for red-flagging and voter canonicalization (`§5.8`, `§5.9`). Prefer machine-readable schema (JSON Schema/Pydantic).
- No deterministic check that `task_description` references exactly match declared `input_variables` (`§5.5`).
- Conditional branching contract is vague: runtime source of next step for `conditional_step` isn’t fully defined (`§5.6`, `§6.2`).
- No policy for large intermediate outputs (prompt bloat/token limits) when injecting prior outputs into step prompts (`§5.6`, `§5.7`).

## 5. YAML Cleaner

Three-stage repair pipeline is a strong practical base (`§5.3`).

Risks/edge cases:

- Deterministic “auto-fixes” can change semantics (especially quoting/special-character rewrites) (`§5.3`).
- Fence stripping needs to handle extra prose, multiple fenced blocks, and partial YAML wrappers (`§5.3`).
- Single LLM repair attempt on cheapest model may be insufficient for complex malformed outputs (`§5.3`).
- No post-repair semantic guardrail: field names/types may silently drift after LLM repair (`§5.3`).
- `parse()` returns `dict | list` but planner/executor need stricter expected structures (`§5.3`, `§5.4`, `§5.7`).

## 6. Tool Registry

Central registry abstraction is the right pattern (`§5.2`).

Issues to fix:

- MCP “discover tools on registration” is likely not implementable as written with documented SDK surface (`§5.2`).
- Tool catalog must include canonical runtime names exactly as passed to `allowed_tools`; alias mapping is not defined (`§5.2`, `§5.6`).
- Tier-3 tool handling is inconsistent with step-level `allowed_tools` filtering (`§5.6`).
- No explicit health-check/reconnect strategy for flaky MCP servers beyond “mark unavailable” (`§9`).
- Secret handling (MCP env vars) needs log redaction rules (`§5.2`).

## 7. Voting Strategies

Overall shape is good (`§5.9`), especially modular strategy classes.

Problems:

- “Exact serialized output match” for majority is too strict; semantically identical outputs with different ordering/formatting will split votes (`§5.9`).
- First-to-K definition is underspecified. Use “ahead of runner-up by K” with clear tie semantics; current wording “over all others” is ambiguous and can stall (`§5.9`).
- No explicit `max_samples`, `max_parallel`, or confidence fallback path in config (`§6.1`, `§9`).
- Correlated errors remain likely because all samples use same model/prompt/tool policy (`§2`, `§5.9`).

## 8. Scalability for v2 (WebSocket/UI)

The event-first interface is a good foundation (`§8.1`, `§8.3`), but not yet enough for UI-scale ops:

- `EventBus.subscribe()` semantics are unclear for multi-consumer fanout (`§4.4`).
- Events lack task/session correlation IDs in the base model (`§6.4`), making multi-task multiplexing hard.
- No cancellation/pause/resume APIs, which UI workflows need.
- No event persistence/replay for reconnecting clients.
- In-memory state design implies one-process limitation unless refactored.

## 9. Top Risks (Highest First)

1. MCP tool discovery and naming mismatch causes planner/executor to reference tools that cannot actually be invoked (`§5.2`, `§5.6`).
2. Data-flow contract ambiguity (`output_schema` strings + loose path grammar) causes runtime breakage in chaining/red-flag/voting (`§5.6`, `§5.8`, `§6.2`).
3. Tier-3 SPEC behavior is not enforceable with current validator/executor design, reducing correctness against core requirements (`§5.5`, `§5.6`).
4. Voting non-termination/low consensus due to strict equality and missing sample limits (`§5.9`, `§9`).
5. WebSocket v2 will require architectural changes unless event metadata/fanout/persistence are defined now (`§4.4`, `§6.4`, `§8.3`).

## 10. Recommendations

1. Add a formal schema contract:
- Replace `output_schema: str` with JSON Schema/Pydantic model references.
- Define `input_variables` path grammar (dot + index syntax) and validate it deterministically.

2. Close SPEC coverage gaps in validator (`§5.5`):
- Add checks for user-instruction fidelity preservation.
- Add checks for explicit `input_variables` vs `task_description` field references.
- Add checks that tool sets exclude implicit Tier-3 tools and that `output_schema` has no ellipsis.

3. Fix tool model/runtime parity:
- Define explicit alias map (`human_input_tool` → `AskUserQuestion`, `ask_duckie` → specific MCP tool name).
- Remove/replace “discover tools on registration” with explicit registration or preflight probe.

4. Harden AgentRunner protocol:
- Specify exactly how to extract final assistant YAML from SDK message stream.
- Add per-step timeout/retry/budget knobs in `TaskConfig`.

5. Improve voting robustness:
- Canonicalize outputs structurally before counting votes.
- Define first-to-K as `leader_count - second_count >= K`.
- Add `max_samples` and deterministic failure behavior.

6. Future-proof v2 now:
- Add `task_id`, `run_id`, `step_id`, and `sequence` to all events.
- Clarify EventBus as true broadcast fanout.
- Define cancellation and optional event persistence interfaces early.