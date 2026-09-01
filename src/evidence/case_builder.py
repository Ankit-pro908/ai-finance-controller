from pathlib import Path

import pandas as pd
try:
    from .completeness import (
        calculate_evidence_completeness,
    )
except ImportError:
    from completeness import (
        calculate_evidence_completeness,
    )


PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent.parent
)


def build_investigation_case(
    payment_id: str,
    reconciliation_row: pd.Series,
    evidence: dict,
):

    completeness = calculate_evidence_completeness(
        evidence
    )

    case = {
        "case_id": f"CASE-{payment_id}",

        "payment_id": payment_id,

        "reconciliation": {
            "status": reconciliation_row[
                "reconciliation_status"
            ],
            "reason": reconciliation_row[
                "exception_reason"
            ],
            "expected_settlement": reconciliation_row[
                "expected_settlement"
            ],
            "actual_settlement": reconciliation_row[
                "actual_settlement"
            ],
            "difference": reconciliation_row[
                "difference"
            ],
        },

        "evidence": {
            "payment": evidence["payment"],
            "fees": evidence["fees"],
            "refunds": evidence["refunds"],
            "settlement": evidence["settlement"],
            "ledger": evidence["ledger"],
        },

        "evidence_completeness": completeness,
    }

    return case