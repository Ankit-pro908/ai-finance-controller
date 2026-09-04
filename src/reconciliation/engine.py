from pathlib import Path

import pandas as pd
try:
    from .evaluator import evaluate_detection
except ImportError:
    from evaluator import evaluate_detection


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

EXCEPTION_DATA_DIR = (
    PROJECT_ROOT / "data" / "exceptions"
)


def load_exception_data():

    payments_df = pd.read_csv(
        EXCEPTION_DATA_DIR / "payments.csv"
    )

    fees_df = pd.read_csv(
        EXCEPTION_DATA_DIR / "fees.csv"
    )

    refunds_df = pd.read_csv(
        EXCEPTION_DATA_DIR / "refunds.csv"
    )

    settlements_df = pd.read_csv(
        EXCEPTION_DATA_DIR / "settlements.csv"
    )

    ledger_df = pd.read_csv(
        EXCEPTION_DATA_DIR / "ledger.csv"
    )

    return {
        "payments": payments_df,
        "fees": fees_df,
        "refunds": refunds_df,
        "settlements": settlements_df,
        "ledger": ledger_df,
    }

def build_payment_view(data):

    payments_df = data["payments"]
    fees_df = data["fees"]
    refunds_df = data["refunds"]
    settlements_df = data["settlements"]

    payment_view = payments_df.copy()

    # Total fee per payment
    fee_totals = (
        fees_df.groupby("payment_id")["fee_amount"]
        .sum()
        .rename("total_fee")
    )

    # Total refund per payment
    refund_totals = (
        refunds_df.groupby("payment_id")["refund_amount"]
        .sum()
        .rename("total_refund")
    )

    # Settlement per payment
    settlement_values = (
        settlements_df.groupby("payment_id")[
            "settlement_amount"
        ]
        .sum()
        .rename("actual_settlement")
    )

    # Attach everything to the payment
    payment_view = payment_view.merge(
        fee_totals,
        on="payment_id",
        how="left",
    )

    payment_view = payment_view.merge(
        refund_totals,
        on="payment_id",
        how="left",
    )

    payment_view = payment_view.merge(
        settlement_values,
        on="payment_id",
        how="left",
    )

    # Payments with no fee/refund get zero
    payment_view["total_fee"] = (
        payment_view["total_fee"]
        .fillna(0)
    )

    payment_view["total_refund"] = (
        payment_view["total_refund"]
        .fillna(0)
    )

    return payment_view

def calculate_expected_settlement(
    payment_view: pd.DataFrame,
) -> pd.DataFrame:

    payment_view = payment_view.copy()

    payment_view["expected_settlement"] = (
        payment_view["amount"]
        - payment_view["total_fee"]
        - payment_view["total_refund"]
    )

    payment_view["difference"] = (
        payment_view["expected_settlement"]
        - payment_view["actual_settlement"]
    )

    return payment_view

def classify_reconciliation(
    payment_view: pd.DataFrame,
) -> pd.DataFrame:

    payment_view = payment_view.copy()

    # Remove tiny floating-point errors.
    payment_view["difference"] = (
        payment_view["difference"]
        .round(2)
    )

    # Default classification
    payment_view["reconciliation_status"] = "MATCH"

    # Missing settlement
    missing_settlement = (
        payment_view["actual_settlement"].isna()
    )

    # Actual amount does not match expected amount
    amount_mismatch = (
        payment_view["difference"].abs() > 0.01
    )

    payment_view.loc[
        missing_settlement | amount_mismatch,
        "reconciliation_status",
    ] = "EXCEPTION"

    return payment_view

