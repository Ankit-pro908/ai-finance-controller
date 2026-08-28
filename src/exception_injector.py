from pathlib import Path
from ground_truth import create_ground_truth
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
EXCEPTIONS_DIR = DATA_DIR / "exceptions"

EXCEPTION_TYPES = [
    "SETTLEMENT_AMOUNT_MISMATCH",
    "MISSING_SETTLEMENT",
    "FEE_MISMATCH",
    "REFUND_MISMATCH",
    "MISSING_LEDGER_ENTRY",
    "DUPLICATE_PAYMENT",
    "CONFLICTING_EVIDENCE",
]

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

def create_working_copy(data):
    return {
        name: dataframe.copy(deep=True)
        for name, dataframe in data.items()
    }

def inject_settlement_amount_mismatch(data):
    settlements_df = data["settlements"]

    # Select the first settlement
    index = settlements_df.index[0]

    original_amount = settlements_df.at[
        index,
        "settlement_amount",
    ]

    # Deliberately reduce the settlement by ₹500
    wrong_amount = round(
        original_amount - 500,
        2,
    )

    # Modify only the working copy
    settlements_df.at[
        index,
        "settlement_amount",
    ] = wrong_amount

    return {
        "payment_id": settlements_df.at[
            index,
            "payment_id",
        ],
        "original_amount": original_amount,
        "wrong_amount": wrong_amount,
    }

def inject_missing_settlement(data):

    settlements_df = data["settlements"]

    # Select the second settlement
    index = settlements_df.index[1]

    payment_id = settlements_df.at[
        index,
        "payment_id",
    ]

    # Remove the settlement from the working copy
    settlements_df.drop(
        index,
        inplace=True,
    )

    return {
        "payment_id": payment_id,
        "exception_type": "MISSING_SETTLEMENT",
        "true_root_cause": "SETTLEMENT_RECORD_MISSING",
    }

def inject_fee_mismatch(data):
    fees_df = data["fees"]

    # Select the third fee
    index = fees_df.index[2]

    payment_id = fees_df.at[
        index,
        "payment_id",
    ]

    original_amount = fees_df.at[
        index,
        "fee_amount",
    ]

    wrong_amount = round(
        original_amount + 100,
        2,
    )

    fees_df.at[
        index,
        "fee_amount",
    ] = wrong_amount

    return {
        "payment_id": payment_id,
        "exception_type": "FEE_MISMATCH",
        "true_root_cause": "FEE_AMOUNT_ERROR",
        "original_amount": original_amount,
        "wrong_amount": wrong_amount,
    }


def inject_refund_mismatch(data):
    refunds_df = data["refunds"]

    if refunds_df.empty:
        raise ValueError(
            "Cannot inject refund mismatch: "
            "no refunds exist."
        )

    # Select the first refund
    index = refunds_df.index[0]

    payment_id = refunds_df.at[
        index,
        "payment_id",
    ]

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
        "payment_id": payment_id,
        "exception_type": "REFUND_MISMATCH",
        "true_root_cause": "REFUND_AMOUNT_ERROR",
        "original_amount": original_amount,
        "wrong_amount": wrong_amount,
    }

def inject_missing_ledger_entry(data):
    ledger_df = data["ledger"]

    # Select the first ledger entry
    index = ledger_df.index[0]

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
        "payment_id": payment_id,
        "exception_type": "MISSING_LEDGER_ENTRY",
        "true_root_cause": "LEDGER_RECORD_MISSING",
        "missing_entry_type": entry_type,
    }

def inject_duplicate_payment(data):
    payments_df = data["payments"]

    # Take the first payment
    duplicate_row = payments_df.iloc[0].copy()

    original_payment_id = duplicate_row["payment_id"]

    # Give the duplicate a new ID, but keep the same
    # order, customer, amount, and timestamp.
    duplicate_row["payment_id"] = (
        f"{original_payment_id}_DUP"
    )

    data["payments"] = pd.concat(
        [
            payments_df,
            pd.DataFrame([duplicate_row]),
        ],
        ignore_index=True,
    )

    return {
        "payment_id": original_payment_id,
        "duplicate_payment_id": duplicate_row["payment_id"],
        "exception_type": "DUPLICATE_PAYMENT",
        "true_root_cause": "DUPLICATE_PAYMENT_RECORD",
    }

