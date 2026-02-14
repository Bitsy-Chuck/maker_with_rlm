QUALITY_SELF_CONTAINED_PROMPT = """Evaluate whether the following plan step's task_description is complete enough that an isolated agent (with no knowledge of the overall plan) can execute it.

Step:
{step_yaml}

Score 0-1:
- 1.0: Fully self-contained — all context, inputs, and expected output are explicit
- 0.5: Mostly self-contained but some context is implicit or vague
- 0.0: Requires knowledge of the overall plan or references undefined variables

Output ONLY a JSON object: {{"score": <float>, "reason": "<brief explanation>"}}"""
