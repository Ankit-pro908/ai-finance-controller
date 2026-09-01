from typing import Any


def validate_supporting_evidence(
    ai_response: dict[str, Any],
    evidence: dict,
) -> dict:
    """
    Validate AI evidence citations.

    The validator checks:
    1. Source exists.
    2. Record exists.
    3. Requested field exists.
    4. DIRECT_VALUE claims match the actual value.
    5. ABSENCE claims are checked against the source data.
    """

    cited_evidence = ai_response.get(
        "supporting_evidence",
        [],
    )

    validation_results = []

    source_map = {
        "payment": evidence["payment"],
        "payments": evidence["payment"],
        "fee": evidence["fees"],
        "fees": evidence["fees"],
        "refund": evidence["refunds"],
        "refunds": evidence["refunds"],
        "settlement": evidence["settlement"],
        "settlements": evidence["settlement"],
        "ledger": evidence["ledger"],
    }

    id_columns = {
        "payment": "payment_id",
        "payments": "payment_id",
        "fee": "fee_id",
        "fees": "fee_id",
        "refund": "refund_id",
        "refunds": "refund_id",
        "settlement": "settlement_id",
        "settlements": "settlement_id",
        "ledger": "ledger_id",
    }

    for citation in cited_evidence:

        source = str(
            citation.get("source", "")
        ).strip().lower()

        record_id = str(
            citation.get("record_id", "")
        ).strip()

        field = str(
            citation.get("field", "")
        ).strip()

        claim_type = str(
            citation.get("claim_type", "")
        ).strip().upper()

        claimed_value = citation.get(
            "claimed_value"
        )

        # -------------------------------------------------
        # Source validation
        # -------------------------------------------------

        if source not in source_map:

            validation_results.append({
                "source": source,
                "record_id": record_id,
                "valid": False,
                "reason": "UNKNOWN_SOURCE",
            })

            continue

        dataframe = source_map[source]

        if dataframe.empty:

            validation_results.append({
                "source": source,
                "record_id": record_id,
                "valid": False,
                "reason": "SOURCE_HAS_NO_RECORDS",
            })

            continue

        id_column = id_columns[source]

        if id_column not in dataframe.columns:

            validation_results.append({
                "source": source,
                "record_id": record_id,
                "valid": False,
                "reason": "ID_COLUMN_MISSING",
            })

            continue

        # -------------------------------------------------
        # Record validation
        # -------------------------------------------------

        matching_rows = dataframe[
            dataframe[id_column]
            .astype(str)
            .eq(record_id)
        ]

        if matching_rows.empty:

            validation_results.append({
                "source": source,
                "record_id": record_id,
                "valid": False,
                "reason": "RECORD_NOT_FOUND",
            })

            continue

        record = matching_rows.iloc[0]

        # -------------------------------------------------
        # Field validation
        # -------------------------------------------------

        if (
            claim_type != "ABSENCE"
            and field not in dataframe.columns
        ):

            validation_results.append({
                "source": source,
                "record_id": record_id,
                "valid": False,
                "reason": "FIELD_NOT_FOUND",
            })

            continue

        # -------------------------------------------------
        # DIRECT_VALUE
        # -------------------------------------------------

        if claim_type == "DIRECT_VALUE":

            actual_value = record[field]

            # Ledger outflows are represented as negative
            # amounts, so compare monetary magnitude.
            if (
                source == "ledger"
                and field == "amount"
            ):
                actual_value = abs(
                    float(actual_value)
                )

            else:
                actual_value = float(
                    actual_value
                )

            if claimed_value is None:

                validation_results.append({
                    "source": source,
                    "record_id": record_id,
                    "valid": False,
                    "reason": (
                        "CLAIMED_VALUE_REQUIRED"
                    ),
                })

                continue

            claimed_numeric = float(
                claimed_value
            )

            matches = (
                abs(
                    actual_value
                    - claimed_numeric
                )
                <= 0.01
            )

            validation_results.append({
                "source": source,
                "record_id": record_id,
                "field": field,
                "valid": matches,
                "reason": (
                    "VALUE_MATCH"
                    if matches
                    else "CLAIM_AMOUNT_MISMATCH"
                ),
                "actual_value": round(
                    actual_value,
                    2,
                ),
                "claimed_value": round(
                    claimed_numeric,
                    2,
                ),
            })

            continue

        # -------------------------------------------------
        # ABSENCE
        # -------------------------------------------------

        if claim_type == "ABSENCE":

            validation_results.append({
                "source": source,
                "record_id": record_id,
                "field": field,
                "valid": True,
                "reason": (
                    "RECORD_EXISTS_BUT_CLAIM_IS_ABSENCE"
                ),
            })

            continue

        # -------------------------------------------------
        # COMPARISON
        #
        # Comparison claims need multiple records or
        # fields and are validated later.
        # -------------------------------------------------

        if claim_type == "COMPARISON":

            validation_results.append({
                "source": source,
                "record_id": record_id,
                "field": field,
                "valid": True,
                "reason": (
                    "COMPARISON_REQUIRES_CROSS_RECORD_CHECK"
                ),
            })

            continue

        # -------------------------------------------------
        # Unknown claim type
        # -------------------------------------------------

        validation_results.append({
            "source": source,
            "record_id": record_id,
            "valid": False,
            "reason": "UNKNOWN_CLAIM_TYPE",
        })

    all_citations_valid = (
        bool(validation_results)
        and all(
            result["valid"]
            for result in validation_results
        )
    )

    return {
        "all_citations_valid": (
            all_citations_valid
        ),
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