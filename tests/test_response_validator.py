from src.ai.response_validator import (
    validate_ai_response,
)


def test_record_delta_requires_proposed_value():

    response = {
        "hypotheses": [
            {
                "hypothesis_id": "H1",
                "root_cause": "Example discrepancy",
                "explanation": "Two records differ.",
                "affected_records": [
                    {
                        "source": "refund",
                        "record_id": "REF1",
                        "field": "refund_amount",
                        "observed_value": 100.0,
                        "proposed_value": None,
                        "role": "REFUND_AMOUNT",
                    },
                    {
                        "source": "ledger",
                        "record_id": "LED1",
                        "field": "amount",
                        "observed_value": -90.0,
                        "proposed_value": None,
                        "role": "LEDGER_AMOUNT",
                    },
                ],
                "causal_relationship": {
                    "type": "RECORD_DELTA",
                    "claimed_delta": 10.0,
                    "direction": "UNKNOWN",
                },
                "testable": True,
                "confidence": 0.5,
            }
        ]
    }

    try:
        validate_ai_response(
            response
        )

    except ValueError as error:

        assert (
            "proposed_value"
            in str(error)
        )

    else:

        raise AssertionError(
            "Expected RECORD_DELTA without "
            "proposed_value to fail."
        )