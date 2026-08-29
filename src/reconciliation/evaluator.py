from pathlib import Path

import pandas as pd


PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent.parent
)

DATA_DIR = PROJECT_ROOT / "data"


def load_ground_truth():
    return pd.read_csv(
        DATA_DIR / "ground_truth.csv"
    )


def evaluate_detection(
    reconciliation_df: pd.DataFrame,
) -> None:

    ground_truth_df = load_ground_truth()

    expected_payment_ids = set(
        ground_truth_df["payment_id"]
    )

    detected_payment_ids = set(
        reconciliation_df.loc[
            reconciliation_df["final_status"]
            == "EXCEPTION",
            "payment_id",
        ]
    )

    correctly_detected = (
        expected_payment_ids
        & detected_payment_ids
    )

    missed_exceptions = (
        expected_payment_ids
        - detected_payment_ids
    )

    print("\n--- Detection Evaluation ---")

    print(
        f"Expected exception payments : "
        f"{len(expected_payment_ids)}"
    )

    print(
        f"Detected exception payments : "
        f"{len(detected_payment_ids)}"
    )

    print(
        f"Correctly detected          : "
        f"{len(correctly_detected)}"
    )

    print(
        f"Missed                       : "
        f"{len(missed_exceptions)}"
    )

    if missed_exceptions:
        print(
            "\nMissed payment IDs:"
        )

        for payment_id in sorted(
            missed_exceptions
        ):
            print(
                f" - {payment_id}"
            )

    detection_rate = (
        len(correctly_detected)
        / len(expected_payment_ids)
        * 100
        if expected_payment_ids
        else 0
    )

    print(
        f"\nDetection Rate: "
        f"{detection_rate:.2f}%"
    )