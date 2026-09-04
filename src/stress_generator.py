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

STRESS_DIR = (
    DATA_DIR / "stress"
)


# =========================================================
# DATA HELPERS
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
# GROUND TRUTH RECORD
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
# 1. SETTLEMENT AMOUNT MISMATCH
# =========================================================

def inject_settlement_error(
    data,
    payment_id,
    amount_delta,
):
    settlements = data[
        "settlements"
    ]

    rows = settlements[
        settlements["payment_id"]
        == payment_id
    ]

    if rows.empty:
        return None

    index = rows.index[0]

    original = float(
        settlements.at[
            index,
            "settlement_amount",
        ]
    )

    wrong = round(
        original + amount_delta,
        2,
    )

    if wrong < 0:
        return None

    settlements.at[
        index,
        "settlement_amount",
    ] = wrong

    return make_ground_truth(
        case_id="",
        payment_id=payment_id,
        exception_type=(
            "SETTLEMENT_AMOUNT_MISMATCH"
        ),
        true_root_cause=(
            "SETTLEMENT_AMOUNT_ERROR"
        ),
        expected_behavior=(
            "INVESTIGATE_AND_RESOLVE"
        ),
    )


# =========================================================
# 2. FEE MISMATCH
# =========================================================

def inject_fee_error(
    data,
    payment_id,
    amount_delta,
):
    fees = data[
        "fees"
    ]

    rows = fees[
        fees["payment_id"]
        == payment_id
    ]

    if rows.empty:
        return None

    index = rows.index[0]

    original = float(
        fees.at[
            index,
            "fee_amount",
        ]
    )

    wrong = round(
        original + amount_delta,
        2,
    )

    if wrong < 0:
        return None

    fees.at[
        index,
        "fee_amount",
    ] = wrong

    return make_ground_truth(
        case_id="",
        payment_id=payment_id,
        exception_type="FEE_MISMATCH",
        true_root_cause=(
            "FEE_AMOUNT_ERROR"
        ),
        expected_behavior=(
            "INVESTIGATE_AND_RESOLVE"
        ),
    )


# =========================================================
# 3. REFUND MISMATCH
# =========================================================

def inject_refund_error(
    data,
    payment_id,
    amount_delta,
):
    refunds = data[
        "refunds"
    ]

    rows = refunds[
        refunds["payment_id"]
        == payment_id
    ]

    if rows.empty:
        return None

    index = rows.index[0]

    original = float(
        refunds.at[
            index,
            "refund_amount",
        ]
    )

    wrong = round(
        original + amount_delta,
        2,
    )

    if wrong < 0:
        return None

    refunds.at[
        index,
        "refund_amount",
    ] = wrong

    return make_ground_truth(
        case_id="",
        payment_id=payment_id,
        exception_type=(
            "REFUND_MISMATCH"
        ),
        true_root_cause=(
            "REFUND_AMOUNT_ERROR"
        ),
        expected_behavior=(
            "INVESTIGATE_AND_RESOLVE"
        ),
    )


# =========================================================
# 4. MISSING SETTLEMENT
# =========================================================

def inject_missing_settlement(
    data,
    payment_id,
):
    settlements = data[
        "settlements"
    ]

    rows = settlements[
        settlements["payment_id"]
        == payment_id
    ]

    if rows.empty:
        return None

    index = rows.index[0]

    settlements.drop(
        index,
        inplace=True,
    )

    return make_ground_truth(
        case_id="",
        payment_id=payment_id,
        exception_type=(
            "MISSING_SETTLEMENT"
        ),
        true_root_cause=(
            "SETTLEMENT_RECORD_MISSING"
        ),
        expected_behavior=(
            "INVESTIGATE_AND_RESOLVE"
        ),
    )


# =========================================================
# 5. MISSING LEDGER PAYMENT ENTRY
# =========================================================

def inject_missing_ledger(
    data,
    payment_id,
):
    ledger = data[
        "ledger"
    ]

    rows = ledger[
        (
            ledger["payment_id"]
            == payment_id
        )
        & (
            ledger["entry_type"]
            == "PAYMENT"
        )
    ]

    if rows.empty:
        return None

    index = rows.index[0]

    ledger.drop(
        index,
        inplace=True,
    )

    return make_ground_truth(
        case_id="",
        payment_id=payment_id,
        exception_type=(
            "MISSING_LEDGER_ENTRY"
        ),
        true_root_cause=(
            "LEDGER_RECORD_MISSING"
        ),
        expected_behavior=(
            "INVESTIGATE_AND_RESOLVE"
        ),
    )


# =========================================================
# 6. DUPLICATE PAYMENT
# =========================================================

def inject_duplicate(
    data,
    payment_id,
):
    payments = data[
        "payments"
    ]

    rows = payments[
        payments["payment_id"]
        == payment_id
    ]

    if rows.empty:
        return None

    original = (
        rows.iloc[0]
        .copy()
    )

    duplicate_id = (
        f"{payment_id}_DUP_STRESS"
    )

    original[
        "payment_id"
    ] = duplicate_id

    data["payments"] = pd.concat(
        [
            payments,
            pd.DataFrame(
                [original]
            ),
        ],
        ignore_index=True,
    )

    return make_ground_truth(
        case_id="",
        payment_id=payment_id,
        exception_type=(
            "DUPLICATE_PAYMENT"
        ),
        true_root_cause=(
            "DUPLICATE_PAYMENT_RECORD"
        ),
        expected_behavior=(
            "INVESTIGATE_AND_RESOLVE"
        ),
    )


