from pathlib import Path

import pandas as pd

from ground_truth import create_ground_truth


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
EXCEPTIONS_DIR = DATA_DIR / "exceptions"


# ---------------------------------------------------------
# Supported exception types
# ---------------------------------------------------------

EXCEPTION_TYPES = [
    "SETTLEMENT_AMOUNT_MISMATCH",
    "MISSING_SETTLEMENT",
    "FEE_MISMATCH",
    "REFUND_MISMATCH",
    "MISSING_LEDGER_ENTRY",
    "DUPLICATE_PAYMENT",
    "CONFLICTING_EVIDENCE",
]


# ---------------------------------------------------------
# Load clean baseline data
# ---------------------------------------------------------

def load_baseline_data():

    payments_df = pd.read_csv(
        DATA_DIR / "payments.csv"
    )

    fees_df = pd.read_csv(
        DATA_DIR / "fees.csv"
    )

    refunds_df = pd.read_csv(
        DATA_DIR / "refunds.csv"
    )

    settlements_df = pd.read_csv(
        DATA_DIR / "settlements.csv"
    )

    ledger_df = pd.read_csv(
        DATA_DIR / "ledger.csv"
    )

    return {
        "payments": payments_df,
        "fees": fees_df,
        "refunds": refunds_df,
        "settlements": settlements_df,
        "ledger": ledger_df,
    }


# ---------------------------------------------------------
# Create safe working copy
# ---------------------------------------------------------

def create_working_copy(data):

    return {
        name: dataframe.copy(deep=True)
        for name, dataframe in data.items()
    }


# ---------------------------------------------------------
# Exception 1
# Settlement amount mismatch
# ---------------------------------------------------------

def inject_settlement_amount_mismatch(data):

    settlements_df = data["settlements"]

    # Use the first settlement
    index = settlements_df.index[0]

    payment_id = settlements_df.at[
        index,
        "payment_id",
    ]

    original_amount = settlements_df.at[
        index,
        "settlement_amount",
    ]

    # Deliberately reduce settlement by Rs. 500
    wrong_amount = round(
        original_amount - 500,
        2,
    )

    settlements_df.at[
        index,
        "settlement_amount",
    ] = wrong_amount

    return {
        "exception_id": "EX00001",
        "payment_id": payment_id,
        "exception_type": "SETTLEMENT_AMOUNT_MISMATCH",
        "true_root_cause": "SETTLEMENT_AMOUNT_ERROR",
        "expected_amount": original_amount,
        "actual_amount": wrong_amount,
        "difference": 500.00,
        "expected_behavior": "INVESTIGATE_AND_RESOLVE",
    }


# ---------------------------------------------------------
# Exception 2
# Missing settlement
# ---------------------------------------------------------

def inject_missing_settlement(data):

    settlements_df = data["settlements"]

    # Use the second settlement
    index = settlements_df.index[1]

    payment_id = settlements_df.at[
        index,
        "payment_id",
    ]

    original_amount = settlements_df.at[
        index,
        "settlement_amount",
    ]

    settlements_df.drop(
        index,
        inplace=True,
    )

    return {
        "exception_id": "EX00002",
        "payment_id": payment_id,
        "exception_type": "MISSING_SETTLEMENT",
        "true_root_cause": "SETTLEMENT_RECORD_MISSING",
        "expected_amount": original_amount,
        "actual_amount": None,
        "difference": None,
        "expected_behavior": "INVESTIGATE_AND_RESOLVE",
    }


# ---------------------------------------------------------
# Exception 3
# Fee mismatch
# ---------------------------------------------------------

def inject_fee_mismatch(data):

    fees_df = data["fees"]

    # Use the third fee
    index = fees_df.index[2]

    payment_id = fees_df.at[
        index,
        "payment_id",
    ]

    original_amount = fees_df.at[
        index,
        "fee_amount",
    ]

    # Deliberately increase fee by Rs. 100
    wrong_amount = round(
        original_amount + 100,
        2,
    )

    fees_df.at[
        index,
        "fee_amount",
    ] = wrong_amount

    return {
        "exception_id": "EX00003",
        "payment_id": payment_id,
        "exception_type": "FEE_MISMATCH",
        "true_root_cause": "FEE_AMOUNT_ERROR",
        "expected_amount": original_amount,
        "actual_amount": wrong_amount,
        "difference": 100.00,
        "expected_behavior": "INVESTIGATE_AND_RESOLVE",
    }


# ---------------------------------------------------------
# Exception 4
# Refund mismatch
# ---------------------------------------------------------
def inject_refund_mismatch(data):

    refunds_df = data["refunds"]

    payment_id = "PAY00004"

    refund_rows = refunds_df[
        refunds_df["payment_id"] == payment_id
    ]

    if refund_rows.empty:
        raise ValueError(
            "PAY00004 does not have a refund."
        )

    index = refund_rows.index[0]

    original_amount = refunds_df.at[
        index,
        "refund_amount",
    ]

    wrong_amount = round(
        original_amount + 250,
        2,
    )

    refunds_df.at[
        index,
        "refund_amount",
    ] = wrong_amount

    return {
        "exception_id": "EX00004",
        "payment_id": payment_id,
        "exception_type": "REFUND_MISMATCH",
        "true_root_cause": "REFUND_AMOUNT_ERROR",
        "expected_amount": original_amount,
        "actual_amount": wrong_amount,
        "difference": 250.00,
        "expected_behavior": "INVESTIGATE_AND_RESOLVE",
    }

