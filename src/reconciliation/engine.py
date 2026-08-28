from pathlib import Path

import pandas as pd


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

if __name__ == "__main__":

    data = load_exception_data()

    payment_view = build_payment_view(
        data
    )

    payment_view = calculate_expected_settlement(
        payment_view
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
            ]
        ]
    )