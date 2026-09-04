from typing import Any


TOLERANCE = 0.01


SOURCE_DATASETS = {
    "payment": "payment",
    "fee": "fees",
    "refund": "refunds",
    "settlement": "settlement",
    "ledger": "ledger",
}


SOURCE_ID_COLUMNS = {
    "payment": "payment_id",
    "fee": "fee_id",
    "refund": "refund_id",
    "settlement": "settlement_id",
    "ledger": "ledger_id",
}


def _to_float(value: Any) -> float:
    return float(value)


def _close(
    first: float,
    second: float,
) -> bool:
    return (
        abs(first - second)
        <= TOLERANCE
    )


def _get_dataframe(
    controller_case: dict[str, Any],
    source: str,
):
    evidence = controller_case["evidence"]

    dataset_name = SOURCE_DATASETS[source]

    return evidence[dataset_name]


def _get_record_value(
    controller_case: dict[str, Any],
    source: str,
    record_id: str,
    field: str,
):
    dataframe = _get_dataframe(
        controller_case,
        source,
    )

    id_column = SOURCE_ID_COLUMNS[source]

    if dataframe.empty:
        return {
            "found": False,
            "reason": "SOURCE_EMPTY",
        }

    if id_column not in dataframe.columns:
        return {
            "found": False,
            "reason": "ID_COLUMN_MISSING",
        }

    if field not in dataframe.columns:
        return {
            "found": False,
            "reason": "FIELD_NOT_FOUND",
        }

    rows = dataframe[
        dataframe[id_column]
        .astype(str)
        .eq(str(record_id))
    ]

    if rows.empty:
        return {
            "found": False,
            "reason": "RECORD_NOT_FOUND",
        }

    record = rows.iloc[0]

    return {
        "found": True,
        "value": record[field],
    }


def _get_observed_reconciliation_difference(
    controller_case: dict[str, Any],
) -> float | None:

    reconciliation = controller_case[
        "financial_facts"
    ]["reconciliation"]

    value = reconciliation.get(
        "difference"
    )

    if value is None:
        return None

    return _to_float(value)


