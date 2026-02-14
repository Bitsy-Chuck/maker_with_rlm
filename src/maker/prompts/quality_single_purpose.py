QUALITY_SINGLE_PURPOSE_PROMPT = """Evaluate whether the following plan step has a single, focused purpose.

Step:
{step_yaml}

Score 0-1:
- 1.0: Step has exactly one clear purpose
- 0.5: Step has a primary purpose with minor secondary concerns
- 0.0: Step tries to accomplish multiple unrelated things

Output ONLY a JSON object: {{"score": <float>, "reason": "<brief explanation>"}}"""
