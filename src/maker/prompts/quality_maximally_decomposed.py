QUALITY_MAXIMALLY_DECOMPOSED_PROMPT = """Evaluate whether the following plan step is maximally decomposed — i.e., it cannot be meaningfully split into smaller subtasks.

Step:
{step_yaml}

Score 0-1:
- 1.0: Step is atomic — splitting further would lose coherence
- 0.5: Step could potentially be split but the split is debatable
- 0.0: Step clearly combines multiple distinct subtasks that should be separate

Output ONLY a JSON object: {{"score": <float>, "reason": "<brief explanation>"}}"""
