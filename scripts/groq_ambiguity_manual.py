from src.ai.client import call_groq


prompt = """
Return ONLY valid JSON.

Return exactly this structure:

{
  "hypotheses": [
    {
      "hypothesis_id": "H1",
      "root_cause": "string",
      "explanation": "string",
      "affected_records": [],
      "causal_relationship": {
        "type": "OTHER",
        "claimed_delta": null,
        "direction": "UNKNOWN"
      }
    }
  ]
}

Situation:

A financial exception has two materially plausible explanations:
1. an additional fee
2. a refund discrepancy

Return TWO hypotheses, one for each possibility.

Do not invent records, IDs, or amounts.
"""


print(
    call_groq(
        prompt,
        max_attempts=1,
    )
)