QUALITY_NON_OVERLAPPING_PROMPT = """Evaluate whether any steps in the following plan fetch overlapping or redundant information.

Plan:
{plan_yaml}

Score 0-1:
- 1.0: All steps fetch completely different information — no overlap
- 0.5: Minor overlap between some steps but each has a unique primary purpose
- 0.0: Multiple steps are largely redundant — some could be removed

Output ONLY a JSON object: {{"score": <float>, "reason": "<brief explanation>"}}"""