def inject_conflicting_evidence(data):

    payments_df = data["payments"]
    fees_df = data["fees"]
    refunds_df = data["refunds"]

    # Pick the first payment
    payment = payments_df.iloc[0]

    payment_id = payment["payment_id"]

    # Use a fixed conflict amount
    conflict_amount = 500.00

    # Add a fee of ₹500
    new_fee = {
        "fee_id": "FEE_CONFLICT_01",
        "payment_id": payment_id,
        "fee_amount": conflict_amount,
        "fee_type": "PROCESSING_FEE",
        "created_at": payment["created_at"],
    }

    data["fees"] = pd.concat(
        [
            fees_df,
            pd.DataFrame([new_fee]),
        ],
        ignore_index=True,
    )

    # Add a refund of ₹500
    new_refund = {
        "refund_id": "REF_CONFLICT_01",
        "payment_id": payment_id,
        "refund_amount": conflict_amount,
        "refund_date": pd.Timestamp(
            payment["created_at"]
        ) + pd.Timedelta(days=1),
        "status": "PROCESSED",
    }

    data["refunds"] = pd.concat(
        [
            refunds_df,
            pd.DataFrame([new_refund]),
        ],
        ignore_index=True,
    )

    return {
        "payment_id": payment_id,
        "exception_type": "CONFLICTING_EVIDENCE",
        "true_root_cause": "INSUFFICIENT_EVIDENCE",
        "conflict_amount": conflict_amount,
    }

def build_exception_batch(baseline_data):
    """
    Create one controlled dataset containing all
    seven exception scenarios.
    """

    data = create_working_copy(
        baseline_data
    )

    ground_truth = []

    # -------------------------------------------------
    # Exception 1: Settlement Amount Mismatch
    # -------------------------------------------------

    index = 0

    original_amount = data["settlements"].at[
        index,
        "settlement_amount",
    ]

    wrong_amount = round(
        original_amount - 500,
        2,
    )

    data["settlements"].at[
        index,
        "settlement_amount",
    ] = wrong_amount

    payment_id = data["settlements"].at[
        index,
        "payment_id",
    ]

    ground_truth.append(
        {
            "exception_id": "EX00001",
            "payment_id": payment_id,
            "exception_type": "SETTLEMENT_AMOUNT_MISMATCH",
            "true_root_cause": "SETTLEMENT_AMOUNT_ERROR",
            "expected_amount": original_amount,
            "actual_amount": wrong_amount,
            "difference": 500.00,
            "expected_behavior": "INVESTIGATE_AND_RESOLVE",
        }
    )

    # -------------------------------------------------
    # Exception 2: Missing Settlement
    # -------------------------------------------------

    index = 1

    payment_id = data["settlements"].at[
        index,
        "payment_id",
    ]

    original_amount = data["settlements"].at[
        index,
        "settlement_amount",
    ]

    data["settlements"].drop(
        index,
        inplace=True,
    )

    ground_truth.append(
        {
            "exception_id": "EX00002",
            "payment_id": payment_id,
            "exception_type": "MISSING_SETTLEMENT",
            "true_root_cause": "SETTLEMENT_RECORD_MISSING",
            "expected_amount": original_amount,
            "actual_amount": None,
            "difference": None,
            "expected_behavior": "INVESTIGATE_AND_RESOLVE",
        }
    )

    # -------------------------------------------------
    # Exception 3: Fee Mismatch
    # -------------------------------------------------

    index = 2

    payment_id = data["fees"].at[
        index,
        "payment_id",
    ]

    original_amount = data["fees"].at[
        index,
        "fee_amount",
    ]

    wrong_amount = round(
        original_amount + 100,
        2,
    )

    data["fees"].at[
        index,
        "fee_amount",
    ] = wrong_amount

    ground_truth.append(
        {
            "exception_id": "EX00003",
            "payment_id": payment_id,
            "exception_type": "FEE_MISMATCH",
            "true_root_cause": "FEE_AMOUNT_ERROR",
            "expected_amount": original_amount,
            "actual_amount": wrong_amount,
            "difference": 100.00,
            "expected_behavior": "INVESTIGATE_AND_RESOLVE",
        }
    )

    # -------------------------------------------------
    # Exception 4: Refund Mismatch
    # -------------------------------------------------

    if data["refunds"].empty:
        raise ValueError(
            "No refund exists in baseline data. "
            "Regenerate baseline data and run again."
        )

    index = data["refunds"].index[0]

    payment_id = data["refunds"].at[
        index,
        "payment_id",
    ]

    original_amount = data["refunds"].at[
        index,
        "refund_amount",
    ]

    wrong_amount = round(
        original_amount + 250,
        2,
    )

    data["refunds"].at[
        index,
        "refund_amount",
    ] = wrong_amount

    ground_truth.append(
        {
            "exception_id": "EX00004",
            "payment_id": payment_id,
            "exception_type": "REFUND_MISMATCH",
            "true_root_cause": "REFUND_AMOUNT_ERROR",
            "expected_amount": original_amount,
            "actual_amount": wrong_amount,
            "difference": 250.00,
            "expected_behavior": "INVESTIGATE_AND_RESOLVE",
        }
    )

    # -------------------------------------------------
    # Exception 5: Missing Ledger Entry
    # -------------------------------------------------

    index = 8

    payment_id = data["ledger"].at[
        index,
        "payment_id",
    ]

    entry_type = data["ledger"].at[
        index,
        "entry_type",
    ]

    data["ledger"].drop(
        index,
        inplace=True,
    )

    ground_truth.append(
        {
            "exception_id": "EX00005",
            "payment_id": payment_id,
            "exception_type": "MISSING_LEDGER_ENTRY",
            "true_root_cause": "LEDGER_RECORD_MISSING",
            "expected_amount": None,
            "actual_amount": None,
            "difference": None,
            "expected_behavior": "INVESTIGATE_AND_RESOLVE",
        }
    )

    # -------------------------------------------------
    # Exception 6: Duplicate Payment
    # -------------------------------------------------

    index = 5

    original_payment = (
        data["payments"]
        .iloc[index]
        .copy()
    )

    original_payment_id = original_payment[
        "payment_id"
    ]

    duplicate_payment_id = (
        f"{original_payment_id}_DUP"
    )

    original_payment["payment_id"] = (
        duplicate_payment_id
    )

    data["payments"] = pd.concat(
        [
            data["payments"],
            pd.DataFrame([original_payment]),
        ],
        ignore_index=True,
    )

    ground_truth.append(
        {
            "exception_id": "EX00006",
            "payment_id": original_payment_id,
            "exception_type": "DUPLICATE_PAYMENT",
            "true_root_cause": "DUPLICATE_PAYMENT_RECORD",
            "expected_amount": None,
            "actual_amount": None,
            "difference": None,
            "expected_behavior": "INVESTIGATE_AND_RESOLVE",
        }
    )

    # -------------------------------------------------
    # Exception 7: Conflicting Evidence
    # -------------------------------------------------

    index = 6

    payment_id = data["payments"].at[
        index,
        "payment_id",
    ]

    conflict_amount = 500.00

    new_fee = {
        "fee_id": "FEE_CONFLICT_01",
        "payment_id": payment_id,
        "fee_amount": conflict_amount,
        "fee_type": "PROCESSING_FEE",
        "created_at": data["payments"].at[
            index,
            "created_at",
        ],
    }

    data["fees"] = pd.concat(
        [
            data["fees"],
            pd.DataFrame([new_fee]),
        ],
        ignore_index=True,
    )

    new_refund = {
        "refund_id": "REF_CONFLICT_01",
        "payment_id": payment_id,
        "refund_amount": conflict_amount,
        "refund_date": pd.Timestamp(
            data["payments"].at[
                index,
                "created_at",
            ]
        ) + pd.Timedelta(days=1),
        "status": "PROCESSED",
    }

    data["refunds"] = pd.concat(
        [
            data["refunds"],
            pd.DataFrame([new_refund]),
        ],
        ignore_index=True,
    )

    ground_truth.append(
        {
            "exception_id": "EX00007",
            "payment_id": payment_id,
            "exception_type": "CONFLICTING_EVIDENCE",
            "true_root_cause": "INSUFFICIENT_EVIDENCE",
            "expected_amount": conflict_amount,
            "actual_amount": conflict_amount,
            "difference": 0.00,
            "expected_behavior": "HUMAN_REVIEW",
        }
    )

    return (
        data,
        pd.DataFrame(ground_truth),
    )

