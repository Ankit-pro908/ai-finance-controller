from typing import Any


# =========================================================
# Canonical enums
#
# This file is the single source of truth for the AI
# hypothesis response contract.
# =========================================================

ALLOWED_SOURCES = (
    "payment",
    "fee",
    "refund",
    "settlement",
    "ledger",
)

ALLOWED_RELATIONSHIP_TYPES = (
    "RECORD_DELTA",
    "MISSING_RECORD",
    "DUPLICATE_RECORD",
    "OTHER",
)

ALLOWED_DIRECTIONS = (
    "INCREASE",
    "DECREASE",
    "NEUTRAL",
    "UNKNOWN",
)


# Financial fields expected to contain numeric values.
NUMERIC_FIELDS = (
    "amount",
    "fee_amount",
    "refund_amount",
    "settlement_amount",
    "tax_amount",
    "proposed_value",
)


# =========================================================
# Human-readable schema
#
# Used by the prompt and for developer reference.
# This is NOT the API-enforced JSON Schema.
# =========================================================

AI_RESPONSE_SCHEMA = {
    "hypotheses": [
        {
            "hypothesis_id": "string",

            "root_cause": "string",

            "explanation": "string",

            "affected_records": [
                {
                    "source": "|".join(
                        ALLOWED_SOURCES
                    ),

                    "record_id": "string_or_null",

                    "field": "string",

                    "observed_value": (
                        "number_or_null"
                    ),

                    "proposed_value": (
                        "number_or_null"
                    ),

                    "role": "string",
                }
            ],

            "causal_relationship": {
                "type": "|".join(
                    ALLOWED_RELATIONSHIP_TYPES
                ),

                "claimed_delta": (
                    "number_or_null"
                ),

                "direction": "|".join(
                    ALLOWED_DIRECTIONS
                ),
            },
        }
    ]
}


# =========================================================
# Strict JSON Schema
#
# This is the schema sent to Groq.
#
# Important:
# - All properties are required.
# - additionalProperties is false.
# - testable/confidence are intentionally NOT part of
#   the AI response contract.
#
# Those values are not financial evidence and can be
# derived later by deterministic controller logic.
# =========================================================

AI_RESPONSE_JSON_SCHEMA: dict[str, Any] = {

    "type": "object",

    "properties": {

        "hypotheses": {

            "type": "array",

            "items": {

                "type": "object",

                "properties": {

                    "hypothesis_id": {
                        "type": "string"
                    },

                    "root_cause": {
                        "type": "string"
                    },

                    "explanation": {
                        "type": "string"
                    },

                    "affected_records": {

                        "type": "array",

                        "items": {

                            "type": "object",

                            "properties": {

                                "source": {
                                    "type": "string",
                                    "enum": list(
                                        ALLOWED_SOURCES
                                    ),
                                },

                                "record_id": {
                                    "type": [
                                        "string",
                                        "null",
                                    ]
                                },

                                "field": {
                                    "type": "string"
                                },

                                "observed_value": {
                                    "type": [
                                        "number",
                                        "null",
                                    ]
                                },

                                "proposed_value": {
                                    "type": [
                                        "number",
                                        "null",
                                    ]
                                },

                                "role": {
                                    "type": "string"
                                },
                            },

                            "required": [
                                "source",
                                "record_id",
                                "field",
                                "observed_value",
                                "proposed_value",
                                "role",
                            ],

                            "additionalProperties": False,
                        },
                    },

                    "causal_relationship": {

                        "type": "object",

                        "properties": {

                            "type": {
                                "type": "string",
                                "enum": list(
                                    ALLOWED_RELATIONSHIP_TYPES
                                ),
                            },

                            "claimed_delta": {
                                "type": [
                                    "number",
                                    "null",
                                ]
                            },

                            "direction": {
                                "type": "string",
                                "enum": list(
                                    ALLOWED_DIRECTIONS
                                ),
                            },
                        },

                        "required": [
                            "type",
                            "claimed_delta",
                            "direction",
                        ],

                        "additionalProperties": False,
                    },
                },

                "required": [
                    "hypothesis_id",
                    "root_cause",
                    "explanation",
                    "affected_records",
                    "causal_relationship",
                ],

                "additionalProperties": False,
            },
        }
    },

    "required": [
        "hypotheses"
    ],

    "additionalProperties": False,
}


# =========================================================
# Prompt schema-rules helper
#
# investigator.py can use this instead of maintaining
# another copy of the allowed enums.
# =========================================================

def _bullet_list(
    values: tuple[str, ...],
) -> str:

    return "\n".join(
        f"- {value}"
        for value in values
    )


def build_schema_rules_block() -> str:
    """
    Render canonical enum values for the AI prompt.
    """

    return f"""
Allowed source values:

{_bullet_list(ALLOWED_SOURCES)}

Allowed causal relationship types:

{_bullet_list(ALLOWED_RELATIONSHIP_TYPES)}

Allowed directions:

{_bullet_list(ALLOWED_DIRECTIONS)}
""".strip()