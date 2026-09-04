from typing import Any

import pandas as pd


# =========================================================
# Deterministic hypothesis generator
#
# This module does NOT use:
#   - payment IDs
#   - ground_truth.csv
#   - AI
#
# It uses only the controller case and supplied evidence.
#
# Its job is to create financially testable hypotheses for
# exceptions that can be reasoned about deterministically.
#
# AI remains responsible for ambiguous/interpretive cases.
# =========================================================


TOLERANCE = 0.01


# =========================================================
# Helpers
# =========================================================

def _to_float(
    value: Any,
) -> float | None:
    """
    Safely convert numeric-like values to float.

    Returns None when conversion is not possible.
    """

    if value is None:
        return None

    try:

        number = float(value)

        if pd.isna(number):
            return None

        return number

    except (
        TypeError,
        ValueError,
    ):

        return None


def _close(
    first: Any,
    second: Any,
) -> bool:
    """
    Compare two numeric values using financial tolerance.
    """

    first_value = _to_float(
        first
    )

    second_value = _to_float(
        second
    )

    if (
        first_value is None
        or second_value is None
    ):
        return False

    return (
        abs(
            first_value
            - second_value
        )
        <= TOLERANCE
    )


def _first_row(
    dataframe: pd.DataFrame,
) -> pd.Series | None:
    """
    Return the first row when available.
    """

    if dataframe is None:
        return None

    if dataframe.empty:
        return None

    return dataframe.iloc[0]


def _rows_for_payment(
    dataframe: pd.DataFrame,
    payment_id: str,
) -> pd.DataFrame:
    """
    Return records belonging to one payment.
    """

    if dataframe is None:
        return pd.DataFrame()

    if dataframe.empty:
        return dataframe

    if "payment_id" not in dataframe.columns:
        return pd.DataFrame()

    return dataframe[
        dataframe[
            "payment_id"
        ].astype(str)
        == str(payment_id)
    ]

def _source_matches_ledger(
    evidence: dict[str, Any],
    payment_id: str,
    source: str,
    amount_field: str,
    ledger_entry_type: str,
) -> bool:
    """
    Check whether a source amount agrees with the corresponding
    ledger entry for the same payment.

    For refunds, the ledger amount is expected to have the
    opposite sign.
    """

    source_df = evidence.get(
        source,
        pd.DataFrame(),
    )

    ledger_df = evidence.get(
        "ledger",
        pd.DataFrame(),
    )

    source_rows = _rows_for_payment(
        source_df,
        payment_id,
    )

    ledger_rows = _rows_for_payment(
        ledger_df,
        payment_id,
    )

    if source_rows.empty:
        return False

    if ledger_rows.empty:
        return False

    if (
        amount_field
        not in source_rows.columns
    ):
        return False

    if (
        "entry_type"
        not in ledger_rows.columns
        or "amount"
        not in ledger_rows.columns
    ):
        return False

    source_total = round(
        sum(
            _to_float(value) or 0.0
            for value in source_rows[
                amount_field
            ]
        ),
        2,
    )

    matching_ledger_rows = ledger_rows[
        ledger_rows[
            "entry_type"
        ]
        .astype(str)
        .str.upper()
        == ledger_entry_type.upper()
    ]

    if matching_ledger_rows.empty:
        return False

    ledger_total = round(
        sum(
            _to_float(value) or 0.0
            for value in matching_ledger_rows[
                "amount"
            ]
        ),
        2,
    )

    if ledger_entry_type.upper() == "REFUND":
        ledger_total = abs(
            ledger_total
        )

    return _close(
        source_total,
        abs(ledger_total),
    )

def _single_record_change(
    source: str,
    record_id: str,
    field: str,
    observed_value: Any,
    proposed_value: Any,
    role: str,
) -> dict[str, Any]:
    """
    Build one standard affected-record object.
    """

    return {
        "source": source,
        "record_id": str(
            record_id
        ),
        "field": field,
        "observed_value": observed_value,
        "proposed_value": proposed_value,
        "role": role,
    }


def _relationship(
    relationship_type: str,
    claimed_delta: Any,
    direction: str,
) -> dict[str, Any]:
    """
    Build the causal relationship object.
    """

    return {
        "type": relationship_type,
        "claimed_delta": claimed_delta,
        "direction": direction,
    }


def _build_hypothesis(
    hypothesis_id: str,
    root_cause: str,
    explanation: str,
    affected_records: list[dict[str, Any]],
    relationship_type: str,
    claimed_delta: Any,
    direction: str,
) -> dict[str, Any]:
    """
    Build a canonical hypothesis matching the current AI
    response contract.
    """

    return {
        "hypothesis_id": hypothesis_id,
        "root_cause": root_cause,
        "explanation": explanation,
        "affected_records": affected_records,
        "causal_relationship": _relationship(
            relationship_type,
            claimed_delta,
            direction,
        ),
    }

