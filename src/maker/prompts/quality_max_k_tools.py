QUALITY_MAX_K_TOOLS_PROMPT = """Evaluate whether the following plan step can be completed with at most {max_k} tool calls.

Step:
{step_yaml}

Score 0-1:
- 1.0: Can clearly be completed in {max_k} or fewer tool calls
- 0.5: Might require more than {max_k} tool calls depending on conditions
- 0.0: Clearly requires more than {max_k} tool calls

Output ONLY a JSON object: {{"score": <float>, "reason": "<brief explanation>"}}"""