def _verify_record_delta(
    hypothesis: dict[str, Any],
    controller_case: dict[str, Any],
) -> dict[str, Any]:
    """
    Verify a RECORD_DELTA hypothesis.

    Supports:
        1. A single existing record being corrected.
        2. Multiple existing records where one or more records
           are cited as supporting evidence.

    The proposed_value is the hypothetical counterfactual.
    The verifier checks that the proposed financial change
    is consistent with the observed reconciliation discrepancy.

    No ground truth is consulted.
    """

    affected_records = hypothesis.get(
        "affected_records",
        [],
    )

    if not affected_records:
        return {
            "status": "UNVERIFIABLE",
            "reason": (
                "RECORD_DELTA requires at least "
                "one affected existing record."
            ),
        }

    actual_records = []
    proposed_changes = []

    # ---------------------------------------------------------
    # Validate and retrieve every cited existing record
    # ---------------------------------------------------------

    for index, affected_record in enumerate(
        affected_records,
        start=1,
    ):

        source = affected_record.get(
            "source"
        )

        record_id = affected_record.get(
            "record_id"
        )

        field = affected_record.get(
            "field"
        )

        if not source:
            return {
                "status": "REJECTED",
                "reason": (
                    f"Affected record {index} "
                    "does not specify a source."
                ),
            }

        if record_id is None:
            return {
                "status": "REJECTED",
                "reason": (
                    f"Affected record {index} "
                    "does not have a record ID."
                ),
            }

        if not field:
            return {
                "status": "REJECTED",
                "reason": (
                    f"Affected record {index} "
                    "does not specify a field."
                ),
            }

        result = _get_record_value(
            controller_case,
            source,
            record_id,
            field,
        )

        if not result["found"]:
            return {
                "status": "REJECTED",
                "reason": (
                    f"Could not retrieve "
                    f"{source}/{record_id}/{field}: "
                    f"{result['reason']}"
                ),
            }

        actual_value = result["value"]

        actual_records.append(
            {
                "source": source,
                "record_id": record_id,
                "field": field,
                "value": actual_value,
            }
        )

        # -----------------------------------------------------
        # Proposed counterfactual change
        # -----------------------------------------------------

        proposed_value = affected_record.get(
            "proposed_value"
        )

        if proposed_value is not None:

            try:

                observed_numeric = _to_float(
                    actual_value
                )

                proposed_numeric = _to_float(
                    proposed_value
                )

            except (TypeError, ValueError):

                return {
                    "status": "REJECTED",
                    "reason": (
                        f"Proposed change for "
                        f"{source}/{record_id}/{field} "
                        "is not numeric."
                    ),
                    "records": actual_records,
                }

            change = round(
                proposed_numeric
                - observed_numeric,
                2,
            )

            proposed_changes.append(
                {
                    "source": source,
                    "record_id": record_id,
                    "field": field,
                    "observed_value": observed_numeric,
                    "proposed_value": proposed_numeric,
                    "change": change,
                }
            )

    # ---------------------------------------------------------
    # A RECORD_DELTA must contain at least one proposed change
    # ---------------------------------------------------------

    if not proposed_changes:
        return {
            "status": "UNVERIFIABLE",
            "reason": (
                "RECORD_DELTA requires at least one "
                "existing record with a proposed_value."
            ),
            "records": actual_records,
        }

    # ---------------------------------------------------------
    # Observed reconciliation discrepancy
    # ---------------------------------------------------------

    observed_difference = (
        _get_observed_reconciliation_difference(
            controller_case
        )
    )

    if observed_difference is None:

        return {
            "status": "UNVERIFIABLE",
            "reason": (
                "Observed reconciliation difference "
                "is unavailable."
            ),
            "records": actual_records,
        }

    observed_magnitude = abs(
        observed_difference
    )

    # ---------------------------------------------------------
    # Determine counterfactual financial delta
    #
    # For the normal case of one proposed change, this is
    # simply proposed - observed.
    #
    # For multiple proposed changes, use the total magnitude
    # of the individual changes. The final financial decision
    # still requires counterfactual simulation.
    # ---------------------------------------------------------

    if len(proposed_changes) == 1:

        counterfactual_delta = abs(
            proposed_changes[0][
                "change"
            ]
        )

    else:

        counterfactual_delta = round(
            sum(
                abs(
                    change["change"]
                )
                for change in proposed_changes
            ),
            2,
        )

    # ---------------------------------------------------------
    # Claimed delta
    # ---------------------------------------------------------

    causal_relationship = hypothesis.get(
        "causal_relationship",
        {},
    )

    claimed_delta = causal_relationship.get(
        "claimed_delta"
    )

    if claimed_delta is None:

        return {
            "status": "UNVERIFIABLE",
            "reason": (
                "Hypothesis did not specify "
                "a claimed delta."
            ),
            "records": actual_records,
            "counterfactual_delta": (
                counterfactual_delta
            ),
            "observed_difference": (
                observed_difference
            ),
        }

    try:

        claimed_delta_numeric = _to_float(
            claimed_delta
        )

    except (TypeError, ValueError):

        return {
            "status": "REJECTED",
            "reason": (
                "Hypothesis claimed_delta "
                "is not numeric."
            ),
            "records": actual_records,
            "counterfactual_delta": (
                counterfactual_delta
            ),
            "observed_difference": (
                observed_difference
            ),
        }

    claimed_delta_magnitude = abs(
        claimed_delta_numeric
    )

    # ---------------------------------------------------------
    # Consistency checks
    # ---------------------------------------------------------

    counterfactual_delta_matches_observed = (
        _close(
            counterfactual_delta,
            observed_magnitude,
        )
    )

    claimed_delta_matches_observed = (
        _close(
            claimed_delta_magnitude,
            observed_magnitude,
        )
    )

    claimed_delta_matches_counterfactual = (
        _close(
            claimed_delta_magnitude,
            counterfactual_delta,
        )
    )

    checks = {
        "counterfactual_delta_matches_observed": (
            counterfactual_delta_matches_observed
        ),
        "claimed_delta_matches_observed": (
            claimed_delta_matches_observed
        ),
        "claimed_delta_matches_counterfactual": (
            claimed_delta_matches_counterfactual
        ),
    }

    # ---------------------------------------------------------
    # Financially coherent candidate
    #
    # This does NOT prove the hypothesis.
    # The orchestrator still runs counterfactual simulation.
    # ---------------------------------------------------------

    if all(checks.values()):

        return {
            "status": "CAUSAL_CANDIDATE",
            "reason": (
                "The proposed counterfactual change "
                "matches the observed reconciliation "
                "discrepancy. Counterfactual simulation "
                "is required before causal support can "
                "be established."
            ),
            "records": actual_records,
            "proposed_changes": proposed_changes,
            "counterfactual_delta": (
                counterfactual_delta
            ),
            "record_delta": (
                counterfactual_delta
            ),
            "claimed_delta": (
                claimed_delta_numeric
            ),
            "observed_difference": (
                observed_difference
            ),
            "checks": checks,
        }

    # ---------------------------------------------------------
    # Not financially supported
    # ---------------------------------------------------------

    return {
        "status": "NOT_SUPPORTED",
        "reason": (
            "The proposed counterfactual change and "
            "claimed delta do not consistently explain "
            "the observed reconciliation discrepancy."
        ),
        "records": actual_records,
        "proposed_changes": proposed_changes,
        "counterfactual_delta": (
            counterfactual_delta
        ),
        "record_delta": (
            counterfactual_delta
        ),
        "claimed_delta": (
            claimed_delta_numeric
        ),
        "observed_difference": (
            observed_difference
        ),
        "checks": checks,
    }