# ---------------------------------------------------------
# Exception 5
# Missing ledger entry
# ---------------------------------------------------------

def inject_missing_ledger_entry(data):

    ledger_df = data["ledger"]

    # Use a ledger entry that belongs to PAY00005.
    target_rows = ledger_df[
        ledger_df["payment_id"] == "PAY00005"
    ]

    if target_rows.empty:
        raise ValueError(
            "PAY00005 does not exist in ledger."
        )

    index = target_rows.index[0]

    payment_id = ledger_df.at[
        index,
        "payment_id",
    ]

    entry_type = ledger_df.at[
        index,
        "entry_type",
    ]

    ledger_df.drop(
        index,
        inplace=True,
    )

    return {
        "exception_id": "EX00005",
        "payment_id": payment_id,
        "exception_type": "MISSING_LEDGER_ENTRY",
        "true_root_cause": "LEDGER_RECORD_MISSING",
        "expected_amount": None,
        "actual_amount": None,
        "difference": None,
        "expected_behavior": "INVESTIGATE_AND_RESOLVE",
        "missing_entry_type": entry_type,
    }


# ---------------------------------------------------------
# Exception 6
# Duplicate payment
# ---------------------------------------------------------

def inject_duplicate_payment(data):

    payments_df = data["payments"]

    # Use PAY00006
    target_rows = payments_df[
        payments_df["payment_id"] == "PAY00006"
    ]

    if target_rows.empty:
        raise ValueError(
            "PAY00006 does not exist."
        )

    original_payment = (
        target_rows.iloc[0].copy()
    )

    original_payment_id = (
        original_payment["payment_id"]
    )

    duplicate_payment_id = (
        f"{original_payment_id}_DUP"
    )

    # Keep order, customer, amount and timestamp
    # exactly the same.
    original_payment["payment_id"] = (
        duplicate_payment_id
    )

    data["payments"] = pd.concat(
        [
            payments_df,
            pd.DataFrame([original_payment]),
        ],
        ignore_index=True,
    )

    return {
        "exception_id": "EX00006",
        "payment_id": original_payment_id,
        "exception_type": "DUPLICATE_PAYMENT",
        "true_root_cause": "DUPLICATE_PAYMENT_RECORD",
        "expected_amount": None,
        "actual_amount": None,
        "difference": None,
        "expected_behavior": "INVESTIGATE_AND_RESOLVE",
        "duplicate_payment_id": duplicate_payment_id,
    }


# ---------------------------------------------------------
# Exception 7
# Conflicting evidence
# ---------------------------------------------------------

def inject_conflicting_evidence(data):

    payments_df = data["payments"]
    fees_df = data["fees"]
    refunds_df = data["refunds"]
    settlements_df = data["settlements"]

    # Use PAY00007
    target_rows = payments_df[
        payments_df["payment_id"] == "PAY00007"
    ]

    if target_rows.empty:
        raise ValueError(
            "PAY00007 does not exist."
        )

    payment = target_rows.iloc[0]

    payment_id = payment["payment_id"]

    # Find original fee
    fee_rows = fees_df[
        fees_df["payment_id"] == payment_id
    ]

    if fee_rows.empty:
        raise ValueError(
            "PAY00007 does not have a fee."
        )

    original_fee = fee_rows.iloc[0]["fee_amount"]

    conflict_amount = 500.00

    # ---------------------------------------------
    # Candidate explanation 1: additional fee
    # ---------------------------------------------

    new_fee = {
        "fee_id": "FEE_CONFLICT_01",
        "payment_id": payment_id,
        "fee_amount": conflict_amount,
        "fee_type": "ADDITIONAL_FEE",
        "created_at": payment["created_at"],
    }

    data["fees"] = pd.concat(
        [
            fees_df,
            pd.DataFrame([new_fee]),
        ],
        ignore_index=True,
    )

    # ---------------------------------------------
    # Candidate explanation 2: refund
    # ---------------------------------------------

    new_refund = {
        "refund_id": "REF_CONFLICT_01",
        "payment_id": payment_id,
        "refund_amount": conflict_amount,
        "refund_date": (
            pd.Timestamp(
                payment["created_at"]
            )
            + pd.Timedelta(days=1)
        ),
        "status": "PROCESSED",
    }

    data["refunds"] = pd.concat(
        [
            refunds_df,
            pd.DataFrame([new_refund]),
        ],
        ignore_index=True,
    )

    # ---------------------------------------------
    # Create a settlement that is Rs. 500 lower
    # than the original expected amount.
    #
    # This means:
    #
    # Extra fee of Rs. 500 could explain it.
    # OR
    # Refund of Rs. 500 could explain it.
    #
    # Both are possible explanations.
    # ---------------------------------------------

    expected_without_conflict = (
        payment["amount"]
        - original_fee
    )

    conflicted_settlement = round(
        expected_without_conflict
        - conflict_amount,
        2,
    )

    settlement_rows = settlements_df[
        settlements_df["payment_id"] == payment_id
    ]

    if settlement_rows.empty:
        raise ValueError(
            "PAY00007 does not have a settlement."
        )

    settlement_index = settlement_rows.index[0]

    data["settlements"].at[
        settlement_index,
        "settlement_amount",
    ] = conflicted_settlement

    return {
        "exception_id": "EX00007",
        "payment_id": payment_id,
        "exception_type": "CONFLICTING_EVIDENCE",
        "true_root_cause": "INSUFFICIENT_EVIDENCE",
        "expected_amount": expected_without_conflict,
        "actual_amount": conflicted_settlement,
        "difference": conflict_amount,
        "expected_behavior": "HUMAN_REVIEW",
    }


