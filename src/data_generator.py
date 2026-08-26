from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import random

import pandas as pd
from faker import Faker

from schema import (
    CUSTOMER_COLUMNS,
    ORDER_COLUMNS,
    PAYMENT_COLUMNS,
    FEE_COLUMNS,
    REFUND_COLUMNS,
    SETTLEMENT_COLUMNS,
    LEDGER_COLUMNS,
)

fake = Faker("en_IN")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def money(value) -> Decimal:
    """
    Convert a value to Decimal and round it to 2 decimal places.
    Used for all financial calculations.
    """
    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

def generate_customers(count: int) -> pd.DataFrame:
    customers = []

    for i in range(1, count + 1):
        customers.append(
            {
                "customer_id": f"CUST{i:05d}",
                "name": fake.name(),
                "email": fake.email(),
            }
        )

    return pd.DataFrame(
        customers,
        columns=CUSTOMER_COLUMNS,
    )

def generate_orders(customers_df: pd.DataFrame) -> pd.DataFrame:
    orders = []

    for i, customer in customers_df.iterrows():

        order_amount = Decimal(
            random.randint(500, 20_000)
        )

        orders.append(
            {
                "order_id": f"ORD{i + 1:05d}",
                "customer_id": customer["customer_id"],
                "order_amount": money(order_amount),
                "created_at": fake.date_time_between(
                    start_date="-30d",
                    end_date="now",
                ),
            }
        )

    return pd.DataFrame(
        orders,
        columns=ORDER_COLUMNS,
    )


# ---------------------------------------------------------
# 3. Payments
# ---------------------------------------------------------

def generate_payments(orders_df: pd.DataFrame) -> pd.DataFrame:
    payments = []

    payment_methods = [
        "UPI",
        "CARD",
        "NETBANKING",
        "WALLET",
    ]

    for i, order in orders_df.iterrows():

        payments.append(
            {
                "payment_id": f"PAY{i + 1:05d}",
                "order_id": order["order_id"],
                "customer_id": order["customer_id"],
                "amount": money(order["order_amount"]),
                "payment_method": random.choice(payment_methods),
                "status": "SUCCESS",
                "created_at": order["created_at"],
            }
        )

    return pd.DataFrame(
        payments,
        columns=PAYMENT_COLUMNS,
    )


# ---------------------------------------------------------
# 4. Fees
# ---------------------------------------------------------

def generate_fees(payments_df: pd.DataFrame) -> pd.DataFrame:
    fees = []

    fee_rate = Decimal("0.02")

    for i, payment in payments_df.iterrows():

        payment_amount = money(payment["amount"])

        fee_amount = money(
            payment_amount * fee_rate
        )

        fees.append(
            {
                "fee_id": f"FEE{i + 1:05d}",
                "payment_id": payment["payment_id"],
                "fee_amount": fee_amount,
                "fee_type": "PROCESSING_FEE",
                "created_at": payment["created_at"],
            }
        )

    return pd.DataFrame(
        fees,
        columns=FEE_COLUMNS,
    )


# ---------------------------------------------------------
# 5. Refunds
# ---------------------------------------------------------

def generate_refunds(payments_df: pd.DataFrame) -> pd.DataFrame:
    refunds = []

    refund_counter = 1

    for _, payment in payments_df.iterrows():

        # Around 20% of payments get a refund
        if random.random() >= 0.20:
            continue

        payment_amount = money(
            payment["amount"]
        )

        # Healthy baseline uses only partial refunds.
        refund_percentage = Decimal(
            str(
                round(
                    random.uniform(0.10, 0.70),
                    2,
                )
            )
        )

        refund_amount = money(
            payment_amount * refund_percentage
        )

        refunds.append(
            {
                "refund_id": f"REF{refund_counter:05d}",
                "payment_id": payment["payment_id"],
                "refund_amount": refund_amount,
                "refund_date": (
                    pd.Timestamp(payment["created_at"])
                    + pd.Timedelta(
                        days=random.randint(1, 5)
                    )
                ),
                "status": "PROCESSED",
            }
        )

        refund_counter += 1

    return pd.DataFrame(
        refunds,
        columns=REFUND_COLUMNS,
    )


# ---------------------------------------------------------
# 6. Settlements
# ---------------------------------------------------------

