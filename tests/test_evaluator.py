from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.controller.orchestrator import (
    build_reconciliation_view,
    build_controller_case_for_payment,
    investigate_controller_case,
)
from src.evidence.retriever import load_exception_data


# ---------------------------------------------------------
# Controlled seven-case expectations derived from the
# project's ground_truth.csv semantics.
# ---------------------------------------------------------
EXPECTED = {
    "SETTLEMENT_AMOUNT_ERROR": {
        "decision": "RESOLUTION_CANDIDATE",
        "operation": "SET_VALUE",
        "source": "settlement",
    },
    "SETTLEMENT_RECORD_MISSING": {
        "decision": "RESOLUTION_CANDIDATE",
        "operation": "ADD_RECORD",
        "source": "settlement",
    },
    "FEE_AMOUNT_ERROR": {
        "decision": "RESOLUTION_CANDIDATE",
        "operation": "SET_VALUE",
        "source": "fee",
    },
    "REFUND_AMOUNT_ERROR": {
        "decision": "RESOLUTION_CANDIDATE",
        "operation": "SET_VALUE",
        "source": "refund",
    },
    "LEDGER_RECORD_MISSING": {
        "decision": "RESOLUTION_CANDIDATE",
        "operation": "ADD_RECORD",
        "source": "ledger",
    },
    "DUPLICATE_PAYMENT_RECORD": {
        "decision": "RESOLUTION_CANDIDATE",
        "operation": "REMOVE_RECORD",
        "source": "payment",
    },
    "INSUFFICIENT_EVIDENCE": {
        "decision": "HUMAN_REVIEW",
        "operation": None,
        "source": None,
    },
}


def _ground_truth_path() -> Path:
    return Path("data") / "ground_truth.csv"


def _successful_applied_change(
    result: dict[str, Any],
) -> dict[str, Any] | None:
    for verification in result.get("verification", []):

        if verification.get(
            "final_verification_status"
        ) not in {
            "CAUSALLY_SUPPORTED",
            "DETERMINISTICALLY_SUPPORTED",
        }:
            continue

        simulation = (
            verification.get("simulation")
            or {}
        )

        for change in simulation.get(
            "applied_changes",
            [],
        ):
            return change

    return None


def _resolved_hypothesis_count(result: dict[str, Any]) -> int:
    return len(
        [
            item
            for item in result.get("verification", [])
            if item.get("final_verification_status")
            in {
                "CAUSALLY_SUPPORTED",
                "DETERMINISTICALLY_SUPPORTED",
            }
        ]
    )


def evaluate() -> int:
    ground_truth_path = _ground_truth_path()
    if not ground_truth_path.exists():
        raise FileNotFoundError(
            f"Ground truth file not found: {ground_truth_path}"
        )

    ground_truth = pd.read_csv(ground_truth_path)
    data = load_exception_data()
    payment_view = build_reconciliation_view(data)

    rows: list[dict[str, Any]] = []
    failures: list[str] = []

    for _, truth in ground_truth.iterrows():
        payment_id = str(truth["payment_id"])
        true_root_cause = str(truth["true_root_cause"])
        expected = EXPECTED.get(true_root_cause)

        if expected is None:
            failures.append(
                f"{payment_id}: no evaluator rule for {true_root_cause}"
            )
            continue

        case = build_controller_case_for_payment(
            data,
            payment_view,
            payment_id,
        )
        result = investigate_controller_case(case)
        decision = result.get("final_decision", {}).get("decision")
        verification = result.get("verification", [])
        resolved_count = _resolved_hypothesis_count(result)
        change = _successful_applied_change(
            result
        )

        decision_ok = decision == expected["decision"]

        if expected["decision"] == "RESOLUTION_CANDIDATE":
            resolution_ok = resolved_count == 1
            operation_ok = bool(change) and change.get("operation") == expected["operation"]
            source_ok = bool(change) and change.get("source") == expected["source"]
            case_ok = decision_ok and resolution_ok and operation_ok and source_ok
        else:
            # Ambiguous case: it must remain unresolved and must
            # expose competing hypotheses rather than silently fail.
            hypothesis_count = len(verification)
            unresolved_count = sum(
                1
                for item in verification
                if item.get("final_verification_status")
                not in {
                    "CAUSALLY_SUPPORTED",
                    "DETERMINISTICALLY_SUPPORTED",
                }
            )
            case_ok = (
                decision_ok
                and resolved_count == 0
                and hypothesis_count >= 2
                and unresolved_count == hypothesis_count
            )
            resolution_ok = resolved_count == 0
            operation_ok = True
            source_ok = True

        if not case_ok:
            failures.append(
                f"{payment_id}: expected {expected}, "
                f"got decision={decision}, resolved={resolved_count}, "
                f"change={change}"
            )

        rows.append(
            {
                "payment_id": payment_id,
                "true_root_cause": true_root_cause,
                "expected_decision": expected["decision"],
                "actual_decision": decision,
                "decision_ok": decision_ok,
                "resolved_hypotheses": resolved_count,
                "applied_operation": None if not change else change.get("operation"),
                "applied_source": None if not change else change.get("source"),
                "resolution_path_ok": resolution_ok,
                "evaluator_pass": case_ok,
            }
        )

    print("\n========================================")
    print("SEVEN-CASE CONTROLLER EVALUATION")
    print("========================================")
    print(pd.DataFrame(rows).to_string(index=False))

    passed = sum(1 for row in rows if row["evaluator_pass"])
    total = len(rows)

    print("\n========================================")
    print(f"FINAL SCORE: {passed}/{total}")
    print("========================================")

    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("All seven controlled cases passed the evaluator.")
    return 0


if __name__ == "__main__":
    raise SystemExit(evaluate())
