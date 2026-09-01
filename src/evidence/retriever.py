from pathlib import Path

import pandas as pd
try:
    from .case_builder import (
        build_investigation_case,
    )

    from .completeness import (
        calculate_evidence_completeness,
    )

    from .consistency import (
        check_evidence_consistency,
    )

except ImportError:
    from case_builder import (
        build_investigation_case,
    )

    from completeness import (
        calculate_evidence_completeness,
    )

    from consistency import (
        check_evidence_consistency,
    )


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent.parent
)

EXCEPTION_DATA_DIR = (
    PROJECT_ROOT / "data" / "exceptions"
)


# ---------------------------------------------------------
# Load exception data
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Retrieve evidence for one payment
# ---------------------------------------------------------

def retrieve_payment_evidence(
    data,
    payment_id: str,
):

    payments_df = data["payments"]
    fees_df = data["fees"]
    refunds_df = data["refunds"]
    settlements_df = data["settlements"]
    ledger_df = data["ledger"]

    # Main payment record
    payment_rows = payments_df[
        payments_df["payment_id"] == payment_id
    ]

    # Related fees
    fee_rows = fees_df[
        fees_df["payment_id"] == payment_id
    ]

    # Related refunds
    refund_rows = refunds_df[
        refunds_df["payment_id"] == payment_id
    ]

    # Related settlement
    settlement_rows = settlements_df[
        settlements_df["payment_id"] == payment_id
    ]

    # Related ledger entries
    ledger_rows = ledger_df[
        ledger_df["payment_id"] == payment_id
    ]

    return {
        "payment": payment_rows,
        "fees": fee_rows,
        "refunds": refund_rows,
        "settlement": settlement_rows,
        "ledger": ledger_rows,
    }


# ---------------------------------------------------------
# Test
# ---------------------------------------------------------

if __name__ == "__main__":

    data = load_exception_data()

    test_payment_ids = [
        "PAY00001",
        "PAY00002",
        "PAY00004",
        "PAY00005",
        "PAY00007",
    ]

    print(
        "\n========================================"
    )

    print(
        "EVIDENCE RETRIEVAL TEST"
    )

    print(
        "========================================"
    )

    for payment_id in test_payment_ids:

        evidence = retrieve_payment_evidence(
            data,
            payment_id,
        )

        print(
            f"\n--- {payment_id} ---"
        )

        print(
            f"Payment     : "
            f"{len(evidence['payment'])} record(s)"
        )

        print(
            f"Fees        : "
            f"{len(evidence['fees'])} record(s)"
        )

        print(
            f"Refunds     : "
            f"{len(evidence['refunds'])} record(s)"
        )

        print(
            f"Settlement  : "
            f"{len(evidence['settlement'])} record(s)"
        )

        print(
            f"Ledger      : "
            f"{len(evidence['ledger'])} record(s)"
        )
        
        completeness = (
            calculate_evidence_completeness(
                evidence
            )
        )
        consistency = (
            check_evidence_consistency(
                evidence
            )
        )    
        print(
            f"Consistency: "
            f"{'PASS' if consistency['consistent'] else 'CONFLICT'}"
        )

        print(
            f"Conflicts  : "
            f"{consistency['conflicts']}"
        )


        print(
            f"Completeness: "
            f"{completeness['completeness_percentage']:.2f}%"
        )

        print(
            f"Missing     : "
            f"{completeness['missing_sources']}"
        )
        print(
            f"Checks      : "
            f"{completeness['checks']}"
        )    