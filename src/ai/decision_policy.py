def decide_next_action(
    ai_response: dict,
    evidence_completeness: dict,
    evidence_consistency: dict,
    evidence_validation: dict,
    reconciliation_reason: str,
) -> dict:
    """
    Convert AI output and deterministic system signals
    into a safe controller decision.
    """

    confidence = float(
        ai_response["confidence"]
    )

    completeness = float(
        evidence_completeness[
            "completeness_percentage"
        ]
    )

    citations_valid = (
        evidence_validation[
            "all_citations_valid"
        ]
    )

    evidence_sufficient = bool(
        ai_response[
            "evidence_sufficient"
        ]
    )

    conflicts = evidence_consistency.get(
        "conflicts",
        []
    )

    # -------------------------------------------------
    # HARD SAFETY GATE 1:
    # Deterministic duplicate detection
    # cannot be overridden by the LLM.
    # -------------------------------------------------

    if reconciliation_reason == "DUPLICATE_PAYMENT":

        return {
            "decision": "HUMAN_REVIEW",
            "reason": (
                "Deterministic duplicate-payment "
                "detection requires explicit review."
            ),
        }

    # -------------------------------------------------
    # HARD SAFETY GATE 2:
    # Invalid AI citations
    # -------------------------------------------------

    if not citations_valid:

        return {
            "decision": "HUMAN_REVIEW",
            "reason": (
                "AI cited evidence that could not "
                "be independently validated."
            ),
        }

    # -------------------------------------------------
    # HARD SAFETY GATE 3:
    # Evidence incomplete
    # -------------------------------------------------

    if completeness < 100:

        return {
            "decision": "HUMAN_REVIEW",
            "reason": (
                "Required evidence is incomplete."
            ),
        }

    # -------------------------------------------------
    # HARD SAFETY GATE 4:
    # Evidence conflicts
    # -------------------------------------------------

    if conflicts:

        return {
            "decision": "HUMAN_REVIEW",
            "reason": (
                "Evidence contains conflicts "
                "or ambiguous explanations."
            ),
        }

    # -------------------------------------------------
    # HARD SAFETY GATE 5:
    # AI itself says insufficient evidence
    # -------------------------------------------------

    if not evidence_sufficient:

        return {
            "decision": "HUMAN_REVIEW",
            "reason": (
                "AI determined that the evidence "
                "is insufficient."
            ),
        }

    # -------------------------------------------------
    # HARD SAFETY GATE 6:
    # Confidence threshold
    # -------------------------------------------------

    if confidence < 0.85:

        return {
            "decision": "HUMAN_REVIEW",
            "reason": (
                "AI confidence is below the "
                "auto-resolution threshold."
            ),
        }

    # -------------------------------------------------
    # Safe resolution recommendation
    # -------------------------------------------------

    return {
        "decision": "INVESTIGATE_AND_RESOLVE",
        "reason": (
            "Evidence is complete, consistent, "
            "independently validated, and AI "
            "confidence meets the threshold."
        ),
    }