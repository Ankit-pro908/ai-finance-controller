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

from src.controller.orchestrator import (
    build_controller_case_for_payment,
    investigate_controller_case,
)

from src.reconciliation.engine import (
    build_payment_view,
    calculate_expected_settlement,
    classify_reconciliation,
    identify_exception_reason,
    validate_ledger,
    build_exception_report,
)


# =========================================================
# PATHS
# =========================================================

STRESS_DIR = (
    PROJECT_ROOT
    / "data"
    / "stress"
)

CASES_DIR = (
    STRESS_DIR
    / "cases"
)

GROUND_TRUTH_PATH = (
    STRESS_DIR
    / "ground_truth.csv"
)


# =========================================================
# LOAD ONE CASE
# =========================================================

def load_case_data(
    case_dir: Path,
):
    return {
        "payments": pd.read_csv(
            case_dir / "payments.csv"
        ),
        "fees": pd.read_csv(
            case_dir / "fees.csv"
        ),
        "refunds": pd.read_csv(
            case_dir / "refunds.csv"
        ),
        "settlements": pd.read_csv(
            case_dir / "settlements.csv"
        ),
        "ledger": pd.read_csv(
            case_dir / "ledger.csv"
        ),
    }


# =========================================================
# BUILD COMPLETE RECONCILIATION VIEW
# =========================================================

def build_full_payment_view(
    data,
):
    payment_view = build_payment_view(
        data
    )

    payment_view = (
        calculate_expected_settlement(
            payment_view
        )
    )

    payment_view = (
        classify_reconciliation(
            payment_view
        )
    )

    payment_view = (
        identify_exception_reason(
            data,
            payment_view,
        )
    )

    payment_view = (
        validate_ledger(
            data,
            payment_view,
        )
    )

    payment_view = (
        build_exception_report(
            payment_view
        )
    )

    return payment_view


# =========================================================
# EXPECTED FINAL DECISION
# =========================================================

def expected_decision(
    ground_truth,
):
    behavior = str(
        ground_truth[
            "expected_behavior"
        ]
    ).strip().upper()

    if behavior == "HUMAN_REVIEW":
        return "HUMAN_REVIEW"

    return "RESOLUTION_CANDIDATE"


# =========================================================
# SUCCESSFUL HYPOTHESES
# =========================================================

def get_successful_hypotheses(
    result,
):
    """
    Accept both statuses used by the controller.

    Deterministic cases may produce:
        DETERMINISTICALLY_SUPPORTED

    General/AI causal cases may produce:
        CAUSALLY_SUPPORTED
    """

    verification = result.get(
        "verification",
        [],
    )

    supported_statuses = {
        "CAUSALLY_SUPPORTED",
        "DETERMINISTICALLY_SUPPORTED",
    }

    successful = []

    for item in verification:

        status = str(
            item.get(
                "final_verification_status",
                "",
            )
        ).strip().upper()

        simulation = (
            item.get(
                "simulation"
            )
            or {}
        )

        if (
            status in supported_statuses
            and simulation.get(
                "exception_cleared"
            )
            is True
        ):
            successful.append(
                item
            )

    return successful


# =========================================================
# SUCCESSFUL SIMULATION CHANGE
# =========================================================

def get_successful_change(
    result,
):
    successful = (
        get_successful_hypotheses(
            result
        )
    )

    if len(successful) != 1:
        return None

    simulation = (
        successful[0].get(
            "simulation"
        )
        or {}
    )

    if (
        simulation.get(
            "status"
        )
        != "SUCCESS"
    ):
        return None

    if (
        simulation.get(
            "exception_cleared"
        )
        is not True
    ):
        return None

    changes = simulation.get(
        "applied_changes",
        [],
    )

    if not changes:
        return None

    return changes[0]


# =========================================================
# CHECK FINAL RESOLUTION PATH
# =========================================================

def check_resolution_path(
    ground_truth,
    result,
):
    expected = expected_decision(
        ground_truth
    )

    actual = result[
        "final_decision"
    ].get(
        "decision"
    )

    successful = (
        get_successful_hypotheses(
            result
        )
    )

    # -----------------------------------------------------
    # HUMAN REVIEW
    # -----------------------------------------------------

    if expected == "HUMAN_REVIEW":

        return (
            actual == "HUMAN_REVIEW"
            and len(successful) == 0
        )

    # -----------------------------------------------------
    # RESOLUTION CANDIDATE
    # -----------------------------------------------------

    if actual != (
        "RESOLUTION_CANDIDATE"
    ):
        return False

    if len(successful) != 1:
        return False

    simulation = (
        successful[0].get(
            "simulation"
        )
        or {}
    )

    if (
        simulation.get(
            "status"
        )
        != "SUCCESS"
    ):
        return False

    if (
        simulation.get(
            "exception_cleared"
        )
        is not True
    ):
        return False

    return True


# =========================================================
# CHECK OPERATION
# =========================================================

