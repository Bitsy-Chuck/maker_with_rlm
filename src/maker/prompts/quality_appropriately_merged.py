QUALITY_APPROPRIATELY_MERGED_PROMPT = """Evaluate whether any steps in the following plan should be merged into a single step. Steps should be merged when they use the same tool to fetch multiple related fields that come from a single call.

Plan:
{plan_yaml}

Score 0-1:
- 1.0: All steps are correctly separate — merging any would combine unrelated work
- 0.5: Some steps could go either way — minor efficiency gain from merging
- 0.0: Multiple steps should definitely be merged — they query the same source for related data

Output ONLY a JSON object: {{"score": <float>, "reason": "<brief explanation>"}}"""
