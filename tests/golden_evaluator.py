from pathlib import Path
import sys

import pandas as pd


# =========================================================
# PROJECT ROOT
# =========================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent
)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


# =========================================================
# PROJECT IMPORTS
# =========================================================

from src.evidence.retriever import (
    load_exception_data,
)

from src.controller.orchestrator import (
    build_reconciliation_view,
    build_controller_case_for_payment,
    investigate_controller_case,
)


# =========================================================
# EXPECTED DECISION MAPPING
# =========================================================

EXPECTED_DECISION_MAP = {
    "INVESTIGATE_AND_RESOLVE":
        "RESOLUTION_CANDIDATE",

    "HUMAN_REVIEW":
        "HUMAN_REVIEW",
}


# =========================================================
# HELPERS
# =========================================================

def normalize_text(
    value,
) -> str:
    return str(
        value
    ).strip().upper()


def get_selected_hypothesis(
    result: dict,
):
    """
    Return the hypothesis that the controller selected
    for resolution.

    The controller stores the complete hypothesis directly
    inside verification[].
    """

    resolution = (
        result.get(
            "resolution"
        )
        or {}
    )

    selected_id = resolution.get(
        "hypothesis_id"
    )

    if not selected_id:
        return None

    for verification in result.get(
        "verification",
        [],
    ):

        if verification.get(
            "hypothesis_id"
        ) == selected_id:

            return verification

    return None


# =========================================================
# ROOT CAUSE CHECK
# =========================================================
def root_cause_matches(
    expected_root_cause: str,
    result: dict,
) -> bool:
    """
    Validate the selected verified hypothesis against
    the expected golden root-cause category.
    """

    expected = normalize_text(
        expected_root_cause
    )

    # -------------------------------------------------
    # Insufficient evidence
    # -------------------------------------------------

    if expected == "INSUFFICIENT_EVIDENCE":

        return (
            normalize_text(
                result.get(
                    "final_decision",
                    {},
                ).get(
                    "decision",
                    "",
                )
            )
            == "HUMAN_REVIEW"
        )

    # -------------------------------------------------
    # Get selected resolution hypothesis
    # -------------------------------------------------

    resolution = (
        result.get(
            "resolution"
        )
        or {}
    )

    selected_id = resolution.get(
        "hypothesis_id"
    )

    if not selected_id:
        return False

    # -------------------------------------------------
    # Find selected verification entry
    # -------------------------------------------------

    selected = None

    for verification in result.get(
        "verification",
        [],
    ):

        if (
            verification.get(
                "hypothesis_id"
            )
            == selected_id
        ):

            selected = verification
            break

    if selected is None:
        return False

    # -------------------------------------------------
    # Require successful verification
    # -------------------------------------------------

    final_status = normalize_text(
        selected.get(
            "final_verification_status",
            "",
        )
    )

    if final_status not in {
        "CAUSALLY_SUPPORTED",
        "DETERMINISTICALLY_SUPPORTED",
    }:
        return False

    # -------------------------------------------------
    # Extract the actual hypothesis
    # -------------------------------------------------

    affected_records = selected.get(
        "affected_records",
        [],
    )

    sources = {
        normalize_text(
            record.get(
                "source",
                "",
            )
        ).lower()
        for record in affected_records
    }

    fields = {
        normalize_text(
            record.get(
                "field",
                "",
            )
        ).lower()
        for record in affected_records
    }

    # -------------------------------------------------
    # IMPORTANT:
    #
    # Your actual controller stores the relationship
    # type inside causal_verification["relationship_type"].
    # -------------------------------------------------

    causal_verification = (
        selected.get(
            "causal_verification",
            {}
        )
        or {}
    )

    relationship_type = normalize_text(
        causal_verification.get(
            "relationship_type",
            "",
        )
    )

    # -------------------------------------------------
    # Amount errors
    # -------------------------------------------------

    if expected == "SETTLEMENT_AMOUNT_ERROR":

        return (
            "settlement" in sources
            and "settlement_amount" in fields
        )

    if expected == "FEE_AMOUNT_ERROR":

        return (
            "fee" in sources
            and "fee_amount" in fields
        )

    if expected == "REFUND_AMOUNT_ERROR":

        return (
            "refund" in sources
            and "refund_amount" in fields
        )

    # -------------------------------------------------
    # Missing settlement
    # -------------------------------------------------

    if expected == "SETTLEMENT_RECORD_MISSING":

        return (
            relationship_type
            == "MISSING_RECORD"
            and "settlement" in sources
        )

    # -------------------------------------------------
    # Missing ledger record
    # -------------------------------------------------

    if expected == "LEDGER_RECORD_MISSING":

        return (
            relationship_type
            == "MISSING_RECORD"
            and "ledger" in sources
        )

    # -------------------------------------------------
    # Duplicate payment
    # -------------------------------------------------

    if expected == "DUPLICATE_PAYMENT_RECORD":

        return (
            relationship_type
            == "DUPLICATE_RECORD"
            and "payment" in sources
        )

    return False


# =========================================================
# MAIN GOLDEN EVALUATION
# =========================================================