def _verify_missing_record(
    hypothesis: dict[str, Any],
    controller_case: dict[str, Any],
) -> dict[str, Any]:
    affected_records = hypothesis[
        "affected_records"
    ]

    if not affected_records:
        return {
            "status": "UNVERIFIABLE",
            "reason": (
                "Missing-record hypothesis does not "
                "identify the missing event."
            ),
        }

    for record in affected_records:

        if record["record_id"] is not None:
            return {
                "status": "REJECTED",
                "reason": (
                    "MISSING_RECORD hypothesis contains "
                    "an existing record ID."
                ),
            }

        if record["observed_value"] is not None:
            return {
                "status": "REJECTED",
                "reason": (
                    "MISSING_RECORD hypothesis contains "
                    "an observed value."
                ),
            }

    claimed_delta = (
        hypothesis[
            "causal_relationship"
        ].get("claimed_delta")
    )

    observed_difference = (
        _get_observed_reconciliation_difference(
            controller_case
        )
    )

    if claimed_delta is None:

        return {
            "status": "PENDING_SIMULATION",
            "reason": (
                "Missing event is structurally "
                "identified, but its financial impact "
                "has not yet been proven."
            ),
            "observed_difference": (
                observed_difference
            ),
        }

    claimed_delta = _to_float(
        claimed_delta
    )

    if observed_difference is None:

        return {
            "status": "UNVERIFIABLE",
            "reason": (
                "Observed reconciliation difference "
                "is unavailable."
            ),
        }

    # claimed_delta is a magnitude, not a signed value --
    # the AI frequently copies the signed reconciliation
    # 'difference' verbatim, so compare magnitudes here too
    # (consistent with _verify_record_delta above).
    if _close(
        abs(claimed_delta),
        abs(observed_difference),
    ):

        return {
            "status": "PENDING_SIMULATION",
            "reason": (
                "The missing-record hypothesis "
                "claims a delta matching the "
                "observed discrepancy, but the "
                "financial effect still requires "
                "simulation."
            ),
            "claimed_delta": claimed_delta,
            "observed_difference": (
                observed_difference
            ),
        }

    return {
        "status": "NOT_SUPPORTED",
        "reason": (
            "The missing-record hypothesis claims "
            "a delta that does not match the "
            "observed discrepancy."
        ),
        "claimed_delta": claimed_delta,
        "observed_difference": (
            observed_difference
        ),
    }


def _verify_duplicate_record(
    hypothesis: dict[str, Any],
    controller_case: dict[str, Any],
) -> dict[str, Any]:
    affected_records = hypothesis[
        "affected_records"
    ]

    if len(affected_records) < 2:
        return {
            "status": "UNVERIFIABLE",
            "reason": (
                "DUPLICATE_RECORD requires at least "
                "two affected records."
            ),
        }

    verified_records = []

    for record in affected_records:

        source = record[
            "source"
        ]

        record_id = record[
            "record_id"
        ]

        field = record[
            "field"
        ]

        if record_id is None:
            return {
                "status": "REJECTED",
                "reason": (
                    "Duplicate hypothesis contains "
                    "a missing record ID."
                ),
            }

        result = _get_record_value(
            controller_case,
            source,
            record_id,
            field,
        )

        if not result["found"]:
            return {
                "status": "REJECTED",
                "reason": (
                    f"Duplicate record "
                    f"{source}/{record_id} "
                    "could not be verified."
                ),
            }

        verified_records.append(
            {
                "source": source,
                "record_id": record_id,
                "field": field,
                "value": result["value"],
            }
        )

    return {
        "status": "PENDING_DUPLICATE_VERIFICATION",
        "reason": (
            "All cited records exist. "
            "Duplicate-event identity requires "
            "relationship verification."
        ),
        "records": verified_records,
    }


def verify_hypothesis(
    hypothesis: dict[str, Any],
    controller_case: dict[str, Any],
) -> dict[str, Any]:
    causal_relationship = hypothesis.get(
        "causal_relationship",
        {},
    )

    relationship_type = str(
        causal_relationship.get(
            "type",
            "",
        )
    ).strip().upper()

    if relationship_type == "RECORD_DELTA":

        return _verify_record_delta(
            hypothesis,
            controller_case,
        )

    if relationship_type == "MISSING_RECORD":

        return _verify_missing_record(
            hypothesis,
            controller_case,
        )

    if relationship_type == "DUPLICATE_RECORD":

        return _verify_duplicate_record(
            hypothesis,
            controller_case,
        )

    return {
        "status": "UNVERIFIABLE",
        "reason": (
            "No deterministic verification rule "
            "has been defined for relationship type "
            f"'{relationship_type}'."
        ),
    }