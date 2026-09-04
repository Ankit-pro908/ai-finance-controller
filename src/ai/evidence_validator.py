from typing import Any


ALLOWED_SOURCES = {
    "payment",
    "fee",
    "refund",
    "settlement",
    "ledger",
}


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


def _values_match(
    actual: Any,
    observed: Any,
) -> bool:
    """
    Compare two financial values using a small tolerance.
    """

    try:
        actual_value = float(actual)
        observed_value = float(observed)

    except (TypeError, ValueError):
        return False

    return (
        abs(
            actual_value
            - observed_value
        )
        <= 0.01
    )


def validate_supporting_evidence(
    hypothesis: dict[str, Any],
    evidence: dict,
) -> dict:
    """
    Validate the affected_records declared by one AI hypothesis.

    This validator checks whether:
    1. The cited source is valid.
    2. Existing record IDs actually exist.
    3. The cited field exists.
    4. The AI's observed_value matches the actual record.
    5. Missing-record claims are represented correctly.

    It does NOT determine whether the hypothesis itself is
    causally correct. That is the causal verifier's job.
    """

    affected_records = hypothesis.get(
        "affected_records",
        [],
    )

    if not isinstance(
        affected_records,
        list,
    ):
        raise ValueError(
            "Hypothesis affected_records "
            "must be a list."
        )

    validation_results = []

    # -----------------------------------------------------
    # Validate every affected record
    # -----------------------------------------------------

    for index, record_claim in enumerate(
        affected_records,
        start=1,
    ):

        if not isinstance(
            record_claim,
            dict,
        ):
            validation_results.append(
                {
                    "index": index,
                    "valid": False,
                    "reason": (
                        "AFFECTED_RECORD_MUST_BE_OBJECT"
                    ),
                }
            )

            continue

        source = str(
            record_claim.get(
                "source",
                "",
            )
        ).strip().lower()

        record_id = (
            record_claim.get(
                "record_id"
            )
        )

        if isinstance(
            record_id,
            str,
        ):
            record_id = record_id.strip()

            if not record_id:
                record_id = None

        field = str(
            record_claim.get(
                "field",
                "",
            )
        ).strip()

        observed_value = (
            record_claim.get(
                "observed_value"
            )
        )

        role = str(
            record_claim.get(
                "role",
                "",
            )
        ).strip()

        # -------------------------------------------------
        # Source validation
        # -------------------------------------------------

        if source not in ALLOWED_SOURCES:

            validation_results.append(
                {
                    "index": index,
                    "source": source,
                    "record_id": record_id,
                    "valid": False,
                    "reason": "UNKNOWN_SOURCE",
                }
            )

            continue

        dataframe = evidence[
            SOURCE_DATASETS[source]
        ]

        id_column = SOURCE_ID_COLUMNS[
            source
        ]

        # -------------------------------------------------
        # Field validation
        # -------------------------------------------------

        if not field:

            validation_results.append(
                {
                    "index": index,
                    "source": source,
                    "record_id": record_id,
                    "valid": False,
                    "reason": "FIELD_REQUIRED",
                }
            )

            continue

        # -------------------------------------------------
        # Missing-record claim
        # -------------------------------------------------

        if record_id is None:

            # A missing record must have no observed value.
            if observed_value is not None:

                validation_results.append(
                    {
                        "index": index,
                        "source": source,
                        "record_id": None,
                        "valid": False,
                        "reason": (
                            "MISSING_RECORD_CANNOT_HAVE_"
                            "OBSERVED_VALUE"
                        ),
                    }
                )

                continue

            # A missing record must have a meaningful role.
            if not role:

                validation_results.append(
                    {
                        "index": index,
                        "source": source,
                        "record_id": None,
                        "valid": False,
                        "reason": (
                            "MISSING_RECORD_ROLE_REQUIRED"
                        ),
                    }
                )

                continue

            # -------------------------------------------------
            # For ledger missing-entry claims, the AI should
            # be describing an absent ledger event.
            # We DO NOT use natural-language parsing to decide
            # whether it is true. We only validate that the
            # structure is a legitimate missing-record claim.
            #
            # Causal verification will determine whether
            # that missing event actually explains the delta.
            # -------------------------------------------------

            validation_results.append(
                {
                    "index": index,
                    "source": source,
                    "record_id": None,
                    "field": field,
                    "valid": True,
                    "reason": (
                        "MISSING_RECORD_CLAIM_ACCEPTED"
                    ),
                    "role": role,
                }
            )

            continue

        # -------------------------------------------------
        # Existing-record claim
        # -------------------------------------------------

        if id_column not in dataframe.columns:

            validation_results.append(
                {
                    "index": index,
                    "source": source,
                    "record_id": record_id,
                    "valid": False,
                    "reason": (
                        "ID_COLUMN_MISSING"
                    ),
                }
            )

            continue

        matching_rows = dataframe[
            dataframe[id_column]
            .astype(str)
            .eq(str(record_id))
        ]

        if matching_rows.empty:

            validation_results.append(
                {
                    "index": index,
                    "source": source,
                    "record_id": record_id,
                    "valid": False,
                    "reason": (
                        "RECORD_NOT_FOUND"
                    ),
                }
            )

            continue

        record = matching_rows.iloc[0]

        # -------------------------------------------------
        # Validate cited field exists
        # -------------------------------------------------

        if field not in dataframe.columns:

            validation_results.append(
                {
                    "index": index,
                    "source": source,
                    "record_id": record_id,
                    "valid": False,
                    "reason": (
                        "FIELD_NOT_FOUND"
                    ),
                }
            )

            continue

        # -------------------------------------------------
        # Observed value must be provided for an existing
        # financial record.
        # -------------------------------------------------

        if observed_value is None:

            validation_results.append(
                {
                    "index": index,
                    "source": source,
                    "record_id": record_id,
                    "valid": False,
                    "reason": (
                        "OBSERVED_VALUE_REQUIRED"
                    ),
                }
            )

            continue

        actual_value = record[field]

        # -------------------------------------------------
        # Numeric financial values
        # -------------------------------------------------

        if isinstance(
            observed_value,
            (int, float),
        ):

            if not _values_match(
                actual_value,
                observed_value,
            ):

                validation_results.append(
                    {
                        "index": index,
                        "source": source,
                        "record_id": record_id,
                        "field": field,
                        "valid": False,
                        "reason": (
                            "OBSERVED_VALUE_MISMATCH"
                        ),
                        "actual_value": actual_value,
                        "observed_value": (
                            observed_value
                        ),
                    }
                )

                continue

        else:

            # -------------------------------------------------
            # Non-numeric fields
            # -------------------------------------------------

            if str(actual_value) != str(
                observed_value
            ):

                validation_results.append(
                    {
                        "index": index,
                        "source": source,
                        "record_id": record_id,
                        "field": field,
                        "valid": False,
                        "reason": (
                            "OBSERVED_VALUE_MISMATCH"
                        ),
                        "actual_value": str(
                            actual_value
                        ),
                        "observed_value": str(
                            observed_value
                        ),
                    }
                )

                continue

        validation_results.append(
            {
                "index": index,
                "source": source,
                "record_id": record_id,
                "field": field,
                "valid": True,
                "reason": (
                    "RECORD_AND_VALUE_VALID"
                ),
                "actual_value": actual_value,
                "observed_value": (
                    observed_value
                ),
                "role": role,
            }
        )

    # -----------------------------------------------------
    # Overall validation
    # -----------------------------------------------------

    all_valid = (
        bool(validation_results)
        and all(
            result["valid"]
            for result in validation_results
        )
    )

    return {
        "all_citations_valid": all_valid,
        "validated_count": sum(
            result["valid"]
            for result in validation_results
        ),
        "total_citations": len(
            validation_results
        ),
        "validation_results": (
            validation_results
        ),
    }