def check_operation(
    ground_truth,
    result,
):
    expected_type = str(
        ground_truth[
            "exception_type"
        ]
    ).strip().upper()

    expected_decision_value = (
        expected_decision(
            ground_truth
        )
    )

    # -----------------------------------------------------
    # HUMAN REVIEW CASES
    #
    # No successful change should be required.
    # -----------------------------------------------------

    if (
        expected_decision_value
        == "HUMAN_REVIEW"
    ):

        successful = (
            get_successful_hypotheses(
                result
            )
        )

        return (
            result[
                "final_decision"
            ].get(
                "decision"
            )
            == "HUMAN_REVIEW"
            and len(successful) == 0
        )

    # -----------------------------------------------------
    # RESOLUTION CASES
    # -----------------------------------------------------

    change = (
        get_successful_change(
            result
        )
    )

    if change is None:
        return False

    operation = str(
        change.get(
            "operation",
            ""
        )
    ).strip().upper()

    source = str(
        change.get(
            "source",
            ""
        )
    ).strip().lower()

    # Settlement mismatch
    if expected_type == (
        "SETTLEMENT_AMOUNT_MISMATCH"
    ):

        return (
            operation == "SET_VALUE"
            and source == "settlement"
        )

    # Fee mismatch
    if expected_type == (
        "FEE_MISMATCH"
    ):

        return (
            operation == "SET_VALUE"
            and source == "fee"
        )

    # Refund mismatch
    if expected_type == (
        "REFUND_MISMATCH"
    ):

        return (
            operation == "SET_VALUE"
            and source == "refund"
        )

    # Missing settlement
    if expected_type == (
        "MISSING_SETTLEMENT"
    ):

        return (
            operation == "ADD_RECORD"
            and source == "settlement"
        )

    # Missing ledger
    if expected_type == (
        "MISSING_LEDGER_ENTRY"
    ):

        return (
            operation == "ADD_RECORD"
            and source == "ledger"
        )

    # Duplicate payment
    if expected_type == (
        "DUPLICATE_PAYMENT"
    ):

        return (
            operation == "REMOVE_RECORD"
            and source == "payment"
        )

    # Conflicting evidence
    if expected_type == (
        "CONFLICTING_EVIDENCE"
    ):

        return (
            result[
                "final_decision"
            ].get(
                "decision"
            )
            == "HUMAN_REVIEW"
        )

    return False


# =========================================================
# RUN ONE CASE
# =========================================================

