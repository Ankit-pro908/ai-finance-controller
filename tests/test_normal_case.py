import pandas as pd

from src.controller.orchestrator import (
    investigate_controller_case,
)


def test_balanced_transaction_bypasses_ai():

    case = {

        "payment_id": "PAY_NORMAL",

        "financial_facts": {
            "reconciliation": {

                "status": "MATCH",

                "reason": "NONE",

                "expected_settlement": 100.00,

                "actual_settlement": 100.00,

                "difference": 0.00,

                "ledger_net": 100.00,

                "ledger_difference": 0.00,

                "ledger_status": "MATCH",

                "final_status": "MATCH",
            }
        },

        "evidence": {

            "payment": pd.DataFrame(),

            "fees": pd.DataFrame(),

            "refunds": pd.DataFrame(),

            "settlement": pd.DataFrame(),

            "ledger": pd.DataFrame(),
        },

        "evidence_quality": {

            "completeness": {},

            "consistency": {},
        },
    }

    result = (
        investigate_controller_case(
            case
        )
    )

    assert (
        result[
            "final_decision"
        ]["decision"]
        == "AUTO_CLOSED"
    )

    assert (
        result["ai_analysis"]
        is None
    )