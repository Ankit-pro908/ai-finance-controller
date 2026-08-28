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


def create_ground_truth(records):
    """
    Convert a list of ground-truth records into a DataFrame.
    """

    return pd.DataFrame(
        records,
        columns=GROUND_TRUTH_COLUMNS,
    )