def generate_settlements(
    payments_df: pd.DataFrame,
    fees_df: pd.DataFrame,
    refunds_df: pd.DataFrame,
) -> pd.DataFrame:

    settlements = []

    for i, payment in payments_df.iterrows():

        payment_id = payment["payment_id"]

        payment_amount = money(
            payment["amount"]
        )

        # Find fee for this payment
        fee_rows = fees_df[
            fees_df["payment_id"] == payment_id
        ]

        fee_amount = (
            money(fee_rows.iloc[0]["fee_amount"])
            if not fee_rows.empty
            else Decimal("0.00")
        )

        # Find refunds for this payment
        refund_rows = refunds_df[
            refunds_df["payment_id"] == payment_id
        ]

        if refund_rows.empty:
            total_refund = Decimal("0.00")
        else:
            total_refund = sum(
                (
                    money(amount)
                    for amount in refund_rows[
                        "refund_amount"
                    ]
                ),
                Decimal("0.00"),
            )

        # Our synthetic reconciliation rule:
        #
        # Settlement = Payment - Fee - Refund
        settlement_amount = money(
            payment_amount
            - fee_amount
            - total_refund
        )

        settlements.append(
            {
                "settlement_id": f"SET{i + 1:05d}",
                "payment_id": payment_id,
                "settlement_amount": settlement_amount,
                "settlement_date": (
                    pd.Timestamp(payment["created_at"])
                    + pd.Timedelta(days=2)
                ),
                "status": "SETTLED",
            }
        )

    return pd.DataFrame(
        settlements,
        columns=SETTLEMENT_COLUMNS,
    )


# ---------------------------------------------------------
# 7. Ledger
# ---------------------------------------------------------

def generate_ledger(
    payments_df: pd.DataFrame,
    fees_df: pd.DataFrame,
    refunds_df: pd.DataFrame,
) -> pd.DataFrame:

    ledger_entries = []

    ledger_counter = 1

    for _, payment in payments_df.iterrows():

        payment_id = payment["payment_id"]

        # Payment entry
        ledger_entries.append(
            {
                "ledger_id": f"LED{ledger_counter:05d}",
                "payment_id": payment_id,
                "entry_type": "PAYMENT",
                "amount": money(payment["amount"]),
                "created_at": payment["created_at"],
            }
        )

        ledger_counter += 1

        # Fee entry
        fee_rows = fees_df[
            fees_df["payment_id"] == payment_id
        ]

        if not fee_rows.empty:

            fee_amount = money(
                fee_rows.iloc[0]["fee_amount"]
            )

            ledger_entries.append(
                {
                    "ledger_id": f"LED{ledger_counter:05d}",
                    "payment_id": payment_id,
                    "entry_type": "FEE",
                    "amount": -fee_amount,
                    "created_at": fee_rows.iloc[0][
                        "created_at"
                    ],
                }
            )

            ledger_counter += 1

        # Refund entries
        refund_rows = refunds_df[
            refunds_df["payment_id"] == payment_id
        ]

        for _, refund in refund_rows.iterrows():

            refund_amount = money(
                refund["refund_amount"]
            )

            ledger_entries.append(
                {
                    "ledger_id": f"LED{ledger_counter:05d}",
                    "payment_id": payment_id,
                    "entry_type": "REFUND",
                    "amount": -refund_amount,
                    "created_at": refund["refund_date"],
                }
            )

            ledger_counter += 1

    return pd.DataFrame(
        ledger_entries,
        columns=LEDGER_COLUMNS,
    )


# ---------------------------------------------------------
# 8. Baseline integrity check
# ---------------------------------------------------------

