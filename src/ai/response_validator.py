from typing import Any


# =========================================================
# Allowed values
# =========================================================

ALLOWED_SOURCES = {
    "payment",
    "fee",
    "refund",
    "settlement",
    "ledger",
}


ALLOWED_RELATIONSHIP_TYPES = {
    "RECORD_DELTA",
    "MISSING_RECORD",
    "DUPLICATE_RECORD",
    "OTHER",
}


ALLOWED_DIRECTIONS = {
    "INCREASE",
    "DECREASE",
    "NEUTRAL",
    "UNKNOWN",
}


# Financial fields expected to contain numeric values.
NUMERIC_FIELDS = {
    "amount",
    "fee_amount",
    "refund_amount",
    "settlement_amount",
    "tax_amount",
    "proposed_value",
}


# =========================================================
# Helper functions
# =========================================================

def _normalize_record_id(
    value: Any,
) -> str | None:
    """
    Normalize a record ID.

    None, empty strings, "none", and "null" represent
    an intentionally missing record ID.
    """

    if value is None:
        return None

    if isinstance(value, str):

        cleaned = value.strip()

        if cleaned.lower() in {
            "",
            "none",
            "null",
        }:
            return None

        return cleaned

    return str(value)


def _normalize_numeric_value(
    value: Any,
) -> float | None:
    """
    Accept numbers and numeric strings.

    Examples:
        250.0       -> 250.0
        "250.0"     -> 250.0
        None        -> None
    """

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            "Boolean is not a valid numeric value."
        )

    if isinstance(
        value,
        (int, float),
    ):
        return float(value)

    if isinstance(
        value,
        str,
    ):

        cleaned = value.strip()

        if not cleaned:
            return None

        try:
            return float(cleaned)

        except ValueError as error:
            raise ValueError(
                f"Expected numeric value, got '{value}'."
            ) from error

    raise ValueError(
        f"Expected numeric value, got "
        f"{type(value).__name__}."
    )


def _normalize_observed_value(
    field: str,
    value: Any,
) -> Any:
    """
    Normalize an observed financial value according to
    the field type.
    """

    if value is None:
        return None

    if field in NUMERIC_FIELDS:
        return _normalize_numeric_value(
            value
        )

    if isinstance(value, str):
        return value.strip()

    return str(value).strip()


# =========================================================
# Main validator
# =========================================================

