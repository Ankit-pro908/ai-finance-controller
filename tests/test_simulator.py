from src.controller.simulator import (
    simulate_hypothesis,
)

from src.evidence.retriever import (
    load_exception_data,
)


def test_single_change_can_clear_exception():

    data = load_exception_data()

    hypothesis = {
        "hypothesis_id": "H1",

        "affected_records": [
            {
                "source": "refund",
                "record_id": "REF00001",
                "field": "refund_amount",
                "observed_value": 3062.92,
                "proposed_value": 2812.92,
                "role": "REFUND_AMOUNT",
            }
        ],
    }

    result = simulate_hypothesis(
        data=data,
        payment_id="PAY00004",
        hypothesis=hypothesis,
    )

    assert result["status"] == "SUCCESS"

    assert (
        result["exception_cleared"]
        is True
    )


def test_multiple_changes_are_simulated_together():

    data = load_exception_data()

    hypothesis = {
        "hypothesis_id": "H1",

        "affected_records": [
            {
                "source": "refund",
                "record_id": "REF00001",
                "field": "refund_amount",
                "observed_value": 3062.92,
                "proposed_value": 2812.92,
                "role": "REFUND_AMOUNT",
            },

            {
                "source": "ledger",
                "record_id": "LED00009",
                "field": "amount",
                "observed_value": -2812.92,
                "proposed_value": -3062.92,
                "role": "LEDGER_AMOUNT",
            },
        ],
    }

    result = simulate_hypothesis(
        data=data,
        payment_id="PAY00004",
        hypothesis=hypothesis,
    )

    assert (
        result["change_count"]
        == 2
    )

    assert len(
        result["applied_changes"]
    ) == 2


def test_unchanged_proposed_value_is_not_a_change():

    data = load_exception_data()

    hypothesis = {
        "hypothesis_id": "H1",

        "affected_records": [
            {
                "source": "refund",
                "record_id": "REF00001",
                "field": "refund_amount",
                "observed_value": 3062.92,
                "proposed_value": 2812.92,
                "role": "REFUND_AMOUNT",
            },

            {
                "source": "ledger",
                "record_id": "LED00009",
                "field": "amount",
                "observed_value": -2812.92,
                "proposed_value": -2812.92,
                "role": "LEDGER_AMOUNT",
            },
        ],
    }

    result = simulate_hypothesis(
        data=data,
        payment_id="PAY00004",
        hypothesis=hypothesis,
    )

    assert (
        result["change_count"]
        == 1
    )