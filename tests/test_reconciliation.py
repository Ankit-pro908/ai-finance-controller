import pandas as pd

from src.reconciliation.engine import (
    calculate_expected_settlement,
    classify_reconciliation,
)


def test_expected_settlement_calculation():
    data = pd.DataFrame(
        {
            "payment_id": ["PAY_TEST"],
            "amount": [10000.00],
            "total_fee": [200.00],
            "total_refund": [1000.00],
            "actual_settlement": [8800.00],
        }
    )

    result = calculate_expected_settlement(data)

    assert (
        result.loc[0, "expected_settlement"]
        == 8800.00
    )

    assert (
        result.loc[0, "difference"]
        == 0.00
    )


def test_mismatch_is_exception():
    data = pd.DataFrame(
        {
            "payment_id": ["PAY_TEST"],
            "amount": [10000.00],
            "total_fee": [200.00],
            "total_refund": [0.00],
            "actual_settlement": [9500.00],
        }
    )

    result = calculate_expected_settlement(data)

    result = classify_reconciliation(result)

    assert (
        result.loc[0, "reconciliation_status"]
        == "EXCEPTION"
    )


def test_missing_settlement_is_exception():
    data = pd.DataFrame(
        {
            "payment_id": ["PAY_TEST"],
            "amount": [10000.00],
            "total_fee": [200.00],
            "total_refund": [0.00],
            "actual_settlement": [float("nan")],
        }
    )

    result = calculate_expected_settlement(data)

    result = classify_reconciliation(result)

    assert (
        result.loc[0, "reconciliation_status"]
        == "EXCEPTION"
    )