# ---------------------------------------------------------
# Build complete exception batch
# ---------------------------------------------------------

def build_exception_batch(baseline_data):

    # Start from a clean copy
    data = create_working_copy(
        baseline_data
    )

    ground_truth_records = []

    # ---------------------------------------------
    # EX00001
    # ---------------------------------------------

    exception = (
        inject_settlement_amount_mismatch(
            data
        )
    )

    ground_truth_records.append(
        exception
    )

    # ---------------------------------------------
    # EX00002
    # ---------------------------------------------

    exception = (
        inject_missing_settlement(
            data
        )
    )

    ground_truth_records.append(
        exception
    )

    # ---------------------------------------------
    # EX00003
    # ---------------------------------------------

    exception = inject_fee_mismatch(
        data
    )

    ground_truth_records.append(
        exception
    )

    # ---------------------------------------------
    # EX00004
    # ---------------------------------------------
    exception = inject_refund_mismatch(
    data
    )
    ground_truth_records.append(
        exception
    )

    # ---------------------------------------------
    # EX00005
    # ---------------------------------------------

    exception = (
        inject_missing_ledger_entry(
            data
        )
    )

    ground_truth_records.append(
        exception
    )

    # ---------------------------------------------
    # EX00006
    # ---------------------------------------------

    exception = inject_duplicate_payment(
        data
    )

    ground_truth_records.append(
        exception
    )

    # ---------------------------------------------
    # EX00007
    # ---------------------------------------------

    # PAY00007 is intentionally reserved
    # for the conflicting-evidence scenario.
    # -------------------------------------------------



    # Exception 7: Conflicting Evidence
    # Target: PAY00007
    # -------------------------------------------------

    exception = inject_conflicting_evidence(
        data
    )

    ground_truth_records.append(
        exception
    )

    # ---------------------------------------------
    # Convert ground truth records into DataFrame
    # ---------------------------------------------

    ground_truth_df = create_ground_truth(
        ground_truth_records
    )

    return (
        data,
        ground_truth_df,
    )


# ---------------------------------------------------------
# Save exception datasets
# ---------------------------------------------------------

def save_exception_data(data):

    EXCEPTIONS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for name, dataframe in data.items():

        output_path = (
            EXCEPTIONS_DIR
            / f"{name}.csv"
        )

        dataframe.to_csv(
            output_path,
            index=False,
        )

        print(
            f"Saved broken data: {output_path}"
        )


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

if __name__ == "__main__":

    print(
        "\n========================================"
    )
    print(
        "BUILDING EXCEPTION DATASET"
    )
    print(
        "========================================"
    )

    # Load healthy baseline
    baseline_data = load_baseline_data()

    # Build all seven exceptions
    exception_data, ground_truth_df = (
        build_exception_batch(
            baseline_data
        )
    )

    # Show record counts
    print(
        f"\nPayments    : "
        f"{len(exception_data['payments'])}"
    )

    print(
        f"Fees        : "
        f"{len(exception_data['fees'])}"
    )

    print(
        f"Refunds     : "
        f"{len(exception_data['refunds'])}"
    )

    print(
        f"Settlements : "
        f"{len(exception_data['settlements'])}"
    )

    print(
        f"Ledger      : "
        f"{len(exception_data['ledger'])}"
    )

    # ---------------------------------------------
    # Ground truth
    # ---------------------------------------------

    print("\n--- Ground Truth ---")

    print(
        ground_truth_df.to_string(
            index=False
        )
    )

    # ---------------------------------------------
    # Save broken dataset
    # ---------------------------------------------

    print(
        "\n--- Saving Exception Dataset ---"
    )

    save_exception_data(
        exception_data
    )

    # ---------------------------------------------
    # Save ground truth
    # ---------------------------------------------

    ground_truth_path = (
        DATA_DIR / "ground_truth.csv"
    )

    ground_truth_df.to_csv(
        ground_truth_path,
        index=False,
    )

    print(
        f"\nGround truth saved to:"
        f"\n{ground_truth_path}"
    )

    print(
        "\n✅ Exception dataset created successfully."
    )