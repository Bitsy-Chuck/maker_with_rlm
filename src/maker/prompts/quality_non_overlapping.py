QUALITY_NON_OVERLAPPING_PROMPT = """Evaluate whether the following two plan steps fetch overlapping or redundant information.

Step A:
{step_a_yaml}

Step B:
{step_b_yaml}

Score 0-1:
- 1.0: Steps fetch completely different information — no overlap
- 0.5: Minor overlap but each has unique primary purpose
- 0.0: Steps are largely redundant — one could be removed

Output ONLY a JSON object: {{"score": <float>, "reason": "<brief explanation>"}}"""
