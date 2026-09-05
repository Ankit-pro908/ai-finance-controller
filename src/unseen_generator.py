from pathlib import Path
from typing import Any
import random

import pandas as pd


# =========================================================
# PATHS
# =========================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent
)

DATA_DIR = PROJECT_ROOT / "data"

UNSEEN_DIR = (
    DATA_DIR / "unseen"
)

CASES_DIR = (
    UNSEEN_DIR / "cases"
)


# =========================================================
# LOAD BASELINE
# =========================================================

def load_baseline_data():
    return {
        "payments": pd.read_csv(
            DATA_DIR / "payments.csv"
        ),
        "fees": pd.read_csv(
            DATA_DIR / "fees.csv"
        ),
        "refunds": pd.read_csv(
            DATA_DIR / "refunds.csv"
        ),
        "settlements": pd.read_csv(
            DATA_DIR / "settlements.csv"
        ),
        "ledger": pd.read_csv(
            DATA_DIR / "ledger.csv"
        ),
    }


def create_working_copy(data):
    return {
        name: dataframe.copy(
            deep=True
        )
        for name, dataframe in data.items()
    }


# =========================================================
# GROUND TRUTH
# =========================================================

def make_ground_truth(
    case_id: str,
    payment_id: str,
    exception_type: str,
    true_root_cause: str,
    expected_behavior: str,
):
    return {
        "case_id": case_id,
        "payment_id": payment_id,
        "exception_type": exception_type,
        "true_root_cause": true_root_cause,
        "expected_behavior": expected_behavior,
    }


# =========================================================
# U001
# COMPOUND FEE + LEDGER INCONSISTENCY
# =========================================================

def inject_compound_fee_ledger_error(
    data,
    payment_id: str,
):
    fees = data["fees"]
    ledger = data["ledger"]

    fee_rows = fees[
        fees["payment_id"].astype(str)
        == str(payment_id)
    ]

    ledger_fee_rows = ledger[
        (
            ledger["payment_id"].astype(str)
            == str(payment_id)
        )
        &
        (
            ledger["entry_type"].astype(str).str.upper()
            == "FEE"
        )
    ]

    if fee_rows.empty or ledger_fee_rows.empty:
        return None

    fee_index = fee_rows.index[0]
    ledger_index = ledger_fee_rows.index[0]

    # Fee source is changed by +50.
    original_fee = float(
        fees.at[
            fee_index,
            "fee_amount",
        ]
    )

    fees.at[
        fee_index,
        "fee_amount",
    ] = round(
        original_fee + 50.0,
        2,
    )

    # Ledger fee is independently changed by -50.
    original_ledger_fee = float(
        ledger.at[
            ledger_index,
            "amount",
        ]
    )

    ledger.at[
        ledger_index,
        "amount",
    ] = round(
        original_ledger_fee - 50.0,
        2,
    )

    return make_ground_truth(
        "U001",
        payment_id,
        "COMPOUND_FEE_LEDGER_INCONSISTENCY",
        "MULTIPLE_RECORDS_INCONSISTENT",
        "HUMAN_REVIEW",
    )


# =========================================================
# U002
# UNEXPECTED LEDGER ADJUSTMENT
# =========================================================

def inject_unexpected_adjustment(
    data,
    payment_id: str,
):
    ledger = data["ledger"]

    rows = ledger[
        ledger["payment_id"].astype(str)
        == str(payment_id)
    ]

    if rows.empty:
        return None

    payment_rows = rows[
        rows["entry_type"].astype(str).str.upper()
        == "PAYMENT"
    ]

    if payment_rows.empty:
        return None

    payment_row = payment_rows.iloc[0]

    adjustment_amount = 25.0

    new_id = (
        f"LED_UNSEEN_{payment_id}"
    )

    new_row = {
        "ledger_id": new_id,
        "payment_id": payment_id,
        "entry_type": "ADJUSTMENT",
        "amount": -adjustment_amount,
        "created_at": payment_row["created_at"],
    }

    data["ledger"] = pd.concat(
        [
            ledger,
            pd.DataFrame([new_row]),
        ],
        ignore_index=True,
    )

    return make_ground_truth(
        "U002",
        payment_id,
        "UNEXPECTED_LEDGER_ADJUSTMENT",
        "UNSUPPORTED_LEDGER_ADJUSTMENT",
        "HUMAN_REVIEW",
    )


# =========================================================
# U003
# DUPLICATE FEE RECORD
# =========================================================

def inject_duplicate_fee(
    data,
    payment_id: str,
):
    fees = data["fees"]

    rows = fees[
        fees["payment_id"].astype(str)
        == str(payment_id)
    ]

    if rows.empty:
        return None

    original = (
        rows.iloc[0]
        .copy()
    )

    original[
        "fee_id"
    ] = (
        f"{original['fee_id']}_DUP_UNSEEN"
    )

    data["fees"] = pd.concat(
        [
            fees,
            pd.DataFrame(
                [original]
            ),
        ],
        ignore_index=True,
    )

    return make_ground_truth(
        "U003",
        payment_id,
        "DUPLICATE_FEE_RECORD",
        "DUPLICATE_FEE_RECORD",
        "INVESTIGATE_AND_RESOLVE",
    )