def verify_baseline(
    payments_df: pd.DataFrame,
    fees_df: pd.DataFrame,
    refunds_df: pd.DataFrame,
    settlements_df: pd.DataFrame,
    ledger_df: pd.DataFrame,
) -> bool:

    print("\n" + "=" * 70)
    print("BASELINE FINANCIAL CALCULATION CHECK")
    print("=" * 70)

    all_passed = True

    for _, payment in payments_df.iterrows():

        payment_id = payment["payment_id"]

        payment_amount = money(
            payment["amount"]
        )

        # -------------------------
        # Find fee
        # -------------------------

        fee_rows = fees_df[
            fees_df["payment_id"] == payment_id
        ]

        if fee_rows.empty:
            fee_amount = Decimal("0.00")
        else:
            fee_amount = money(
                fee_rows.iloc[0]["fee_amount"]
            )

        # -------------------------
        # Find refunds
        # -------------------------

        refund_rows = refunds_df[
            refunds_df["payment_id"] == payment_id
        ]

        if refund_rows.empty:
            refund_amount = Decimal("0.00")
        else:
            refund_amount = sum(
                (
                    money(amount)
                    for amount in refund_rows[
                        "refund_amount"
                    ]
                ),
                Decimal("0.00"),
            )

        # -------------------------
        # Expected settlement
        # -------------------------

        expected_settlement = money(
            payment_amount
            - fee_amount
            - refund_amount
        )

        # -------------------------
        # Actual settlement
        # -------------------------

        settlement_rows = settlements_df[
            settlements_df["payment_id"] == payment_id
        ]

        if settlement_rows.empty:
            print(
                f"\n❌ {payment_id}: Settlement missing"
            )
            all_passed = False
            continue

        actual_settlement = money(
            settlement_rows.iloc[0][
                "settlement_amount"
            ]
        )

        # -------------------------
        # Ledger calculation
        # -------------------------

        payment_ledger = ledger_df[
            ledger_df["payment_id"] == payment_id
        ]

        ledger_net = sum(
            (
                money(amount)
                for amount in payment_ledger[
                    "amount"
                ]
            ),
            Decimal("0.00"),
        )

        # -------------------------
        # Display calculation
        # -------------------------

        print(f"\n{payment_id}")
        print("-" * 70)

        print(
            f"Payment      : ₹{payment_amount:,.2f}"
        )

        print(
            f"Fee          : -₹{fee_amount:,.2f}"
        )

        print(
            f"Refund       : -₹{refund_amount:,.2f}"
        )

        print(
            f"Calculation  : "
            f"{payment_amount:,.2f} "
            f"- {fee_amount:,.2f} "
            f"- {refund_amount:,.2f}"
        )

        print(
            f"Expected Set.: ₹{expected_settlement:,.2f}"
        )

        print(
            f"Actual Set.  : ₹{actual_settlement:,.2f}"
        )

        print(
            f"Ledger Net   : ₹{ledger_net:,.2f}"
        )

        # -------------------------
        # Validation
        # -------------------------

        settlement_ok = (
            expected_settlement
            == actual_settlement
        )

        ledger_ok = (
            ledger_net
            == actual_settlement
        )

        if settlement_ok and ledger_ok:

            print(
                "Result       : ✅ MATCH"
            )

        else:

            print(
                "Result       : ❌ MISMATCH"
            )

            all_passed = False

    print("\n" + "=" * 70)

    if all_passed:
        print(
            "✅ ALL BASELINE RECORDS PASSED"
        )
    else:
        print(
            "❌ SOME BASELINE RECORDS FAILED"
        )

    print("=" * 70)

    return all_passed

# ---------------------------------------------------------
# 9. Main program
# ---------------------------------------------------------

if __name__ == "__main__":

    RECORD_COUNT = 20

    # Generate our healthy financial world
    customers_df = generate_customers(RECORD_COUNT)

    orders_df = generate_orders(
        customers_df
    )

    payments_df = generate_payments(
        orders_df
    )

    fees_df = generate_fees(
        payments_df
    )

    refunds_df = generate_refunds(
        payments_df
    )

    settlements_df = generate_settlements(
        payments_df,
        fees_df,
        refunds_df,
    )

    ledger_df = generate_ledger(
        payments_df,
        fees_df,
        refunds_df,
    )

    # Verify the healthy dataset
    verify_baseline(
        payments_df,
        fees_df,
        refunds_df,
        settlements_df,
        ledger_df,
    )

    # Save everything
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    datasets = {
        "customers.csv": customers_df,
        "orders.csv": orders_df,
        "payments.csv": payments_df,
        "fees.csv": fees_df,
        "refunds.csv": refunds_df,
        "settlements.csv": settlements_df,
        "ledger.csv": ledger_df,
    }

    print("\n--- Saving Files ---")

    for filename, dataframe in datasets.items():

        output_path = DATA_DIR / filename

        dataframe.to_csv(
            output_path,
            index=False,
        )

        print(
            f"✅ Saved: {output_path}"
        )