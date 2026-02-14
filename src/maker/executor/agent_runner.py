import claude_agent_sdk as sdk
from maker.core.models import PlanStep, AgentResult, TaskConfig
from maker.yaml_cleaner.cleaner import YAMLCleaner, YAMLParseError
from maker.prompts import load_prompt


class AgentRunner:
    def __init__(self):
        self._yaml_cleaner = YAMLCleaner()

    async def run(self, step: PlanStep, context: str, config: TaskConfig) -> AgentResult:
        """Run one isolated agent for one step.

        1. Build prompt from step description + context
        2. Call SDK query() with step's tools
        3. Extract last TextBlock from final AssistantMessage
        4. Parse through YAML cleaner
        5. Return AgentResult
        """
        prompt = load_prompt(
            "executor_step",
            task_description=step.task_description,
            context=context or "None",
            output_schema=step.output_schema,
        )

        # Combine primary + fallback + implicit AskUserQuestion
        allowed_tools = list(step.primary_tools) + list(step.fallback_tools)
        if "AskUserQuestion" not in allowed_tools:
            allowed_tools.append("AskUserQuestion")

        # Collect messages from stream
        assistant_messages = []
        result_message = None

        async for msg in self._sdk_query(prompt, allowed_tools=allowed_tools, model=config.model):
            cls_name = type(msg).__name__
            if cls_name == "AssistantMessage":
                assistant_messages.append(msg)
            elif cls_name == "ResultMessage":
                result_message = msg

        # Handle empty stream
        if not assistant_messages:
            return AgentResult(
                output={},
                raw_response="",
                was_repaired=False,
                tokens=0,
                cost_usd=result_message.total_cost_usd if result_message else 0.0,
                duration_ms=result_message.duration_ms if result_message else 0,
                error="No assistant messages received",
            )

        # Check for error in result message
        if result_message and result_message.subtype == "error":
            return AgentResult(
                output={},
                raw_response="",
                was_repaired=False,
                tokens=0,
                cost_usd=result_message.total_cost_usd or 0.0,
                duration_ms=result_message.duration_ms,
                error=f"Agent returned error status",
            )

        # Extract last TextBlock from final AssistantMessage
        final_msg = assistant_messages[-1]
        raw_text = ""
        for block in final_msg.content:
            if type(block).__name__ == "TextBlock":
                raw_text = block.text

        # Parse through YAML cleaner
        try:
            parsed, was_repaired = await self._yaml_cleaner.parse(raw_text)
        except YAMLParseError as e:
            return AgentResult(
                output={},
                raw_response=raw_text,
                was_repaired=False,
                tokens=0,
                cost_usd=result_message.total_cost_usd if result_message else 0.0,
                duration_ms=result_message.duration_ms if result_message else 0,
                error=f"YAML parse error: {e}",
            )

        return AgentResult(
            output=parsed,
            raw_response=raw_text,
            was_repaired=was_repaired,
            tokens=0,
            cost_usd=result_message.total_cost_usd if result_message else 0.0,
            duration_ms=result_message.duration_ms if result_message else 0,
            error=None,
        )

    async def _sdk_query(self, prompt: str, **kwargs):
        """Call claude-agent-sdk query(). Yields message stream.
        This method exists to be easily mocked in tests."""
        allowed_tools = kwargs.pop("allowed_tools", [])
        model = kwargs.pop("model", None)

        options = sdk.ClaudeAgentOptions(
            allowed_tools=allowed_tools,
            model=model,
            permission_mode="bypassPermissions",
        )

        async for msg in sdk.query(prompt=prompt, options=options):
            yield msg