def identify_exception_reason(
    data,
    payment_view: pd.DataFrame,
) -> pd.DataFrame:

    payment_view = payment_view.copy()

    payments_df = data["payments"]
    fees_df = data["fees"]
    refunds_df = data["refunds"]
    ledger_df = data["ledger"]

    reasons = []
    statuses = []

    for _, row in payment_view.iterrows():

        payment_id = row["payment_id"]

        payment_amount = row["amount"]
        order_id = row["order_id"]
        customer_id = row["customer_id"]

        difference = round(
            abs(row["difference"]),
            2,
        )

        # -------------------------------------------------
        # 1. Duplicate payment
        # -------------------------------------------------

        duplicate_candidates = payments_df[
            (
                payments_df["order_id"]
                == order_id
            )
            &
            (
                payments_df["customer_id"]
                == customer_id
            )
            &
            (
                payments_df["amount"]
                == payment_amount
            )
        ]

        if len(duplicate_candidates) > 1:

            reasons.append(
                "DUPLICATE_PAYMENT"
            )

            statuses.append(
                "EXCEPTION"
            )

            continue

        # -------------------------------------------------
        # 2. Missing settlement
        # -------------------------------------------------

        if pd.isna(row["actual_settlement"]):

            reasons.append(
                "MISSING_SETTLEMENT"
            )

            statuses.append(
                "EXCEPTION"
            )

            continue

        # -------------------------------------------------
        # 3. No difference means matched
        # -------------------------------------------------

        if difference <= 0.01:

            reasons.append(
                "NONE"
            )

            statuses.append(
                "MATCH"
            )

            continue

        # -------------------------------------------------
        # 4. Source-to-ledger consistency
        #
        # Only use this as a deterministic discriminator
        # when both sides of the relationship actually exist.
        #
        # This allows:
        #
        #     source amount != ledger amount
        #
        # to identify a specific upstream mismatch without
        # treating a missing ledger record as automatically
        # equivalent to an amount mismatch.
        # -------------------------------------------------

        ledger_rows = ledger_df[
            ledger_df["payment_id"].astype(str)
            == str(payment_id)
        ]

        fee_rows = fees_df[
            fees_df["payment_id"].astype(str)
            == str(payment_id)
        ]

        refund_rows = refunds_df[
            refunds_df["payment_id"].astype(str)
            == str(payment_id)
        ]

        # -------------------------------------------------
        # Fee source ↔ ledger FEE
        # -------------------------------------------------

        fee_consistent = None

        ledger_fee_rows = ledger_rows[
            ledger_rows[
                "entry_type"
            ]
            .astype(str)
            .str.upper()
            == "FEE"
        ]

        if (
            not fee_rows.empty
            and not ledger_fee_rows.empty
        ):

            source_fee = round(
                fee_rows[
                    "fee_amount"
                ].sum(),
                2,
            )

            ledger_fee = round(
                ledger_fee_rows[
                    "amount"
                ].sum(),
                2,
            )

            fee_consistent = (
                abs(
                    abs(source_fee)
                    - abs(ledger_fee)
                )
                <= 0.01
            )

        # -------------------------------------------------
        # Refund source ↔ ledger REFUND
        # -------------------------------------------------

        refund_consistent = None

        ledger_refund_rows = ledger_rows[
            ledger_rows[
                "entry_type"
            ]
            .astype(str)
            .str.upper()
            == "REFUND"
        ]

        if (
            not refund_rows.empty
            and not ledger_refund_rows.empty
        ):

            source_refund = round(
                refund_rows[
                    "refund_amount"
                ].sum(),
                2,
            )

            ledger_refund = round(
                ledger_refund_rows[
                    "amount"
                ].sum(),
                2,
            )

            # Ledger refunds are stored as negative values.
            refund_consistent = (
                abs(
                    abs(source_refund)
                    - abs(ledger_refund)
                )
                <= 0.01
            )

        # -------------------------------------------------
        # One clear source-to-ledger mismatch
        #
        # Only classify it when the other relevant
        # relationship is actually present and consistent.
        # -------------------------------------------------

        if (
            fee_consistent == False
            and refund_consistent == True
        ):

            reasons.append(
                "FEE_MISMATCH"
            )

            statuses.append(
                "EXCEPTION"
            )

            continue

        if (
            fee_consistent == True
            and refund_consistent == False
        ):

            reasons.append(
                "REFUND_MISMATCH"
            )

            statuses.append(
                "EXCEPTION"
            )

            continue

        # -------------------------------------------------
        # 5. Existing discrepancy-based explanation logic
        #
        # Used when:
        #
        # - both upstream relationships are consistent,
        # - one or both relationships are unavailable,
        # - or the evidence remains genuinely ambiguous.
        # -------------------------------------------------

        fee_explanation = False
        refund_explanation = False

        # -------------------------------------------------
        # Candidate A: extra fee explains difference
        # -------------------------------------------------

        expected_fee = round(
            payment_amount * 0.02,
            2,
        )

        actual_fee = round(
            fee_rows[
                "fee_amount"
            ].sum(),
            2,
        ) if not fee_rows.empty else 0.0

        extra_fee = round(
            actual_fee
            - expected_fee,
            2,
        )

        if abs(
            extra_fee
            - difference
        ) <= 0.01:

            fee_explanation = True

        # -------------------------------------------------
        # Candidate B: refund explains difference
        # -------------------------------------------------

        total_refund = round(
            refund_rows[
                "refund_amount"
            ].sum(),
            2,
        ) if not refund_rows.empty else 0.0

        if abs(
            total_refund
            - difference
        ) <= 0.01:

            refund_explanation = True

        # -------------------------------------------------
        # Both explanations fit
        # -------------------------------------------------

        if (
            fee_explanation
            and refund_explanation
        ):

            reasons.append(
                "CONFLICTING_EVIDENCE"
            )

            statuses.append(
                "EXCEPTION"
            )

            continue

        # -------------------------------------------------
        # Fee explanation only
        # -------------------------------------------------

        if fee_explanation:

            reasons.append(
                "FEE_MISMATCH"
            )

            statuses.append(
                "EXCEPTION"
            )

            continue

        # -------------------------------------------------
        # Refund explanation only
        # -------------------------------------------------

        if refund_explanation:

            reasons.append(
                "REFUND_RELATED_MISMATCH"
            )

            statuses.append(
                "EXCEPTION"
            )

            continue

        # -------------------------------------------------
        # Generic settlement mismatch
        # -------------------------------------------------

        reasons.append(
            "SETTLEMENT_AMOUNT_MISMATCH"
        )

        statuses.append(
            "EXCEPTION"
        )

    payment_view[
        "exception_reason"
    ] = reasons

    payment_view[
        "reconciliation_status"
    ] = statuses

    return payment_view