# =========================================================
# CASE GENERATION
# =========================================================

def generate_stress_cases(
    case_count=100,
    seed=42,
):
    random.seed(seed)

    baseline = (
        load_baseline_data()
    )

    payments = baseline[
        "payments"
    ]["payment_id"].astype(str).tolist()

    fee_payment_ids = set(
        baseline["fees"][
            "payment_id"
        ].astype(str)
    )

    refund_payment_ids = set(
        baseline["refunds"][
            "payment_id"
        ].astype(str)
    )

    settlement_payment_ids = set(
        baseline["settlements"][
            "payment_id"
        ].astype(str)
    )

    ledger_payment_ids = set(
        baseline["ledger"][
            "payment_id"
        ].astype(str)
    )

    payment_ids_for_all = [
        payment_id
        for payment_id in payments
        if not payment_id.endswith("_DUP")
    ]

    scenarios = []

    scenario_types = [
        "SETTLEMENT_AMOUNT_MISMATCH",
        "FEE_MISMATCH",
        "REFUND_MISMATCH",
        "MISSING_SETTLEMENT",
        "MISSING_LEDGER_ENTRY",
        "DUPLICATE_PAYMENT",
    ]

    for index in range(
        case_count
    ):

        case_id = (
            f"S{index + 1:03d}"
        )

        for attempt in range(20):

            payment_id = random.choice(
                payment_ids_for_all
            )

            exception_type = random.choice(
                scenario_types
            )

            working = (
                create_working_copy(
                    baseline
                )
            )

            ground_truth = None

            if (
                exception_type
                == "SETTLEMENT_AMOUNT_MISMATCH"
            ):

                if payment_id not in (
                    settlement_payment_ids
                ):
                    continue

                delta = random.choice(
                    [
                        -500,
                        -250,
                        -100,
                        100,
                        250,
                        500,
                    ]
                )

                ground_truth = (
                    inject_settlement_error(
                        working,
                        payment_id,
                        delta,
                    )
                )

            elif (
                exception_type
                == "FEE_MISMATCH"
            ):

                if payment_id not in (
                    fee_payment_ids
                ):
                    continue

                delta = random.choice(
                    [
                        -100,
                        -50,
                        50,
                        100,
                        200,
                    ]
                )

                ground_truth = (
                    inject_fee_error(
                        working,
                        payment_id,
                        delta,
                    )
                )

            elif (
                exception_type
                == "REFUND_MISMATCH"
            ):

                if payment_id not in (
                    refund_payment_ids
                ):
                    continue

                delta = random.choice(
                    [
                        -250,
                        -100,
                        100,
                        250,
                    ]
                )

                ground_truth = (
                    inject_refund_error(
                        working,
                        payment_id,
                        delta,
                    )
                )

            elif (
                exception_type
                == "MISSING_SETTLEMENT"
            ):

                if payment_id not in (
                    settlement_payment_ids
                ):
                    continue

                ground_truth = (
                    inject_missing_settlement(
                        working,
                        payment_id,
                    )
                )

            elif (
                exception_type
                == "MISSING_LEDGER_ENTRY"
            ):

                if payment_id not in (
                    ledger_payment_ids
                ):
                    continue

                ground_truth = (
                    inject_missing_ledger(
                        working,
                        payment_id,
                    )
                )

            elif (
                exception_type
                == "DUPLICATE_PAYMENT"
            ):

                ground_truth = (
                    inject_duplicate(
                        working,
                        payment_id,
                    )
                )

            if ground_truth is None:
                continue

            ground_truth[
                "case_id"
            ] = case_id

            scenarios.append(
                {
                    "case_id": case_id,
                    "data": working,
                    "ground_truth": ground_truth,
                }
            )

            break

    return scenarios


# =========================================================
# SAVE BATCH
# =========================================================

def save_stress_batch(
    scenarios
):
    STRESS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    case_root = (
        STRESS_DIR / "cases"
    )

    case_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    ground_truth_rows = []

    for scenario in scenarios:

        case_id = scenario[
            "case_id"
        ]

        case_dir = (
            case_root / case_id
        )

        case_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        for name, dataframe in (
            scenario["data"].items()
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

    ground_truth_df = pd.DataFrame(
        ground_truth_rows
    )

    ground_truth_df.to_csv(
        STRESS_DIR
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
        "BUILDING STRESS TEST DATASET"
    )

    print(
        "========================================"
    )

    scenarios = (
        generate_stress_cases(
            case_count=100,
            seed=42,
        )
    )

    ground_truth_df = (
        save_stress_batch(
            scenarios
        )
    )

    print(
        f"\nGenerated cases: "
        f"{len(scenarios)}"
    )

    print(
        "\nScenario distribution:"
    )

    print(
        ground_truth_df[
            "exception_type"
        ].value_counts()
    )

    print(
        "\nGround truth:"
    )

    print(
        ground_truth_df[
            [
                "case_id",
                "payment_id",
                "exception_type",
                "true_root_cause",
                "expected_behavior",
            ]
        ].to_string(
            index=False
        )
    )

    print(
        "\nSaved to:"
    )

    print(
        STRESS_DIR
    )