def validate_ai_response(
    response: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate and normalize an AI hypothesis response.

    IMPORTANT:

    This validator checks whether the AI response is
    structurally and semantically well-formed.

    It does NOT decide whether a hypothesis is financially
    correct.

    Financial correctness belongs to the causal verifier.
    """

    # -----------------------------------------------------
    # Top-level response
    # -----------------------------------------------------

    if not isinstance(
        response,
        dict,
    ):
        raise ValueError(
            "AI response must be a dictionary."
        )

    if "hypotheses" not in response:
        raise ValueError(
            "AI response must contain 'hypotheses'."
        )

    hypotheses = response[
        "hypotheses"
    ]

    if not isinstance(
        hypotheses,
        list,
    ):
        raise ValueError(
            "'hypotheses' must be a list."
        )

    validated_hypotheses = []

    seen_ids = set()

    # -----------------------------------------------------
    # Hypothesis loop
    # -----------------------------------------------------

    for index, hypothesis in enumerate(
        hypotheses,
        start=1,
    ):

        if not isinstance(
            hypothesis,
            dict,
        ):
            raise ValueError(
                f"Hypothesis {index} must be a dictionary."
            )

        required_fields = [
            "hypothesis_id",
            "root_cause",
            "explanation",
            "affected_records",
            "causal_relationship",
        ]


        missing_fields = [
            field
            for field in required_fields
            if field not in hypothesis
        ]

        if missing_fields:

            raise ValueError(
                f"Hypothesis {index} is missing "
                f"fields: {missing_fields}"
            )

        # -------------------------------------------------
        # Hypothesis ID
        # -------------------------------------------------

        hypothesis_id = str(
            hypothesis[
                "hypothesis_id"
            ]
        ).strip()

        if not hypothesis_id:

            raise ValueError(
                f"Hypothesis {index}: "
                "hypothesis_id cannot be empty."
            )

        if hypothesis_id in seen_ids:

            raise ValueError(
                f"Duplicate hypothesis_id: "
                f"{hypothesis_id}"
            )

        seen_ids.add(
            hypothesis_id
        )

        # -------------------------------------------------
        # Root cause
        # -------------------------------------------------

        root_cause = hypothesis[
            "root_cause"
        ]

        if not isinstance(
            root_cause,
            str,
        ):

            raise ValueError(
                f"Hypothesis {hypothesis_id}: "
                "root_cause must be a string."
            )

        root_cause = root_cause.strip()

        if not root_cause:

            raise ValueError(
                f"Hypothesis {hypothesis_id}: "
                "root_cause cannot be empty."
            )

        # -------------------------------------------------
        # Explanation
        # -------------------------------------------------

        explanation = hypothesis[
            "explanation"
        ]

        if not isinstance(
            explanation,
            str,
        ):

            raise ValueError(
                f"Hypothesis {hypothesis_id}: "
                "explanation must be a string."
            )

        explanation = explanation.strip()

        if not explanation:

            raise ValueError(
                f"Hypothesis {hypothesis_id}: "
                "explanation cannot be empty."
            )

        # -------------------------------------------------
        # Affected records
        # -------------------------------------------------

        affected_records = hypothesis[
            "affected_records"
        ]

        if not isinstance(
            affected_records,
            list,
        ):

            raise ValueError(
                f"Hypothesis {hypothesis_id}: "
                "affected_records must be a list."
            )

        validated_records = []

        for record_index, record in enumerate(
            affected_records,
            start=1,
        ):

            if not isinstance(
                record,
                dict,
            ):

                raise ValueError(
                    f"Hypothesis {hypothesis_id}: "
                    f"affected record {record_index} "
                    "must be a dictionary."
                )

            required_record_fields = [
                "source",
                "record_id",
                "field",
                "observed_value",
                "proposed_value",
                "role",
            ]

            missing_record_fields = [
                field
                for field in required_record_fields
                if field not in record
            ]

            if missing_record_fields:

                raise ValueError(
                    f"Hypothesis {hypothesis_id}: "
                    f"affected record {record_index} "
                    f"is missing fields: "
                    f"{missing_record_fields}"
                )

            source = str(
                record[
                    "source"
                ]
            ).strip().lower()

            record_id = (
                _normalize_record_id(
                    record[
                        "record_id"
                    ]
                )
            )

            field = str(
                record[
                    "field"
                ]
            ).strip()

            observed_value = (
                record[
                    "observed_value"
                ]
            )

            proposed_value = (
                record[
                    "proposed_value"
                ]
            )

            role = str(
                record[
                    "role"
                ]
            ).strip()

            # ---------------------------------------------
            # Source
            # ---------------------------------------------

            if source not in ALLOWED_SOURCES:

                raise ValueError(
                    f"Hypothesis {hypothesis_id}: "
                    f"invalid source '{source}'. "
                    f"Allowed sources: "
                    f"{sorted(ALLOWED_SOURCES)}"
                )

            # ---------------------------------------------
            # Field
            # ---------------------------------------------

            if not field:

                raise ValueError(
                    f"Hypothesis {hypothesis_id}: "
                    f"affected record {record_index}: "
                    "field cannot be empty."
                )

            # ---------------------------------------------
            # Role
            # ---------------------------------------------

            if not role:

                raise ValueError(
                    f"Hypothesis {hypothesis_id}: "
                    f"affected record {record_index}: "
                    "role cannot be empty."
                )

            # ---------------------------------------------
            # Existing vs missing record
            # ---------------------------------------------

            if record_id is None:

                # A missing record cannot have an observed
                # value because it does not exist.

                if observed_value is not None:

                    raise ValueError(
                        f"Hypothesis {hypothesis_id}: "
                        f"affected record {record_index}: "
                        "missing record cannot have "
                        "an observed_value."
                    )

            else:

                # Existing records must provide the observed
                # value that was actually seen.

                if observed_value is None:

                    raise ValueError(
                        f"Hypothesis {hypothesis_id}: "
                        f"affected record {record_index}: "
                        "existing record must have "
                        "an observed_value."
                    )

                observed_value = (
                    _normalize_observed_value(
                        field,
                        observed_value,
                    )
                )

            # ---------------------------------------------
            # Proposed value
            # ---------------------------------------------

            if proposed_value is not None:

                if field in NUMERIC_FIELDS:

                    proposed_value = (
                        _normalize_numeric_value(
                            proposed_value
                        )
                    )

                else:

                    if isinstance(
                        proposed_value,
                        str,
                    ):
                        proposed_value = (
                            proposed_value.strip()
                        )

                    else:
                        proposed_value = str(
                            proposed_value
                        ).strip()

            # ---------------------------------------------
            # Missing records cannot currently receive a
            # proposed direct value. Creation simulation
            # will later use an explicit event structure.
            # ---------------------------------------------

            if (
                record_id is None
                and proposed_value is not None
            ):

                raise ValueError(
                    f"Hypothesis {hypothesis_id}: "
                    f"affected record {record_index}: "
                    "missing records must use "
                    "proposed_value=None."
                )

            validated_records.append(
                {
                    "source": source,
                    "record_id": record_id,
                    "field": field,
                    "observed_value": (
                        observed_value
                    ),
                    "proposed_value": (
                        proposed_value
                    ),
                    "role": role,
                }
            )

        # -------------------------------------------------
        # Causal relationship
        # -------------------------------------------------

        causal_relationship = (
            hypothesis[
                "causal_relationship"
            ]
        )

        if not isinstance(
            causal_relationship,
            dict,
        ):

            raise ValueError(
                f"Hypothesis {hypothesis_id}: "
                "causal_relationship must be "
                "a dictionary."
            )

        relationship_fields = [
            "type",
            "claimed_delta",
            "direction",
        ]

        missing_relationship_fields = [
            field
            for field in relationship_fields
            if field not in causal_relationship
        ]

        if missing_relationship_fields:

            raise ValueError(
                f"Hypothesis {hypothesis_id}: "
                "causal_relationship is missing "
                f"fields: {missing_relationship_fields}"
            )

        relationship_type = str(
            causal_relationship[
                "type"
            ]
        ).strip().upper()

        if (
            relationship_type
            not in ALLOWED_RELATIONSHIP_TYPES
        ):

            raise ValueError(
                f"Hypothesis {hypothesis_id}: "
                f"invalid relationship type "
                f"'{relationship_type}'. "
                f"Allowed types: "
                f"{sorted(ALLOWED_RELATIONSHIP_TYPES)}"
            )

        direction = str(
            causal_relationship[
                "direction"
            ]
        ).strip().upper()

        if direction not in ALLOWED_DIRECTIONS:

            raise ValueError(
                f"Hypothesis {hypothesis_id}: "
                f"invalid direction "
                f"'{direction}'. "
                f"Allowed directions: "
                f"{sorted(ALLOWED_DIRECTIONS)}"
            )

        claimed_delta = (
            causal_relationship[
                "claimed_delta"
            ]
        )

        if claimed_delta is not None:

            claimed_delta = (
                _normalize_numeric_value(
                    claimed_delta
                )
            )

        # -------------------------------------------------
        # Relationship-specific semantics
        # -------------------------------------------------

        if relationship_type == "RECORD_DELTA":

            if not validated_records:

                raise ValueError(
                    f"Hypothesis {hypothesis_id}: "
                    "RECORD_DELTA requires at least "
                    "one affected records."
                )

            # Every RECORD_DELTA record must already exist.
            for record_index, record in enumerate(
                validated_records,
                start=1,
            ):

                if record["record_id"] is None:

                    raise ValueError(
                        f"Hypothesis {hypothesis_id}: "
                        f"affected record {record_index}: "
                        "RECORD_DELTA requires "
                        "real record IDs."
                    )

            # At least one existing record must have a
            # proposed correction for simulation.
            proposed_records = [
                record
                for record in validated_records
                if record["proposed_value"] is not None
            ]

            if not proposed_records:

                raise ValueError(
                    f"Hypothesis {hypothesis_id}: "
                    "RECORD_DELTA requires at least one "
                    "existing record with a proposed_value."
                )

        elif relationship_type == "MISSING_RECORD":

            if not validated_records:

                raise ValueError(
                    f"Hypothesis {hypothesis_id}: "
                    "MISSING_RECORD requires at least "
                    "one affected record."
                )

            for record_index, record in enumerate(
                validated_records,
                start=1,
            ):

                if record["record_id"] is not None:

                    raise ValueError(
                        f"Hypothesis {hypothesis_id}: "
                        f"affected record {record_index}: "
                        "MISSING_RECORD requires "
                        "record_id=None."
                    )

                if record["observed_value"] is not None:

                    raise ValueError(
                        f"Hypothesis {hypothesis_id}: "
                        f"affected record {record_index}: "
                        "MISSING_RECORD requires "
                        "observed_value=None."
                    )

                if (
                    "MISSING"
                    not in record["role"].upper()
                    and
                    "ABSENCE"
                    not in record["role"].upper()
                ):

                    raise ValueError(
                        f"Hypothesis {hypothesis_id}: "
                        f"affected record {record_index}: "
                        "MISSING_RECORD requires a role "
                        "that identifies the missing event."
                    )

        elif relationship_type == "DUPLICATE_RECORD":

            if len(validated_records) < 2:

                raise ValueError(
                    f"Hypothesis {hypothesis_id}: "
                    "DUPLICATE_RECORD requires at least "
                    "two affected records."
                )

            for record_index, record in enumerate(
                validated_records,
                start=1,
            ):

                if record["record_id"] is None:

                    raise ValueError(
                        f"Hypothesis {hypothesis_id}: "
                        f"affected record {record_index}: "
                        "DUPLICATE_RECORD requires "
                        "real record IDs."
                    )


        # -------------------------------------------------
        # Store normalized hypothesis
        # -------------------------------------------------

        validated_hypotheses.append(
            {
                "hypothesis_id": hypothesis_id,

                "root_cause": root_cause,

                "explanation": explanation,

                "affected_records": (
                    validated_records
                ),

                "causal_relationship": {
                    "type": relationship_type,
                    "claimed_delta": (
                        claimed_delta
                    ),
                    "direction": direction,
                },
            }
        )

    # -----------------------------------------------------
    # Final normalized response
    # -----------------------------------------------------

    return {
        "hypotheses": validated_hypotheses
    }