def validate_ledger(
    data,
    payment_view: pd.DataFrame,
) -> pd.DataFrame:

    payment_view = payment_view.copy()

    ledger_df = data["ledger"]

    ledger_nets = (
        ledger_df.groupby("payment_id")["amount"]
        .sum()
        .rename("ledger_net")
    )

    payment_view = payment_view.merge(
        ledger_nets,
        on="payment_id",
        how="left",
    )

    payment_view["ledger_difference"] = (
        payment_view["ledger_net"]
        - payment_view["actual_settlement"]
    )

    payment_view["ledger_difference"] = (
        payment_view["ledger_difference"].round(2)
    )

    payment_view["ledger_status"] = "MATCH"

    missing_ledger = (
        payment_view["ledger_net"].isna()
    )

    ledger_mismatch = (
        payment_view["ledger_difference"]
        .abs()
        > 0.01
    )

    payment_view.loc[
        missing_ledger | ledger_mismatch,
        "ledger_status",
    ] = "EXCEPTION"

    return payment_view

def build_exception_report(
    payment_view: pd.DataFrame,
) -> pd.DataFrame:

    payment_view = payment_view.copy()

    # Any financial or ledger inconsistency
    # means the overall record is an exception.
    payment_view["final_status"] = "MATCH"

    exception_condition = (
        (
            payment_view["reconciliation_status"]
            == "EXCEPTION"
        )
        |
        (
            payment_view["ledger_status"]
            == "EXCEPTION"
        )
    )

    payment_view.loc[
        exception_condition,
        "final_status",
    ] = "EXCEPTION"

    # -----------------------------------------------------
    # Explicitly classify missing-ledger-entry cases.
    #
    # This is only used when the reconciliation itself did
    # not identify a more specific exception reason.
    # -----------------------------------------------------

    missing_ledger_reason = (
        (
            payment_view[
                "ledger_status"
            ]
            == "EXCEPTION"
        )
        &
        (
            payment_view[
                "exception_reason"
            ]
            == "NONE"
        )
    )

    payment_view.loc[
        missing_ledger_reason,
        "exception_reason",
    ] = "MISSING_LEDGER_ENTRY"

    return payment_view


def print_reconciliation_summary(
    payment_view: pd.DataFrame,
) -> None:

    total_records = len(payment_view)

    matched_records = (
        payment_view[
            "reconciliation_status"
        ] == "MATCH"
    ).sum()

    exception_records = (
        payment_view[
            "reconciliation_status"
        ] == "EXCEPTION"
    ).sum()

    match_rate = (
        matched_records / total_records * 100
        if total_records > 0
        else 0
    )

    print("\n--- Reconciliation Summary ---")

    print(
        f"Total Records : {total_records}"
    )

    print(
        f"Matched       : {matched_records}"
    )

    print(
        f"Exceptions    : {exception_records}"
    )

    print(
        f"Match Rate    : {match_rate:.2f}%"
    )

    print("\nException Breakdown:")

    print(
        payment_view[
            payment_view[
                "reconciliation_status"
            ] == "EXCEPTION"
        ][
            "exception_reason"
        ].value_counts()
    )

if __name__ == "__main__":

    data = load_exception_data()

    payment_view = build_payment_view(
        data
    )

    payment_view = calculate_expected_settlement(
        payment_view
    )

    payment_view = classify_reconciliation(
        payment_view
    )

    payment_view = identify_exception_reason(
        data,
        payment_view
    )

    payment_view = validate_ledger(
        data,
        payment_view,
    )
    payment_view = build_exception_report(
        payment_view,
    )

    print("\n--- Payment Reconciliation View ---")

    print(
        payment_view[
            [
                "payment_id",
                "amount",
                "total_fee",
                "total_refund",
                "expected_settlement",
                "actual_settlement",
                "difference",
                "reconciliation_status",
                "exception_reason",
                "ledger_net",
                "ledger_difference",
                "ledger_status",
                "final_status",
            ]
        ].to_string(index=False)
    )
    print_reconciliation_summary(
    payment_view
    )
    evaluate_detection(
    payment_view
    )