def run_case(
    case_id,
    ground_truth,
):
    payment_id = str(
        ground_truth[
            "payment_id"
        ]
    )

    case_dir = (
        CASES_DIR
        / case_id
    )

    if not case_dir.exists():
        raise FileNotFoundError(
            f"Missing case directory: "
            f"{case_dir}"
        )

    data = load_case_data(
        case_dir
    )

    payment_view = (
        build_full_payment_view(
            data
        )
    )

    controller_case = (
        build_controller_case_for_payment(
            data,
            payment_view,
            payment_id,
        )
    )

    result = (
        investigate_controller_case(
            controller_case
        )
    )

    expected = expected_decision(
        ground_truth
    )

    actual = result[
        "final_decision"
    ].get(
        "decision"
    )

    decision_ok = (
        expected == actual
    )

    path_ok = (
        check_resolution_path(
            ground_truth,
            result,
        )
    )

    operation_ok = (
        check_operation(
            ground_truth,
            result,
        )
    )

    successful = (
        get_successful_hypotheses(
            result
        )
    )

    return {
        "case_id": case_id,
        "payment_id": payment_id,
        "exception_type": str(
            ground_truth[
                "exception_type"
            ]
        ),
        "true_root_cause": str(
            ground_truth[
                "true_root_cause"
            ]
        ),
        "expected_decision": expected,
        "actual_decision": actual,
        "decision_ok": decision_ok,
        "resolution_path_ok": path_ok,
        "operation_ok": operation_ok,
        "passed": (
            decision_ok
            and path_ok
            and operation_ok
        ),
        "investigation_mode": result.get(
            "investigation_mode"
        ),
        "successful_hypotheses": len(
            successful
        ),
    }


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "\n========================================"
    )

    print(
        "100-CASE STRESS TEST"
    )

    print(
        "========================================"
    )

    if not GROUND_TRUTH_PATH.exists():

        raise FileNotFoundError(
            "Stress ground truth not found: "
            f"{GROUND_TRUTH_PATH}"
        )

    ground_truth_df = (
        pd.read_csv(
            GROUND_TRUTH_PATH
        )
    )

    results = []

    failures = []

    total_rows = len(
        ground_truth_df
    )

    for position, (_, row) in enumerate(
        ground_truth_df.iterrows(),
        start=1,
    ):

        case_id = str(
            row["case_id"]
        )

        print(
            f"[{position}/{total_rows}] "
            f"Processing {case_id} "
            f"({row['payment_id']})"
        )

        try:

            result = run_case(
                case_id,
                row,
            )

            results.append(
                result
            )

            if not result[
                "passed"
            ]:

                failures.append(
                    result
                )

                print(
                    "  ❌ FAILED"
                )

                print(
                    "  Expected:"
                    f" {result['expected_decision']}"
                )

                print(
                    "  Actual:"
                    f" {result['actual_decision']}"
                )

                print(
                    "  Decision check:"
                    f" {result['decision_ok']}"
                )

                print(
                    "  Resolution path:"
                    f" {result['resolution_path_ok']}"
                )

                print(
                    "  Operation check:"
                    f" {result['operation_ok']}"
                )

            else:

                print(
                    "  ✅ PASSED"
                )

        except Exception as error:

            failure = {
                "case_id": case_id,
                "payment_id": str(
                    row["payment_id"]
                ),
                "exception_type": str(
                    row[
                        "exception_type"
                    ]
                ),
                "true_root_cause": str(
                    row[
                        "true_root_cause"
                    ]
                ),
                "expected_decision": (
                    expected_decision(
                        row
                    )
                ),
                "actual_decision": "ERROR",
                "decision_ok": False,
                "resolution_path_ok": False,
                "operation_ok": False,
                "passed": False,
                "investigation_mode": "ERROR",
                "successful_hypotheses": 0,
                "error": str(error),
            }

            results.append(
                failure
            )

            failures.append(
                failure
            )

            print(
                "  ❌ ERROR"
            )

            print(
                f"  {error}"
            )

    results_df = pd.DataFrame(
        results
    )

    # =====================================================
    # SUMMARY
    # =====================================================

    total = len(
        results_df
    )

    passed = int(
        results_df[
            "passed"
        ].sum()
    )

    failed = (
        total - passed
    )

    decision_accuracy = (
        results_df[
            "decision_ok"
        ].mean()
        * 100
        if total
        else 0
    )

    resolution_path_accuracy = (
        results_df[
            "resolution_path_ok"
        ].mean()
        * 100
        if total
        else 0
    )

    operation_accuracy = (
        results_df[
            "operation_ok"
        ].mean()
        * 100
        if total
        else 0
    )

    pass_rate = (
        passed / total * 100
        if total
        else 0
    )

    print(
        "\n========================================"
    )

    print(
        "STRESS TEST SUMMARY"
    )

    print(
        "========================================"
    )

    print(
        f"Total cases:                 {total}"
    )

    print(
        f"Passed:                      {passed}"
    )

    print(
        f"Failed:                      {failed}"
    )

    print(
        f"Pass rate:                   "
        f"{pass_rate:.2f}%"
    )

    print(
        f"Decision accuracy:           "
        f"{decision_accuracy:.2f}%"
    )

    print(
        f"Resolution-path accuracy:    "
        f"{resolution_path_accuracy:.2f}%"
    )

    print(
        f"Operation accuracy:          "
        f"{operation_accuracy:.2f}%"
    )

    # =====================================================
    # BY TYPE
    # =====================================================

    print(
        "\nBy exception type:"
    )

    grouped = (
        results_df.groupby(
            "exception_type"
        )
        .agg(
            cases=(
                "case_id",
                "count",
            ),
            passed=(
                "passed",
                "sum",
            ),
        )
    )

    grouped[
        "pass_rate"
    ] = (
        grouped[
            "passed"
        ]
        / grouped[
            "cases"
        ]
        * 100
    )

    print(
        grouped
    )

    # =====================================================
    # FAILURES
    # =====================================================

    if failures:

        print(
            "\n========================================"
        )

        print(
            "FAILURES"
        )

        print(
            "========================================"
        )

        for failure in failures:

            print(
                f"\n{failure['case_id']} "
                f"({failure['payment_id']})"
            )

            print(
                "Exception:"
                f" {failure['exception_type']}"
            )

            print(
                "Expected:"
                f" {failure['expected_decision']}"
            )

            print(
                "Actual:"
                f" {failure['actual_decision']}"
            )

            print(
                "Decision check:"
                f" {failure['decision_ok']}"
            )

            print(
                "Resolution path:"
                f" {failure['resolution_path_ok']}"
            )

            print(
                "Operation check:"
                f" {failure['operation_ok']}"
            )

            if "error" in failure:

                print(
                    "Error:"
                    f" {failure['error']}"
                )

    # =====================================================
    # SAVE RESULTS
    # =====================================================

    output_path = (
        STRESS_DIR
        / "stress_results.csv"
    )

    results_df.to_csv(
        output_path,
        index=False,
    )

    print(
        f"\nDetailed results saved to:"
    )

    print(
        output_path
    )

    print(
        "\n========================================"
    )

    if failed == 0:

        print(
            "✅ ALL STRESS CASES PASSED"
        )

    else:

        print(
            "⚠️ REAL FAILURES DETECTED"
        )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()