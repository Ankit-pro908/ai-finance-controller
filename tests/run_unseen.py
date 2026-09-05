from pathlib import Path
import sys
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.stress_runner import (
    load_case_data,
)

from src.controller.orchestrator import (
    build_reconciliation_view,
    build_controller_case_for_payment,
    investigate_controller_case,
)


UNSEEN_DIR = (
    PROJECT_ROOT
    / "data"
    / "unseen"
)

GROUND_TRUTH = (
    UNSEEN_DIR
    / "ground_truth.csv"
)


def main():

    gt = pd.read_csv(
        GROUND_TRUTH
    )

    rows = []

    for _, truth in gt.iterrows():

        case_id = str(
            truth["case_id"]
        )

        payment_id = str(
            truth["payment_id"]
        )

        case_dir = (
            UNSEEN_DIR
            / "cases"
            / case_id
        )

        data = load_case_data(
            case_dir
        )

        view = build_reconciliation_view(
            data
        )

        case = (
            build_controller_case_for_payment(
                data,
                view,
                payment_id,
            )
        )

        result = (
            investigate_controller_case(
                case
            )
        )

        actual_decision = (
            result
            .get(
                "final_decision",
                {},
            )
            .get(
                "decision",
                "",
            )
        )

        rows.append(
            {
                "case_id": case_id,
                "payment_id": payment_id,
                "expected":
                    truth[
                        "expected_behavior"
                    ],
                "actual":
                    actual_decision,
                "mode":
                    result.get(
                        "investigation_mode"
                    ),
            }
        )

    out = pd.DataFrame(
        rows
    )

    print(
        "\n========================================"
    )
    print(
        "UNSEEN CASE RESULTS"
    )
    print(
        "========================================"
    )

    print(
        out.to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()