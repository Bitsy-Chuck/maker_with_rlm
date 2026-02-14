QUALITY_APPROPRIATELY_MERGED_PROMPT = """Evaluate whether the following two plan steps should be merged into a single step. Steps should be merged when they use the same tool to fetch multiple related fields that come from a single call.

Step A:
{step_a_yaml}

Step B:
{step_b_yaml}

Score 0-1:
- 1.0: Steps are correctly separate — merging would combine unrelated work
- 0.5: Steps could go either way — minor efficiency gain from merging
- 0.0: Steps should definitely be merged — they query the same source for related data

Output ONLY a JSON object: {{"score": <float>, "reason": "<brief explanation>"}}"""