def _settlement_or_upstream_mismatch(
    controller_case: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Decide whether a settlement mismatch is caused by the
    settlement record itself or by an upstream component.

    When settlement agrees with ledger, inspect the actual
    upstream source-to-ledger relationships before generating
    competing hypotheses.

    No payment IDs are hardcoded.
    """

    reconciliation = (
        controller_case[
            "financial_facts"
        ][
            "reconciliation"
        ]
    )

    evidence = controller_case.get(
        "evidence",
        {},
    )

    actual_settlement = _to_float(
        reconciliation.get(
            "actual_settlement"
        )
    )

    ledger_net = _to_float(
        reconciliation.get(
            "ledger_net"
        )
    )

    payment_rows = evidence.get(
        "payment",
        pd.DataFrame(),
    )

    payment_row = _first_row(
        payment_rows
    )

    if payment_row is None:
        return []

    payment_id = payment_row.get(
        "payment_id"
    )

    if payment_id is None:
        return []

    # -----------------------------------------------------
    # Settlement agrees with ledger.
    #
    # In this situation, do not create competing fee/refund
    # hypotheses merely because either could mathematically
    # alter the settlement equation.
    #
    # First determine which upstream source actually disagrees
    # with its corresponding ledger entry.
    # -----------------------------------------------------

    if (
        actual_settlement is not None
        and ledger_net is not None
        and _close(
            actual_settlement,
            ledger_net,
        )
    ):

        fee_matches_ledger = (
            _source_matches_ledger(
                evidence=evidence,
                payment_id=payment_id,
                source="fees",
                amount_field="fee_amount",
                ledger_entry_type="FEE",
            )
        )

        refund_matches_ledger = (
            _source_matches_ledger(
                evidence=evidence,
                payment_id=payment_id,
                source="refunds",
                amount_field="refund_amount",
                ledger_entry_type="REFUND",
            )
        )

        # -------------------------------------------------
        # Both upstream sources agree with the ledger.
        #
        # No defensible upstream correction can be selected
        # from source-to-ledger evidence.
        # -------------------------------------------------

        if (
            fee_matches_ledger
            and refund_matches_ledger
        ):
            return []

        # -------------------------------------------------
        # Fee source disagrees with ledger, refund agrees.
        # -------------------------------------------------

        if (
            not fee_matches_ledger
            and refund_matches_ledger
        ):

            return _fee_mismatch(
                controller_case
            )[:1]

        # -------------------------------------------------
        # Refund source disagrees with ledger, fee agrees.
        # -------------------------------------------------

        if (
            fee_matches_ledger
            and not refund_matches_ledger
        ):

            refund_candidates = (
                _refund_mismatch(
                    controller_case
                )
            )

            return refund_candidates[:1]

        # -------------------------------------------------
        # Both sources disagree with the ledger.
        #
        # This is genuinely ambiguous from the current
        # deterministic evidence, so preserve both candidate
        # explanations for AI comparison.
        # -------------------------------------------------

        refund_candidates = (
            _refund_mismatch(
                controller_case
            )
        )

        fee_candidates = (
            _fee_mismatch(
                controller_case
            )
        )

        if (
            refund_candidates
            and fee_candidates
        ):
            return [
                *fee_candidates,
                *refund_candidates,
            ]

        if refund_candidates:
            return refund_candidates

        if fee_candidates:
            return fee_candidates

        return []

    # -----------------------------------------------------
    # Settlement itself disagrees with ledger.
    # -----------------------------------------------------

    return _settlement_amount_mismatch(
        controller_case
    )
    
# =========================================================
# SETTLEMENT AMOUNT MISMATCH
# =========================================================

def _settlement_amount_mismatch(
    controller_case: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Build a deterministic correction candidate when the
    settlement amount differs from the expected settlement.

    Example:

        expected = 4065.04
        actual   = 3565.04

        candidate:
            settlement_amount
            3565.04 -> 4065.04
    """

    reconciliation = (
        controller_case[
            "financial_facts"
        ][
            "reconciliation"
        ]
    )

    evidence = (
        controller_case[
            "evidence"
        ]
    )

    expected = _to_float(
        reconciliation.get(
            "expected_settlement"
        )
    )

    actual = _to_float(
        reconciliation.get(
            "actual_settlement"
        )
    )

    if (
        expected is None
        or actual is None
    ):
        return []

    difference = round(
        actual - expected,
        2,
    )

    if _close(
        expected,
        actual,
    ):
        return []

    settlement_df = evidence.get(
        "settlement",
        pd.DataFrame(),
    )

    settlement_row = _first_row(
        settlement_df
    )

    if settlement_row is None:
        return []

    settlement_id = settlement_row.get(
        "settlement_id"
    )

    observed_value = settlement_row.get(
        "settlement_amount"
    )

    if (
        settlement_id is None
        or observed_value is None
    ):
        return []

    return [
        _build_hypothesis(
            hypothesis_id="D1",
            root_cause=(
                "Settlement amount does not "
                "match the deterministic expected "
                "settlement."
            ),
            explanation=(
                f"The settlement record reports "
                f"{_to_float(observed_value):.2f}, "
                f"while the reconciliation engine "
                f"calculates an expected settlement "
                f"of {expected:.2f}. "
                f"Correcting the settlement amount "
                f"to {expected:.2f} removes the "
                f"observed discrepancy of "
                f"{abs(difference):.2f}."
            ),
            affected_records=[
                _single_record_change(
                    source="settlement",
                    record_id=settlement_id,
                    field="settlement_amount",
                    observed_value=observed_value,
                    proposed_value=expected,
                    role="SETTLEMENT_AMOUNT",
                )
            ],
            relationship_type="RECORD_DELTA",
            claimed_delta=abs(
                difference
            ),
            direction=(
                "INCREASE"
                if expected > actual
                else "DECREASE"
            ),
        )
    ]


# =========================================================
# MISSING SETTLEMENT
# =========================================================

def _missing_settlement(
    controller_case: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Identify a missing settlement event.

    No fake record ID is created.

    The simulator will later construct the missing record
    from deterministic financial facts.
    """

    reconciliation = (
        controller_case[
            "financial_facts"
        ][
            "reconciliation"
        ]
    )

    evidence = (
        controller_case[
            "evidence"
        ]
    )

    settlement_df = evidence.get(
        "settlement",
        pd.DataFrame(),
    )

    if not settlement_df.empty:
        return []

    expected = _to_float(
        reconciliation.get(
            "expected_settlement"
        )
    )

    if expected is None:
        return []

    payment_df = evidence.get(
        "payment",
        pd.DataFrame(),
    )

    payment_row = _first_row(
        payment_df
    )

    if payment_row is None:
        return []

    payment_id = payment_row.get(
        "payment_id"
    )

    if payment_id is None:
        return []

    return [
        _build_hypothesis(
            hypothesis_id="D1",
            root_cause=(
                "Settlement record is missing."
            ),
            explanation=(
                f"No settlement record exists "
                f"for payment {payment_id}. "
                f"The deterministic reconciliation "
                f"engine expects a settlement of "
                f"{expected:.2f}."
            ),
            affected_records=[
                {
                    "source": "settlement",
                    "record_id": None,
                    "field": "settlement_amount",
                    "observed_value": None,
                    "proposed_value": None,
                    "role": "MISSING_SETTLEMENT_EVENT",
                }
            ],
            relationship_type="MISSING_RECORD",
            claimed_delta=expected,
            direction="INCREASE",
        )
    ]


# =========================================================
# FEE MISMATCH
# =========================================================
def _fee_mismatch(
    controller_case: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Determine whether the recorded fee differs from the
    fee implied by:

        payment
        - refund
        - actual settlement

    Normally, one fee hypothesis is returned.

    If the same discrepancy can also be explained by
    changing an existing refund record, both hypotheses
    are returned so the controller can treat the case as
    ambiguous and route it through the AI comparison path.
    """

    reconciliation = (
        controller_case[
            "financial_facts"
        ][
            "reconciliation"
        ]
    )

    evidence = (
        controller_case[
            "evidence"
        ]
    )

    payment_df = evidence.get(
        "payment",
        pd.DataFrame(),
    )

    fee_df = evidence.get(
        "fees",
        pd.DataFrame(),
    )

    refund_df = evidence.get(
        "refunds",
        pd.DataFrame(),
    )

    # -----------------------------------------------------
    # Payment
    # -----------------------------------------------------

    payment_row = _first_row(
        payment_df
    )

    if payment_row is None:
        return []

    payment_amount = _to_float(
        payment_row.get(
            "amount"
        )
    )

    if payment_amount is None:
        return []

    payment_id = payment_row.get(
        "payment_id"
    )

    if payment_id is None:
        return []

    # -----------------------------------------------------
    # Actual settlement
    # -----------------------------------------------------

    actual_settlement = _to_float(
        reconciliation.get(
            "actual_settlement"
        )
    )

    if actual_settlement is None:
        return []

    # -----------------------------------------------------
    # Refund evidence
    # -----------------------------------------------------

    payment_refunds = (
        _rows_for_payment(
            refund_df,
            payment_id,
        )
    )

    total_refund = 0.0

    if not payment_refunds.empty:

        total_refund = round(
            sum(
                _to_float(value) or 0.0
                for value in payment_refunds[
                    "refund_amount"
                ]
            ),
            2,
        )

    # -----------------------------------------------------
    # Fee implied by the financial equation
    # -----------------------------------------------------

    implied_fee = round(
        payment_amount
        - total_refund
        - actual_settlement,
        2,
    )

    # -----------------------------------------------------
    # Recorded fee evidence
    # -----------------------------------------------------

    payment_fees = _rows_for_payment(
        fee_df,
        payment_id,
    )

    if payment_fees.empty:
        return []

    total_recorded_fee = round(
        sum(
            _to_float(value) or 0.0
            for value in payment_fees[
                "fee_amount"
            ]
        ),
        2,
    )

    # Already consistent
    if _close(
        implied_fee,
        total_recorded_fee,
    ):
        return []

    # Only one fee record can currently be corrected
    # deterministically.
    if len(payment_fees) != 1:
        return []

    fee_row = payment_fees.iloc[0]

    fee_id = fee_row.get(
        "fee_id"
    )

    observed_fee = _to_float(
        fee_row.get(
            "fee_amount"
        )
    )

    if (
        fee_id is None
        or observed_fee is None
    ):
        return []

    delta = round(
        implied_fee
        - total_recorded_fee,
        2,
    )

    # -----------------------------------------------------
    # Primary fee hypothesis
    # -----------------------------------------------------

    fee_hypothesis = _build_hypothesis(
        hypothesis_id="H1",
        root_cause=(
            "Recorded fee amount does not "
            "match the fee implied by the "
            "payment, refund, and settlement."
        ),
        explanation=(
            f"The recorded fee is "
            f"{total_recorded_fee:.2f}, "
            f"but the deterministic financial "
            f"equation implies a fee of "
            f"{implied_fee:.2f}. "
            f"Changing the fee record to "
            f"{implied_fee:.2f} changes the "
            f"fee by {abs(delta):.2f}."
        ),
        affected_records=[
            _single_record_change(
                source="fee",
                record_id=fee_id,
                field="fee_amount",
                observed_value=observed_fee,
                proposed_value=implied_fee,
                role="FEE_AMOUNT",
            )
        ],
        relationship_type=(
            "RECORD_DELTA"
        ),
        claimed_delta=abs(delta),
        direction=(
            "INCREASE"
            if implied_fee > total_recorded_fee
            else "DECREASE"
        ),
    )

    # -----------------------------------------------------
    # Competing refund explanation
    #
    # The same settlement discrepancy may also be
    # explained by changing the recorded refund.
    #
    # IMPORTANT:
    # We only create this candidate when a refund record
    # actually exists and its required adjustment equals
    # the fee discrepancy.
    # -----------------------------------------------------

    refund_hypotheses = []

    if not payment_refunds.empty:

        # With fee treated as currently recorded,
        # determine the refund implied by the equation.
        implied_refund = round(
            payment_amount
            - total_recorded_fee
            - actual_settlement,
            2,
        )

        if len(payment_refunds) == 1:

            refund_row = (
                payment_refunds.iloc[0]
            )

            refund_id = (
                refund_row.get(
                    "refund_id"
                )
            )

            observed_refund = _to_float(
                refund_row.get(
                    "refund_amount"
                )
            )

            if (
                refund_id is not None
                and observed_refund is not None
                and not _close(
                    implied_refund,
                    observed_refund,
                )
            ):

                refund_delta = round(
                    implied_refund
                    - observed_refund,
                    2,
                )

                # Only treat it as a competing
                # explanation when the magnitude of
                # the refund correction equals the
                # magnitude of the fee correction.
                if _close(
                    abs(refund_delta),
                    abs(delta),
                ):

                    refund_hypothesis = (
                        _build_hypothesis(
                            hypothesis_id="H2",
                            root_cause=(
                                "Refund amount is an "
                                "alternative explanation "
                                "for the settlement "
                                "discrepancy."
                            ),
                            explanation=(
                                f"The recorded refund is "
                                f"{observed_refund:.2f}, "
                                f"while the financial "
                                f"equation implies "
                                f"{implied_refund:.2f}. "
                                f"Changing the refund by "
                                f"{abs(refund_delta):.2f} "
                                f"could therefore explain "
                                f"the same discrepancy."
                            ),
                            affected_records=[
                                _single_record_change(
                                    source="refund",
                                    record_id=(
                                        refund_id
                                    ),
                                    field="refund_amount",
                                    observed_value=(
                                        observed_refund
                                    ),
                                    proposed_value=(
                                        implied_refund
                                    ),
                                    role=(
                                        "ALTERNATIVE_REFUND_CAUSE"
                                    ),
                                )
                            ],
                            relationship_type=(
                                "RECORD_DELTA"
                            ),
                            claimed_delta=(
                                abs(refund_delta)
                            ),
                            direction=(
                                "INCREASE"
                                if implied_refund
                                > observed_refund
                                else "DECREASE"
                            ),
                        )
                    )

                    refund_hypotheses.append(
                        refund_hypothesis
                    )

    # -----------------------------------------------------
    # Ambiguous case:
    # return both candidates.
    # -----------------------------------------------------

    if refund_hypotheses:

        return [
            fee_hypothesis,
            *refund_hypotheses,
        ]

    # -----------------------------------------------------
    # Ordinary fee mismatch:
    # return only fee candidate.
    # -----------------------------------------------------

    return [
        fee_hypothesis
    ]


# =========================================================
# REFUND MISMATCH
# =========================================================

def _refund_mismatch(
    controller_case: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Determine whether the recorded refund can be inferred
    from the deterministic settlement equation.

        refund
        =
        payment - fee - actual settlement
    """

    reconciliation = (
        controller_case[
            "financial_facts"
        ][
            "reconciliation"
        ]
    )

    evidence = (
        controller_case[
            "evidence"
        ]
    )

    payment_df = evidence.get(
        "payment",
        pd.DataFrame(),
    )

    fee_df = evidence.get(
        "fees",
        pd.DataFrame(),
    )

    refund_df = evidence.get(
        "refunds",
        pd.DataFrame(),
    )

    payment_row = _first_row(
        payment_df
    )

    if payment_row is None:
        return []

    payment_id = payment_row.get(
        "payment_id"
    )

    if payment_id is None:
        return []

    payment_amount = _to_float(
        payment_row.get(
            "amount"
        )
    )

    actual_settlement = _to_float(
        reconciliation.get(
            "actual_settlement"
        )
    )

    if (
        payment_amount is None
        or actual_settlement is None
    ):
        return []

    fee_rows = _rows_for_payment(
        fee_df,
        payment_id,
    )

    total_fee = 0.0

    if not fee_rows.empty:

        total_fee = sum(
            _to_float(value) or 0.0
            for value in fee_rows[
                "fee_amount"
            ]
        )

    implied_refund = round(
        payment_amount
        - total_fee
        - actual_settlement,
        2,
    )

    refund_rows = _rows_for_payment(
        refund_df,
        payment_id,
    )

    if refund_rows.empty:
        return []

    if len(refund_rows) != 1:
        return []

    refund_row = refund_rows.iloc[0]

    refund_id = refund_row.get(
        "refund_id"
    )

    observed_refund = refund_row.get(
        "refund_amount"
    )

    observed_refund_value = _to_float(
        observed_refund
    )

    if (
        refund_id is None
        or observed_refund_value is None
    ):
        return []

    if _close(
        implied_refund,
        observed_refund_value,
    ):
        return []

    delta = round(
        implied_refund
        - observed_refund_value,
        2,
    )

    return [
        _build_hypothesis(
            hypothesis_id="D1",
            root_cause=(
                "Recorded refund amount does "
                "not match the deterministic "
                "settlement equation."
            ),
            explanation=(
                f"The recorded refund is "
                f"{observed_refund_value:.2f}, "
                f"while the financial equation "
                f"implies a refund of "
                f"{implied_refund:.2f}. "
                f"Changing the refund record to "
                f"{implied_refund:.2f} changes the "
                f"refund by {abs(delta):.2f}."
            ),
            affected_records=[
                _single_record_change(
                    source="refund",
                    record_id=refund_id,
                    field="refund_amount",
                    observed_value=(
                        observed_refund
                    ),
                    proposed_value=(
                        implied_refund
                    ),
                    role="REFUND_AMOUNT",
                )
            ],
            relationship_type="RECORD_DELTA",
            claimed_delta=abs(delta),
            direction=(
                "INCREASE"
                if implied_refund > observed_refund_value
                else "DECREASE"
            ),
        )
    ]


# =========================================================
# MISSING LEDGER ENTRY
# =========================================================

def _missing_ledger_entry(
    controller_case: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Detect a missing ledger event from the difference
    between the expected/actual financial state and the
    ledger net.

    The hypothesis identifies the missing event but does
    not invent a ledger ID.
    """

    reconciliation = (
        controller_case[
            "financial_facts"
        ][
            "reconciliation"
        ]
    )

    evidence = (
        controller_case[
            "evidence"
        ]
    )

    payment_df = evidence.get(
        "payment",
        pd.DataFrame(),
    )

    payment_row = _first_row(
        payment_df
    )

    if payment_row is None:
        return []

    payment_id = payment_row.get(
        "payment_id"
    )

    payment_amount = _to_float(
        payment_row.get(
            "amount"
        )
    )

    ledger_net = _to_float(
        reconciliation.get(
            "ledger_net"
        )
    )

    actual_settlement = _to_float(
        reconciliation.get(
            "actual_settlement"
        )
    )

    if (
        payment_id is None
        or payment_amount is None
        or ledger_net is None
    ):
        return []

    # -----------------------------------------------------
    # Determine what kind of ledger event appears absent.
    # -----------------------------------------------------

    ledger_df = evidence.get(
        "ledger",
        pd.DataFrame(),
    )

    payment_ledger_rows = (
        ledger_df[
            (
                ledger_df[
                    "payment_id"
                ].astype(str)
                == str(payment_id)
            )
            &
            (
                ledger_df[
                    "entry_type"
                ].astype(str)
                == "PAYMENT"
            )
        ]
        if (
            not ledger_df.empty
            and "payment_id" in ledger_df.columns
            and "entry_type" in ledger_df.columns
        )
        else pd.DataFrame()
    )

    settlement_ledger_rows = (
        ledger_df[
            (
                ledger_df[
                    "payment_id"
                ].astype(str)
                == str(payment_id)
            )
            &
            (
                ledger_df[
                    "entry_type"
                ].astype(str)
                == "SETTLEMENT"
            )
        ]
        if (
            not ledger_df.empty
            and "payment_id" in ledger_df.columns
            and "entry_type" in ledger_df.columns
        )
        else pd.DataFrame()
    )

    # -----------------------------------------------------
    # Missing payment ledger entry
    # -----------------------------------------------------

    if payment_ledger_rows.empty:

        return [
            _build_hypothesis(
                hypothesis_id="D1",
                root_cause=(
                    "Payment ledger entry is missing."
                ),
                explanation=(
                    f"No PAYMENT ledger entry exists "
                    f"for {payment_id}, even though "
                    f"the payment record shows "
                    f"{payment_amount:.2f}."
                ),
                affected_records=[
                    {
                        "source": "ledger",
                        "record_id": None,
                        "field": "amount",
                        "observed_value": None,
                        "proposed_value": None,
                        "role": (
                            "MISSING_PAYMENT_LEDGER_ENTRY"
                        ),
                    }
                ],
                relationship_type="MISSING_RECORD",
                claimed_delta=payment_amount,
                direction="INCREASE",
            )
        ]

    # -----------------------------------------------------
    # Missing settlement ledger entry
    # -----------------------------------------------------

    if (
        actual_settlement is not None
        and settlement_ledger_rows.empty
        and not _close(
            ledger_net,
            actual_settlement,
        )
    ):

        return [
            _build_hypothesis(
                hypothesis_id="D1",
                root_cause=(
                    "Settlement ledger entry is missing."
                ),
                explanation=(
                    f"The settlement amount is "
                    f"{actual_settlement:.2f}, "
                    f"but no SETTLEMENT ledger entry "
                    f"exists for {payment_id}. "
                    f"The ledger therefore does not "
                    f"fully represent the settlement "
                    f"flow."
                ),
                affected_records=[
                    {
                        "source": "ledger",
                        "record_id": None,
                        "field": "amount",
                        "observed_value": None,
                        "proposed_value": None,
                        "role": (
                            "MISSING_SETTLEMENT_LEDGER_ENTRY"
                        ),
                    }
                ],
                relationship_type="MISSING_RECORD",
                claimed_delta=actual_settlement,
                direction="INCREASE",
            )
        ]

    return []


# =========================================================
# DUPLICATE PAYMENT
# =========================================================

def _duplicate_payment(
    controller_case: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Detect duplicate payment records using the FULL source
    dataset, not payment-scoped evidence.

    Duplicate identity is based on business attributes:
        order_id
        customer_id
        amount
        created_at

    No payment ID is hardcoded.
    """

    source_data = controller_case.get(
        "_source_data"
    )

    if not source_data:
        return []

    payment_df = source_data.get(
        "payments",
        pd.DataFrame(),
    )

    if payment_df.empty:
        return []

    required_columns = {
        "payment_id",
        "order_id",
        "customer_id",
        "amount",
        "created_at",
    }

    if not required_columns.issubset(
        payment_df.columns
    ):
        return []

    duplicates = payment_df[
        payment_df.duplicated(
            subset=[
                "order_id",
                "customer_id",
                "amount",
                "created_at",
            ],
            keep=False,
        )
    ].copy()

    if duplicates.empty:
        return []

    grouped = duplicates.groupby(
        [
            "order_id",
            "customer_id",
            "amount",
            "created_at",
        ],
        sort=False,
    )

    for _, group in grouped:

        if len(group) < 2:
            continue

        # Keep the first record as the surviving record.
        survivor = group.iloc[0]

        duplicate_records = []

        for _, row in group.iloc[1:].iterrows():

            duplicate_records.append(
                {
                    "source": "payment",
                    "record_id": str(
                        row["payment_id"]
                    ),
                    "field": "amount",
                    "observed_value": row[
                        "amount"
                    ],
                    "proposed_value": None,
                    "role": "DUPLICATE_PAYMENT",
                }
            )

        if not duplicate_records:
            continue

        affected_records = [
            {
                "source": "payment",
                "record_id": str(
                    survivor["payment_id"]
                ),
                "field": "amount",
                "observed_value": survivor[
                    "amount"
                ],
                "proposed_value": None,
                "role": "DUPLICATE_GROUP_SURVIVOR",
            }
        ]

        affected_records.extend(
            duplicate_records
        )

        return [
            _build_hypothesis(
                hypothesis_id="D1",
                root_cause=(
                    "Duplicate payment record detected."
                ),
                explanation=(
                    "Multiple payment records share "
                    "the same order, customer, amount, "
                    "and creation timestamp. The first "
                    "record is treated as the surviving "
                    "record and the additional matching "
                    "record is tested as the duplicate."
                ),
                affected_records=(
                    affected_records
                ),
                relationship_type=(
                    "DUPLICATE_RECORD"
                ),
                claimed_delta=None,
                direction="NEUTRAL",
            )
        ]

    return []

def _conflicting_evidence_fallback(
    controller_case: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Build competing hypotheses for a known ambiguous
    financial conflict.

    This is a SAFE fallback when AI cannot produce a
    usable response.

    The hypotheses are intentionally not treated as facts.
    The simulator must test them.
    """

    evidence = controller_case.get(
        "evidence",
        {}
    )

    fee_df = evidence.get(
        "fees",
        pd.DataFrame(),
    )

    refund_df = evidence.get(
        "refunds",
        pd.DataFrame(),
    )

    ledger_df = evidence.get(
        "ledger",
        pd.DataFrame(),
    )

    reconciliation = (
        controller_case[
            "financial_facts"
        ][
            "reconciliation"
        ]
    )

    payment_id = controller_case[
        "payment_id"
    ]

    difference = _to_float(
        reconciliation.get(
            "difference"
        )
    )

    if difference is None:
        return []

    delta = abs(
        difference
    )

    hypotheses = []

    # -----------------------------------------------------
    # Candidate 1:
    # Additional fee is the erroneous component.
    # -----------------------------------------------------

    payment_fees = _rows_for_payment(
        fee_df,
        payment_id,
    )

    if not payment_fees.empty:

        for _, fee_row in payment_fees.iterrows():

            fee_type = str(
                fee_row.get(
                    "fee_type",
                    "",
                )
            ).upper()

            fee_amount = _to_float(
                fee_row.get(
                    "fee_amount"
                )
            )

            fee_id = fee_row.get(
                "fee_id"
            )

            if (
                fee_id is None
                or fee_amount is None
            ):
                continue

            if (
                "ADDITIONAL"
                not in fee_type
                and not _close(
                    fee_amount,
                    delta,
                )
            ):
                continue

            hypotheses.append(
                _build_hypothesis(
                    hypothesis_id="H1",
                    root_cause=(
                        "Additional fee may be "
                        "causing the exception."
                    ),
                    explanation=(
                        f"Fee record {fee_id} "
                        f"contains {fee_amount:.2f}. "
                        f"This is consistent with "
                        f"the ambiguous fee explanation "
                        f"for the {delta:.2f} discrepancy."
                    ),
                    affected_records=[
                        _single_record_change(
                            source="fee",
                            record_id=fee_id,
                            field="fee_amount",
                            observed_value=(
                                fee_amount
                            ),
                            proposed_value=(
                                max(
                                    fee_amount - delta,
                                    0.0,
                                )
                            ),
                            role="ADDITIONAL_FEE",
                        ),

                        {
                            "source": "settlement",
                            "record_id": (
                                _first_row(
                                    evidence.get(
                                        "settlement",
                                        pd.DataFrame(),
                                    )
                                ).get(
                                    "settlement_id"
                                )
                                if _first_row(
                                    evidence.get(
                                        "settlement",
                                        pd.DataFrame(),
                                    )
                                ) is not None
                                else None
                            ),
                            "field": (
                                "settlement_amount"
                            ),
                            "observed_value": (
                                _first_row(
                                    evidence.get(
                                        "settlement",
                                        pd.DataFrame(),
                                    )
                                ).get(
                                    "settlement_amount"
                                )
                                if _first_row(
                                    evidence.get(
                                        "settlement",
                                        pd.DataFrame(),
                                    )
                                ) is not None
                                else None
                            ),
                            "proposed_value": None,
                            "role": "SETTLEMENT_REFERENCE",
                        },
                    ],
                    relationship_type="RECORD_DELTA",
                    claimed_delta=delta,
                    direction="DECREASE",
                )
            )

            break

    # -----------------------------------------------------
    # Candidate 2:
    # Refund exists but corresponding ledger refund
    # record is missing.
    # -----------------------------------------------------

    payment_refunds = _rows_for_payment(
        refund_df,
        payment_id,
    )

    refund_amount = 0.0

    if not payment_refunds.empty:

        refund_amount = round(
            sum(
                _to_float(value) or 0.0
                for value in payment_refunds[
                    "refund_amount"
                ]
            ),
            2,
        )

    if _close(
        refund_amount,
        delta,
    ):

        hypotheses.append(
            _build_hypothesis(
                hypothesis_id="H2",
                root_cause=(
                    "Refund exists in the refund "
                    "source but is not represented "
                    "in the ledger."
                ),
                explanation=(
                    f"Refund evidence contains a "
                    f"{refund_amount:.2f} refund, "
                    f"which matches the "
                    f"{delta:.2f} discrepancy. "
                    f"A missing ledger refund entry "
                    f"is therefore a plausible "
                    f"alternative explanation."
                ),
                affected_records=[
                    {
                        "source": "refund",
                        "record_id": (
                            payment_refunds.iloc[
                                0
                            ][
                                "refund_id"
                            ]
                        ),
                        "field": (
                            "refund_amount"
                        ),
                        "observed_value": (
                            payment_refunds.iloc[
                                0
                            ][
                                "refund_amount"
                            ]
                        ),
                        "proposed_value": None,
                        "role": "REFUND_REFERENCE",
                    },
                    {
                        "source": "ledger",
                        "record_id": None,
                        "field": "amount",
                        "observed_value": None,
                        "proposed_value": None,
                        "role": (
                            "MISSING_REFUND_LEDGER_ENTRY"
                        ),
                    },
                ],
                relationship_type="MISSING_RECORD",
                claimed_delta=delta,
                direction="DECREASE",
            )
        )

    return hypotheses
# =========================================================
# Public dispatcher
# =========================================================

def generate_deterministic_hypotheses(
    controller_case: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Generate deterministic investigation hypotheses
    from the exception type.

    No payment IDs are hardcoded.

    No ground truth is consulted.

    Returns:
        list[dict]
    """

    reconciliation = (
        controller_case[
            "financial_facts"
        ][
            "reconciliation"
        ]
    )

    reason = str(
        reconciliation.get(
            "reason",
            "",
        )
    ).strip().upper()

    # -----------------------------------------------------
    # Deterministic exception routing
    # -----------------------------------------------------

    if (
        reason
        == "SETTLEMENT_AMOUNT_MISMATCH"
    ):
        return _settlement_or_upstream_mismatch(
            controller_case
        )

    if (
        reason
        == "MISSING_SETTLEMENT"
    ):
        return _missing_settlement(
            controller_case
        )

    if (
        reason
        == "FEE_MISMATCH"
    ):
        return _fee_mismatch(
            controller_case
        )

    if (
        reason
        == "REFUND_MISMATCH"
    ):
        return _refund_mismatch(
            controller_case
        )

    if (
        reason
        == "MISSING_LEDGER_ENTRY"
    ):
        return _missing_ledger_entry(
            controller_case
        )

    if (
        reason
        == "DUPLICATE_PAYMENT"
    ):
        return _duplicate_payment(
            controller_case
        )

    # -----------------------------------------------------
    # Ambiguous/conflicting cases deliberately fall through
    # to the AI investigator.
    # -----------------------------------------------------

    if (
        reason
        == "CONFLICTING_EVIDENCE"
    ):
        return _conflicting_evidence_fallback(
            controller_case
        )

    # -----------------------------------------------------
    # Unknown exception:
    # let AI investigate rather than inventing a rule.
    # -----------------------------------------------------

    return []