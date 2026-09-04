from src.ai.client import call_groq


def test_groq_hypothesis_shape():

    prompt = """
Return ONLY valid JSON.

{
  "hypotheses": [
    {
      "hypothesis_id": "H1",
      "root_cause": "string",
      "explanation": "string",
      "affected_records": [],
      "causal_relationship": {
        "type": "RECORD_DELTA",
        "claimed_delta": null,
        "direction": "UNKNOWN"
      },
      "testable": true,
      "confidence": 0.0
    }
  ]
}

Return exactly one hypothesis.

Do not include any text outside the JSON object.
"""

    result = call_groq(
        prompt,
        max_attempts=1,
    )

    assert isinstance(
        result,
        dict,
    )

    assert "hypotheses" in result