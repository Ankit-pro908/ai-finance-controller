from typing import Any


def build_controller_case(
    payment_id: str,
    reconciliation: dict[str, Any],
    evidence: dict[str, Any],
    evidence_completeness: dict[str, Any],
    evidence_consistency: dict[str, Any],
) -> dict[str, Any]:
    """
    Build the canonical case object used by the
    finance controller.

    This object contains facts gathered by the system.
    It does not contain ground truth and it does not
    contain an AI conclusion.
    """

    return {
        "case_id": f"CASE-{payment_id}",

        "payment_id": payment_id,

        "financial_facts": {
            "reconciliation": reconciliation,
        },

        "evidence": evidence,

        "evidence_quality": {
            "completeness": evidence_completeness,
            "consistency": evidence_consistency,
        },

        "ai_analysis": None,

        "verification": None,

        "resolution": None,

        "final_decision": None,
    }