def validate_ai_response(response: dict) -> dict:
    """
    Validate the structure and basic constraints
    of an AI investigation response.
    """

    required_fields = [
        "root_cause",
        "explanation",
        "supporting_evidence",
        "evidence_sufficient",
        "confidence",
        "recommended_action",
    ]

    missing_fields = [
        field
        for field in required_fields
        if field not in response
    ]

    if missing_fields:
        raise ValueError(
            f"Missing AI response fields: "
            f"{missing_fields}"
        )

    confidence = response["confidence"]

    if not isinstance(confidence, (int, float)):
        raise ValueError(
            "Confidence must be a number."
        )

    if not 0 <= confidence <= 1:
        raise ValueError(
            "Confidence must be between 0 and 1."
        )

    if not isinstance(
        response["evidence_sufficient"],
        bool,
    ):
        raise ValueError(
            "evidence_sufficient must be boolean."
        )

    if not isinstance(
        response["supporting_evidence"],
        list,
    ):
        raise ValueError(
            "supporting_evidence must be a list."
        )

    return response

if __name__ == "__main__":

    test_response = {
        "root_cause": "REFUND_AMOUNT_MISMATCH",

        "explanation": (
            "Refund and ledger refund amounts "
            "differ by Rs. 250."
        ),

        "supporting_evidence": [
            {
                "source": "refunds",
                "record_id": "REF00001",
                "reason": (
                    "Refund amount is Rs. 3062.92."
                ),
            }
        ],

        "evidence_sufficient": True,

        "confidence": 0.94,

        "recommended_action": "HUMAN_REVIEW",
    }

    validated = validate_ai_response(
        test_response
    )

    print(
        "\nAI response validation passed."
    )

    print(validated)