def save_exception_data(data):

    EXCEPTIONS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for name, dataframe in data.items():

        output_path = (
            EXCEPTIONS_DIR / f"{name}.csv"
        )

        dataframe.to_csv(
            output_path,
            index=False,
        )

        print(
            f"Saved broken data: {output_path}"
        )

if __name__ == "__main__":

    print("\n========================================")
    print("BUILDING EXCEPTION DATASET")
    print("========================================")

    # Load healthy baseline
    baseline_data = load_baseline_data()

    # Create all 7 controlled exceptions
    exception_data, ground_truth_df = (
        build_exception_batch(
            baseline_data
        )
    )

    print(
        f"\nPayments: "
        f"{len(exception_data['payments'])}"
    )

    print(
        f"Fees: "
        f"{len(exception_data['fees'])}"
    )

    print(
        f"Refunds: "
        f"{len(exception_data['refunds'])}"
    )

    print(
        f"Settlements: "
        f"{len(exception_data['settlements'])}"
    )

    print(
        f"Ledger: "
        f"{len(exception_data['ledger'])}"
    )

    print("\n--- Ground Truth ---")
    print(ground_truth_df)

    # Create output directory
    EXCEPTIONS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Save broken datasets
    save_exception_data(
        exception_data
    )

    # Save ground truth
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
        "\n✅ Day 2 exception dataset created."
    )