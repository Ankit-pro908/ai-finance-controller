from typing import Any


def verify_hypothesis(
    hypothesis: dict[str, Any],
    controller_case: dict[str, Any],
) -> dict[str, Any]:
    """
    Verify whether an AI-generated hypothesis is
    supported by the controller's financial facts
    and retrieved evidence.

    This function does not call the LLM.
    """

    reconciliation = controller_case[
        "financial_facts"
    ]["reconciliation"]

    claimed_delta = hypothesis.get(
        "claimed_delta"
    )

    if claimed_delta is None:

        return {
            "status": "UNVERIFIABLE",
            "reason": (
                "Hypothesis does not specify "
                "a claimed financial delta."
            ),
        }

    observed_difference = (
        reconciliation["difference"]
    )

    try:
        claimed_delta = float(
            claimed_delta
        )

        observed_difference = float(
            observed_difference
        )

    except (TypeError, ValueError):

        return {
            "status": "UNVERIFIABLE",
            "reason": (
                "Financial delta is not numeric."
            ),
        }

    # Compare magnitude first because accounting
    # direction may be represented by a sign.
    delta_matches = (
        abs(
            abs(claimed_delta)
            - abs(observed_difference)
        )
        <= 0.01
    )

    if not delta_matches:

        return {
            "status": "REJECTED",
            "reason": (
                "Hypothesis delta does not "
                "match the observed reconciliation "
                "difference."
            ),
            "observed_difference": (
                observed_difference
            ),
            "claimed_delta": claimed_delta,
        }

    return {
        "status": "SUPPORTED_DELTA",
        "reason": (
            "Hypothesis claims a financial "
            "delta matching the observed "
            "reconciliation difference."
        ),
        "observed_difference": (
            observed_difference
        ),
        "claimed_delta": claimed_delta,
    }

if __name__ == "__main__":

    test_case = {
        "financial_facts": {
            "reconciliation": {
                "difference": -250.00,
            }
        }
    }

    supported_hypothesis = {
        "hypothesis_id": "H1",
        "root_cause": (
            "Refund mismatch"
        ),
        "claimed_delta": 250.00,
    }

    wrong_hypothesis = {
        "hypothesis_id": "H2",
        "root_cause": (
            "Fee mismatch"
        ),
        "claimed_delta": 500.00,
    }

    print(
        "\n--- Supported Hypothesis ---"
    )

    print(
        verify_hypothesis(
            supported_hypothesis,
            test_case,
        )
    )

    print(
        "\n--- Wrong Hypothesis ---"
    )

    print(
        verify_hypothesis(
            wrong_hypothesis,
            test_case,
        )
    )