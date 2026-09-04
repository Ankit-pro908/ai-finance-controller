import pandas as pd

from src.controller.causal_verifier import (
    verify_hypothesis,
)


def build_pay00004_case():

    return {
        "financial_facts": {
            "reconciliation": {
                "difference": -250.00,
            }
        },

        "evidence": {
            "payment": pd.DataFrame(
                [
                    {
                        "payment_id": "PAY00004",
                        "amount": 8524.00,
                    }
                ]
            ),

            "fees": pd.DataFrame(
                [
                    {
                        "fee_id": "FEE00004",
                        "fee_amount": 170.48,
                    }
                ]
            ),

            "refunds": pd.DataFrame(
                [
                    {
                        "refund_id": "REF00001",
                        "refund_amount": 3062.92,
                    }
                ]
            ),

            "settlement": pd.DataFrame(
                [
                    {
                        "settlement_id": "SET00004",
                        "settlement_amount": 5540.60,
                    }
                ]
            ),

            "ledger": pd.DataFrame(
                [
                    {
                        "ledger_id": "LED00009",
                        "entry_type": "REFUND",
                        "amount": -2812.92,
                    }
                ]
            ),
        },
    }


def test_refund_hypothesis_is_causally_supported():

    case = build_pay00004_case()

    hypothesis = {
        "hypothesis_id": "H1",

        "root_cause": (
            "Ledger refund amount discrepancy"
        ),

        "affected_records": [
            {
                "source": "ledger",
                "record_id": "LED00009",
                "field": "amount",
                "observed_value": -2812.92,
                "role": "LEDGER_AMOUNT",
            },
            {
                "source": "refund",
                "record_id": "REF00001",
                "field": "refund_amount",
                "observed_value": 3062.92,
                "role": "REFUND_AMOUNT",
            },
        ],

        "causal_relationship": {
            "type": "RECORD_DELTA",
            "claimed_delta": 250.00,
            "direction": "INCREASE",
        },

        "testable": True,
        "confidence": 0.9,
    }

    result = verify_hypothesis(
        hypothesis,
        case,
    )

    assert result["status"] == (
            "CAUSAL_CANDIDATE"
    )


def test_wrong_delta_is_rejected():

    case = build_pay00004_case()

    hypothesis = {
        "hypothesis_id": "H1",

        "root_cause": (
            "Wrong financial explanation"
        ),

        "affected_records": [
            {
                "source": "ledger",
                "record_id": "LED00009",
                "field": "amount",
                "observed_value": -2812.92,
                "role": "LEDGER_AMOUNT",
            },
            {
                "source": "refund",
                "record_id": "REF00001",
                "field": "refund_amount",
                "observed_value": 3062.92,
                "role": "REFUND_AMOUNT",
            },
        ],

        "causal_relationship": {
            "type": "RECORD_DELTA",
            "claimed_delta": 500.00,
            "direction": "INCREASE",
        },

        "testable": True,
        "confidence": 0.8,
    }

    result = verify_hypothesis(
        hypothesis,
        case,
    )

    assert result["status"] == (
        "NOT_SUPPORTED"
    )