# =========================================================
# U004
# MULTIPLE FEE RECORDS WITH DIFFERENT VALUES
# =========================================================

def inject_conflicting_fee_records(
    data,
    payment_id: str,
):
    fees = data["fees"]

    rows = fees[
        fees["payment_id"].astype(str)
        == str(payment_id)
    ]

    if rows.empty:
        return None

    original = (
        rows.iloc[0]
        .copy()
    )

    original[
        "fee_id"
    ] = (
        f"{original['fee_id']}_ALT_UNSEEN"
    )

    original[
        "fee_amount"
    ] = round(
        float(
            original[
                "fee_amount"
            ]
        ) + 35.0,
        2,
    )

    data["fees"] = pd.concat(
        [
            fees,
            pd.DataFrame(
                [original]
            ),
        ],
        ignore_index=True,
    )

    return make_ground_truth(
        "U004",
        payment_id,
        "CONFLICTING_FEE_RECORDS",
        "CONFLICTING_FEE_EVIDENCE",
        "HUMAN_REVIEW",
    )


# =========================================================
# U005
# REFUND + FEE INTERACTION
# =========================================================

def inject_fee_refund_interaction(
    data,
    payment_id: str,
):
    fees = data["fees"]
    refunds = data["refunds"]

    fee_rows = fees[
        fees["payment_id"].astype(str)
        == str(payment_id)
    ]

    refund_rows = refunds[
        refunds["payment_id"].astype(str)
        == str(payment_id)
    ]

    if fee_rows.empty or refund_rows.empty:
        return None

    fee_index = fee_rows.index[0]
    refund_index = refund_rows.index[0]

    fees.at[
        fee_index,
        "fee_amount",
    ] = round(
        float(
            fees.at[
                fee_index,
                "fee_amount",
            ]
        ) + 50.0,
        2,
    )

    refunds.at[
        refund_index,
        "refund_amount",
    ] = round(
        float(
            refunds.at[
                refund_index,
                "refund_amount",
            ]
        ) + 50.0,
        2,
    )

    return make_ground_truth(
        "U005",
        payment_id,
        "COMPOUND_FEE_REFUND_EXCEPTION",
        "MULTIPLE_PLAUSIBLE_CAUSES",
        "HUMAN_REVIEW",
    )


# =========================================================
# GENERATE UNSEEN CASES
# =========================================================

def generate_unseen_cases(
    seed: int = 42,
):
    random.seed(seed)

    baseline = (
        load_baseline_data()
    )

    payment_ids = (
        baseline[
            "payments"
        ][
            "payment_id"
        ]
        .astype(str)
        .tolist()
    )

    generators = [
        inject_compound_fee_ledger_error,
        inject_unexpected_adjustment,
        inject_duplicate_fee,
        inject_conflicting_fee_records,
        inject_fee_refund_interaction,
    ]

    scenarios = []

    case_number = 1

    for generator in generators:

        attempts = 0

        while attempts < 50:

            attempts += 1

            payment_id = random.choice(
                payment_ids
            )

            working = (
                create_working_copy(
                    baseline
                )
            )

            ground_truth = generator(
                working,
                payment_id,
            )

            if ground_truth is None:
                continue

            ground_truth[
                "case_id"
            ] = (
                f"U{case_number:03d}"
            )

            scenarios.append(
                {
                    "case_id":
                        ground_truth[
                            "case_id"
                        ],
                    "data":
                        working,
                    "ground_truth":
                        ground_truth,
                }
            )

            case_number += 1

            break

    return scenarios


# =========================================================
# SAVE DATASET
# =========================================================

def save_unseen_batch(
    scenarios,
):
    UNSEEN_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    CASES_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    ground_truth_rows = []

    for scenario in scenarios:

        case_id = scenario[
            "case_id"
        ]

        case_dir = (
            CASES_DIR / case_id
        )

        case_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        for name, dataframe in (
            scenario[
                "data"
            ].items()
        ):

            dataframe.to_csv(
                case_dir
                / f"{name}.csv",
                index=False,
            )

        ground_truth_rows.append(
            scenario[
                "ground_truth"
            ]
        )

    ground_truth_df = (
        pd.DataFrame(
            ground_truth_rows
        )
    )

    ground_truth_df.to_csv(
        UNSEEN_DIR
        / "ground_truth.csv",
        index=False,
    )

    return ground_truth_df


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    print(
        "\n========================================"
    )

    print(
        "BUILDING UNSEEN TEST DATASET"
    )

    print(
        "========================================"
    )

    scenarios = (
        generate_unseen_cases(
            seed=42
        )
    )

    ground_truth_df = (
        save_unseen_batch(
            scenarios
        )
    )

    print(
        f"\nGenerated unseen cases: "
        f"{len(scenarios)}"
    )

    print(
        "\nGround truth:"
    )

    print(
        ground_truth_df.to_string(
            index=False
        )
    )

    print(
        "\nSaved to:"
    )

    print(
        UNSEEN_DIR
    )