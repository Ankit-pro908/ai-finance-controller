from typing import Any


AI_RESPONSE_SCHEMA = {
    "root_cause": "string",
    "explanation": "string",
    "supporting_evidence": [
        {
            "source": "string",
            "record_id": "string",
            "field": "string",
            "claimed_value": "number_or_null",
            "claim_type": "DIRECT_VALUE|ABSENCE|COMPARISON",
            "reason": "string",
        }
    ],
    "evidence_sufficient": "boolean",
    "confidence": "number_0_to_1",
    "recommended_action": "string",
}