def main() -> int:

    print(
        "\n========================================"
    )

    print(
        "GOLDEN CASE EVALUATION"
    )

    print(
        "========================================"
    )

    # -----------------------------------------------------
    # Load ground truth
    # -----------------------------------------------------

    ground_truth_path = (
        PROJECT_ROOT
        / "data"
        / "ground_truth.csv"
    )

    if not ground_truth_path.exists():

        print(
            "\nERROR: ground_truth.csv not found:"
        )

        print(
            ground_truth_path
        )

        return 1

    ground_truth = pd.read_csv(
        ground_truth_path
    )

    required_columns = {
        "exception_id",
        "payment_id",
        "exception_type",
        "true_root_cause",
        "expected_behavior",
    }

    missing_columns = (
        required_columns
        - set(
            ground_truth.columns
        )
    )

    if missing_columns:

        print(
            "\nERROR: ground_truth.csv is missing:"
        )

        print(
            sorted(
                missing_columns
            )
        )

        return 1

    # -----------------------------------------------------
    # Load application data
    # -----------------------------------------------------

    data = load_exception_data()

    # -----------------------------------------------------
    # Build reconciliation once
    # -----------------------------------------------------

    payment_view = (
        build_reconciliation_view(
            data
        )
    )

    results = []

    # =====================================================
    # EVALUATE EACH GOLDEN CASE
    # =====================================================

    for _, truth in ground_truth.iterrows():

        payment_id = str(
            truth["payment_id"]
        )

        expected_exception = normalize_text(
            truth["exception_type"]
        )

        expected_root_cause = normalize_text(
            truth["true_root_cause"]
        )

        expected_behavior = normalize_text(
            truth["expected_behavior"]
        )

        expected_decision = (
            EXPECTED_DECISION_MAP.get(
                expected_behavior
            )
        )

        print(
            f"\nChecking {payment_id} ..."
        )

        try:

            # -------------------------------------------------
            # Build controller case
            # -------------------------------------------------

            case = (
                build_controller_case_for_payment(
                    data,
                    payment_view,
                    payment_id,
                )
            )

            # -------------------------------------------------
            # Run controller
            # -------------------------------------------------

            result = (
                investigate_controller_case(
                    case
                )
            )

            # -------------------------------------------------
            # Actual exception
            # -------------------------------------------------

            actual_exception = normalize_text(
                result[
                    "financial_facts"
                ][
                    "reconciliation"
                ].get(
                    "reason",
                    "",
                )
            )

            # -------------------------------------------------
            # Actual decision
            # -------------------------------------------------

            actual_decision = normalize_text(
                result.get(
                    "final_decision",
                    {},
                ).get(
                    "decision",
                    "",
                )
            )

            # -------------------------------------------------
            # Compare
            # -------------------------------------------------

            exception_ok = (
                actual_exception
                == expected_exception
            )

            decision_ok = (
                actual_decision
                == expected_decision
            )

            root_cause_ok = (
                root_cause_matches(
                    expected_root_cause,
                    result,
                )
            )

            passed = (
                exception_ok
                and decision_ok
                and root_cause_ok
            )

            results.append(
                {
                    "exception_id":
                        truth[
                            "exception_id"
                        ],

                    "payment_id":
                        payment_id,

                    "expected_exception":
                        expected_exception,

                    "actual_exception":
                        actual_exception,

                    "expected_root_cause":
                        expected_root_cause,

                    "expected_decision":
                        expected_decision,

                    "actual_decision":
                        actual_decision,

                    "exception_ok":
                        exception_ok,

                    "root_cause_ok":
                        root_cause_ok,

                    "decision_ok":
                        decision_ok,

                    "passed":
                        passed,
                }
            )

        except Exception as error:

            results.append(
                {
                    "exception_id":
                        truth[
                            "exception_id"
                        ],

                    "payment_id":
                        payment_id,

                    "expected_exception":
                        expected_exception,

                    "actual_exception":
                        "ERROR",

                    "expected_root_cause":
                        expected_root_cause,

                    "expected_decision":
                        expected_decision,

                    "actual_decision":
                        "ERROR",

                    "exception_ok":
                        False,

                    "root_cause_ok":
                        False,

                    "decision_ok":
                        False,

                    "passed":
                        False,

                    "error":
                        str(error),
                }
            )

    # =====================================================
    # RESULTS TABLE
    # =====================================================

    result_df = pd.DataFrame(
        results
    )

    print(
        "\n========================================"
    )

    print(
        "GOLDEN RESULTS"
    )

    print(
        "========================================"
    )

    print(
        result_df[
            [
                "exception_id",
                "payment_id",
                "expected_exception",
                "actual_exception",
                "expected_root_cause",
                "expected_decision",
                "actual_decision",
                "exception_ok",
                "root_cause_ok",
                "decision_ok",
                "passed",
            ]
        ].to_string(
            index=False
        )
    )

    # =====================================================
    # SUMMARY
    # =====================================================

    passed_count = int(
        result_df[
            "passed"
        ].sum()
    )

    total_count = len(
        result_df
    )

    print(
        "\n========================================"
    )

    print(
        f"Golden cases passed: "
        f"{passed_count}/{total_count}"
    )

    print(
        "========================================"
    )

    if passed_count == total_count:

        print(
            "\n✅ GOLDEN SUITE PASS"
        )

        print(
            "All golden cases match the "
            "ground-truth contract."
        )

        return 0

    print(
        "\n❌ GOLDEN SUITE FAIL"
    )

    print(
        "Do not freeze the implementation yet."
    )

    return 1


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    raise SystemExit(
        main()
    )