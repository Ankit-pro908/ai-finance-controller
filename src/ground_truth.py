from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


GROUND_TRUTH_COLUMNS = [
    "exception_id",
    "payment_id",
    "exception_type",
    "true_root_cause",
    "expected_amount",
    "actual_amount",
    "difference",
    "expected_behavior",
]


def create_ground_truth(exception):

    expected_amount = exception["original_amount"]
    actual_amount = exception["wrong_amount"]

    difference = round(
        expected_amount - actual_amount,
        2,
    )

    ground_truth = {
        "exception_id": "EX00001",
        "payment_id": exception["payment_id"],
        "exception_type": "SETTLEMENT_AMOUNT_MISMATCH",
        "true_root_cause": "SETTLEMENT_AMOUNT_ERROR",
        "expected_amount": expected_amount,
        "actual_amount": actual_amount,
        "difference": difference,
        "expected_behavior": "INVESTIGATE_AND_RESOLVE",
    }

    return pd.DataFrame(
        [ground_truth],
        columns=GROUND_TRUTH_COLUMNS,
    )


if __name__ == "__main__":

    print("Ground truth module created.")