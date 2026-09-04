from pathlib import Path
import json
import pandas as pd
import sys
from typing import Any


# =========================================================
# Make project root importable when this file is executed
# directly.
#
# Example:
#     python src/ai/investigator.py
# =========================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent.parent
)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


# =========================================================
# Project imports
# =========================================================

from src.ai.client import call_groq

from src.ai.response_validator import (
    validate_ai_response,
)

from src.ai.response_schema import (
    build_schema_rules_block,
)

from src.ai.evidence_validator import (
    validate_supporting_evidence,
)

from src.evidence.retriever import (
    load_exception_data,
    retrieve_payment_evidence,
)

from src.evidence.completeness import (
    calculate_evidence_completeness,
)

from src.evidence.consistency import (
    check_evidence_consistency,
)

from src.controller.case import (
    build_controller_case,
)

from src.reconciliation.engine import (
    build_payment_view,
    calculate_expected_settlement,
    classify_reconciliation,
    identify_exception_reason,
    validate_ledger,
    build_exception_report,
)


# =========================================================
# Prompt value serialization
# =========================================================

def _json_default(
    value: Any,
) -> Any:
    """
    Convert NumPy/Pandas scalar values into ordinary
    Python values so the AI prompt never receives
    representations such as:

        np.float64(500.0)
        np.True_

    """

    try:
        import numpy as np

        if isinstance(
            value,
            np.generic,
        ):
            return value.item()

    except ImportError:
        pass

    if isinstance(
        value,
        pd.Timestamp,
    ):
        return value.isoformat()

    raise TypeError(
        f"Object of type {type(value).__name__} "
        "is not JSON serializable."
    )


def value_to_prompt_text(
    value: Any,
) -> str:
    """
    Serialize arbitrary controller/evidence values into
    clean JSON-compatible text for the investigation prompt.
    """

    if value is None:
        return "null"

    if isinstance(
        value,
        bool,
    ):
        return (
            "true"
            if value
            else "false"
        )

    if isinstance(
        value,
        (int, float, str),
    ):
        return str(value)

    try:
        return json.dumps(
            value,
            default=_json_default,
            ensure_ascii=False,
        )

    except TypeError:
        return str(value)


# =========================================================
# Convert a DataFrame into readable evidence text
# =========================================================

def dataframe_to_text(
    name: str,
    dataframe: pd.DataFrame,
) -> str:
    """
    Convert one evidence dataframe into readable prompt text.

    Values are normalized first so NumPy/Pandas implementation
    details do not leak into the LLM prompt.
    """

    if dataframe.empty:
        return (
            f"{name}: NO RECORDS"
        )

    normalized = dataframe.copy(
        deep=True
    )

    # Convert NumPy scalar values to native Python values.
    for column in normalized.columns:

        normalized[column] = (
            normalized[column]
            .map(
                lambda value: (
                    _json_default(value)
                    if not isinstance(
                        value,
                        (
                            str,
                            int,
                            float,
                            bool,
                        ),
                    )
                    and value is not None
                    else value
                )
            )
        )

    return (
        f"{name}:\n"
        f"{normalized.to_string(index=False)}"
    )


# =========================================================
# Build AI investigation prompt
# =========================================================

def build_investigation_prompt(
    investigation_case: dict[str, Any],
) -> str:
    """
    Build the investigation prompt.

    The AI is a hypothesis generator only.

    It does not make the final financial decision.

    The controller independently:
        - validates evidence
        - verifies relationships
        - simulates proposed changes
        - determines the final outcome
    """

    # -----------------------------------------------------
    # Canonical controller-case sections
    # -----------------------------------------------------

    reconciliation = (
        investigation_case[
            "financial_facts"
        ][
            "reconciliation"
        ]
    )

    completeness = (
        investigation_case[
            "evidence_quality"
        ][
            "completeness"
        ]
    )

    consistency = (
        investigation_case[
            "evidence_quality"
        ][
            "consistency"
        ]
    )

    evidence = (
        investigation_case[
            "evidence"
        ]
    )

    # -----------------------------------------------------
    # Serialize evidence
    # -----------------------------------------------------

    evidence_text = "\n\n".join(
        [
            dataframe_to_text(
                "PAYMENT",
                evidence[
                    "payment"
                ],
            ),

            dataframe_to_text(
                "FEES",
                evidence[
                    "fees"
                ],
            ),

            dataframe_to_text(
                "REFUNDS",
                evidence[
                    "refunds"
                ],
            ),

            dataframe_to_text(
                "SETTLEMENT",
                evidence[
                    "settlement"
                ],
            ),

            dataframe_to_text(
                "LEDGER",
                evidence[
                    "ledger"
                ],
            ),
        ]
    )

    available_sources_text = (
        value_to_prompt_text(
            completeness[
                "available_sources"
            ]
        )
    )

    missing_sources_text = (
        value_to_prompt_text(
            completeness[
                "missing_sources"
            ]
        )
    )

    consistency_text = (
        value_to_prompt_text(
            consistency
        )
    )

    # -----------------------------------------------------
    # Canonical schema rules
    # -----------------------------------------------------

    schema_rules = (
        build_schema_rules_block()
    )

    # -----------------------------------------------------
    # Prompt
    # -----------------------------------------------------

    prompt = f"""
You are a financial reconciliation investigation assistant.

Your task is to generate plausible hypotheses that may explain
a financial reconciliation exception.

You are NOT the final decision maker.

The controller will independently validate the evidence,
verify financial relationships, and simulate proposed
counterfactual corrections.

==================================================
CASE
==================================================

PAYMENT ID:
{investigation_case["payment_id"]}

RECONCILIATION STATUS:
{reconciliation["status"]}

INITIAL EXCEPTION SIGNAL:
{reconciliation["reason"]}

EXPECTED SETTLEMENT:
{reconciliation["expected_settlement"]}

ACTUAL SETTLEMENT:
{reconciliation["actual_settlement"]}

SETTLEMENT DIFFERENCE:
{reconciliation["difference"]}

LEDGER NET:
{reconciliation["ledger_net"]}

LEDGER DIFFERENCE:
{reconciliation["ledger_difference"]}

LEDGER STATUS:
{reconciliation["ledger_status"]}

FINAL RECONCILIATION STATUS:
{reconciliation["final_status"]}

==================================================
EVIDENCE QUALITY
==================================================

EVIDENCE COMPLETENESS:
{completeness["completeness_percentage"]}%

AVAILABLE EVIDENCE SOURCES:
{available_sources_text}

MISSING EVIDENCE SOURCES:
{missing_sources_text}

EVIDENCE CONSISTENCY:
{consistency_text}

==================================================
FINANCIAL EVIDENCE
==================================================

{evidence_text}

==================================================
INVESTIGATION OBJECTIVE
==================================================

Generate zero or more materially plausible hypotheses
that could explain the observed financial exception.

A hypothesis is only a candidate explanation.

Do not declare a hypothesis proven.

Do not assume that the initial exception signal is the true
root cause.

The controller will independently test every proposed
hypothesis.

==================================================
HYPOTHESIS REQUIREMENTS
==================================================

For every hypothesis:

1. Identify the possible root cause.

2. Explain why the supplied evidence supports that possibility.

3. Identify the exact financial records relevant to the
   hypothesis.

4. Identify the relevant field on each record.

5. Report the observed value exactly as it appears in the
   supplied evidence.

6. When the hypothesis proposes changing an existing record,
   provide proposed_value as the hypothetical value to test.

7. When a cited record is not being changed by this hypothesis,
   use proposed_value = null.

8. State the financial delta that the hypothesis claims
   to explain.

9. The proposed correction must represent the hypothesis's
   own intended counterfactual state.

A hypothesis may contain one or multiple proposed changes.

Do not add a proposed change merely to restate an unchanged
record.

==================================================
EVIDENCE RULES
==================================================

Use ONLY the supplied evidence.

Do not invent:

- records
- record IDs
- amounts
- dates
- transactions
- relationships

Do not use hidden ground truth.

Do not infer that one source is authoritative merely because
it is a ledger, refund source, payment source, or settlement
source.

Conflicting sources may produce multiple plausible hypotheses.

==================================================
EXISTING VS MISSING RECORD
==================================================

Use RECORD_DELTA when an existing record may contain an
incorrect financial value.

Use MISSING_RECORD only when the expected financial event
itself does not exist.

For MISSING_RECORD:

- record_id must be null.
- observed_value must be null.
- proposed_value must be null.
- role must identify the missing event.

Never create a fake record ID for a missing event.

# ==================================================
# COMPETING HYPOTHESES
# ==================================================

When the available evidence supports multiple materially
plausible explanations for the PRIMARY exception:

- return all materially plausible explanations.
- do not collapse them into one.
- do not select one explanation as proven.
- keep each hypothesis independently testable.

Each competing hypothesis must represent a genuinely
different causal correction to the PRIMARY exception.

Do not create multiple hypotheses that merely describe the
same source discrepancy using different wording.

For every competing hypothesis, identify:

- the exact evidence supporting it.
- the exact record(s) that would change.
- the hypothetical value to test.
- why that change could explain the PRIMARY exception.

The controller will independently compare, verify, and
simulate the hypotheses after your response.


# ==================================================
# PROPOSED CORRECTIONS
# ==================================================

For an existing record:

observed_value
= the value currently present in the supplied evidence.

proposed_value
= the hypothetical value that this hypothesis proposes
  the controller should test.

proposed_value is NOT an observed fact.

Do not describe a proposed_value as though it already exists.

If the hypothesis does not require changing a cited record,
use proposed_value = null.

# ==================================================
# EXCEPTION-LEVEL CAUSALITY
# ==================================================

Every hypothesis must explain the PRIMARY financial
exception currently being investigated.

A hypothesis is materially plausible only when:

1. The proposed change is supported by supplied evidence.
2. The proposed change directly addresses the reported
   financial exception.
3. The proposed change has the correct financial direction
   relative to the observed discrepancy.
4. The proposed change can be independently tested by the
   controller's counterfactual simulator.

Do NOT return a hypothesis merely because two source records
disagree with each other.

A disagreement between two records is only supporting evidence.
It is not sufficient by itself to establish a causal hypothesis.

Before returning a hypothesis, evaluate:

"Would this proposed counterfactual change explain why the
PRIMARY financial exception exists?"

If the answer is NO, do not return that hypothesis.

The hypothesis must connect:

PRIMARY EXCEPTION
        ↓
EVIDENCE
        ↓
PROPOSED CHANGE
        ↓
EXPECTED FINANCIAL EFFECT

Do not confuse a source-to-source discrepancy with the primary
reconciliation discrepancy.

# ==================================================
# VALUE AND SIGN CONVENTIONS
# ==================================================

Observed values must be copied exactly from the supplied
source record.

Do NOT convert, negate, normalize, or reinterpret an observed
value because another financial source uses a different sign
convention.

For example:

- refund.refund_amount is the value stored in the refund source.
- ledger.amount may represent the same refund as a negative
  amount.

These are different source values.

When citing a refund record:

observed_value = refund.refund_amount exactly as supplied.

When citing a ledger record:

observed_value = ledger.amount exactly as supplied.

Never copy a signed ledger amount into a refund record.

Never change the sign of observed_value.

proposed_value must use the sign convention of the specific
source record being changed.

# ==================================================
# COMPETING HYPOTHESES / AMBIGUITY
# ==================================================

When the supplied evidence supports multiple materially
plausible explanations for the PRIMARY exception, return each
plausible explanation as a separate hypothesis.

For an ambiguous financial amount discrepancy:

1. Identify the PRIMARY exception difference.
2. Identify every supplied existing record whose value can
   plausibly account for that difference.
3. For each plausible cause, construct the counterfactual
   correction that directly addresses the PRIMARY exception.
4. Return ALL materially plausible corrections.
5. Do not choose a winner.
6. Do not return a hypothesis that does not directly address
   the PRIMARY exception.

A difference between two sources is supporting evidence only.
It is not sufficient by itself to establish causality.

The controller will independently validate evidence, verify
causal relationships, and run counterfactual simulation.

Do not use ground truth to choose between hypotheses.

==================================================
OUTPUT
==================================================

Return ONLY valid JSON.

Return exactly one top-level object:

{{
  "hypotheses": [
    {{
      "hypothesis_id": "H1",
      "root_cause": "string",
      "explanation": "string",
      "affected_records": [
        {{
          "source": "payment|fee|refund|settlement|ledger",
          "record_id": "string_or_null",
          "field": "string",
          "observed_value": null,
          "proposed_value": null,
          "role": "string"
        }}
      ],
      "causal_relationship": {{
        "type": "RECORD_DELTA",
        "claimed_delta": null,
        "direction": "UNKNOWN"
      }}
    }}
  ]
}}

==================================================
SCHEMA RULES
==================================================

{schema_rules}

For RECORD_DELTA:

- affected_records must contain at least ONE existing record.
- each affected record must have a real record_id.
- each affected record must have an observed_value.
- use the records whose financial values are being compared.
- at least one affected record should normally contain
  the proposed hypothetical correction.
- proposed_value is hypothetical, not an observed fact.
- proposed_value may be null when that record is unchanged.

For MISSING_RECORD:

- record_id must be null.
- observed_value must be null.
- proposed_value must be null.

Return no commentary outside the JSON object.
"""

    return prompt


# =========================================================
# Investigate one case with Groq
# =========================================================

def investigate_case(
    investigation_case: dict[str, Any],
) -> dict:
    """
    Generate and validate AI investigation hypotheses.

    Maximum two investigation attempts:

        Attempt 1
            ↓
        Groq
            ↓
        response validation
            ↓
        valid → return

        invalid / API failure
            ↓
        Attempt 2 with failure feedback
            ↓
        valid → return

        still invalid
            ↓
        RuntimeError
            ↓
        controller escalates to HUMAN_REVIEW

    Groq API retry behavior is intentionally bounded by
    call_groq(max_attempts=1).
    """

    base_prompt = (
        build_investigation_prompt(
            investigation_case
        )
    )

    last_error = None

    # -----------------------------------------------------
    # Maximum two complete investigation attempts.
    # -----------------------------------------------------

    for attempt in range(2):

        if attempt == 0:

            prompt = base_prompt

        else:
            prompt = f"""
{base_prompt}

==================================================
RETRY / CORRECTION INSTRUCTIONS
==================================================

The previous AI investigation response could not be
accepted.

Failure detail:

{last_error}

You are investigating a financial exception using only
the supplied evidence.

Generate a NEW investigation response.

IMPORTANT:

1. Return ONLY valid JSON.
2. Do not return markdown.
3. Do not return commentary outside the JSON object.
4. Do not invent record IDs.
5. Do not invent amounts.
6. Every observed_value must match the supplied evidence.
7. proposed_value represents a hypothetical counterfactual
   change only.
8. A hypothesis may contain unchanged reference records
   with proposed_value = null.
9. When multiple plausible causes exist, return MULTIPLE
   hypotheses rather than silently selecting one.
10. The controller will independently validate evidence and
    run counterfactual simulation.

Required structure:

{{
  "hypotheses": [
    {{
      "hypothesis_id": "H1",
      "root_cause": "string",
      "explanation": "string",
      "affected_records": [
        {{
          "source": "string",
          "record_id": "string or null",
          "field": "string",
          "observed_value": "number or null",
          "proposed_value": "number or null",
          "role": "string"
        }}
      ],
      "causal_relationship": {{
        "type": "RECORD_DELTA or MISSING_RECORD or DUPLICATE_RECORD",
        "claimed_delta": "number or null",
        "direction": "INCREASE or DECREASE or NEUTRAL or UNKNOWN"
      }}
    }}
  ]
}}

Rules for existing records:

- record_id must exactly match a supplied record.
- observed_value must exactly match the supplied evidence.
- Preserve the source-specific sign exactly.
- proposed_value may be different only as a hypothetical
  counterfactual.
- proposed_value must be null when the record is only a
  reference and is not being changed.

Rules for missing records:

- record_id = null
- observed_value = null
- proposed_value = null
- role must identify the missing event.

Rules for ambiguity:

- If multiple existing records can plausibly explain the same
  PRIMARY discrepancy, return all materially plausible
  hypotheses.
- Each hypothesis must represent a different causal
  correction.
- Do not collapse plausible causes into one hypothesis.
- Do not select a winner.

For this retry, prefer the simplest evidence-supported
hypotheses.

Return ONLY the JSON object.
"""

        # -------------------------------------------------
        # Groq API call
        # -------------------------------------------------

        try:

            response = call_groq(
                prompt,
                max_attempts=1,
            )

        except Exception as error:

            last_error = (
                f"Groq API call failed: {error}"
            )

            if attempt == 0:
                continue

            raise RuntimeError(
                "AI investigation failed after two "
                "attempts. The Groq API call did not "
                "produce a usable response. "
                f"Last error: {last_error}"
            ) from error

        # -------------------------------------------------
        # Python semantic/schema validation
        # -------------------------------------------------

        try:

            validated_response = (
                validate_ai_response(
                    response
                )
            )

            return validated_response

        except ValueError as error:

            last_error = (
                f"Response validation failed: {error}"
            )

            if attempt == 0:
                continue

            raise RuntimeError(
                "AI returned an invalid hypothesis "
                "response after two investigation "
                f"attempts. Last error: {last_error}"
            ) from error

    # -----------------------------------------------------
    # Defensive fallback
    # -----------------------------------------------------

    raise RuntimeError(
        "AI investigation failed after two attempts. "
        f"Last error: {last_error}"
    )


# =========================================================
# Batch AI hypothesis investigation test
# =========================================================

if __name__ == "__main__":

    data = load_exception_data()

    # -----------------------------------------------------
    # Run deterministic reconciliation once
    # -----------------------------------------------------

    payment_view = build_payment_view(
        data
    )

    payment_view = (
        calculate_expected_settlement(
            payment_view
        )
    )

    payment_view = classify_reconciliation(
        payment_view
    )

    payment_view = identify_exception_reason(
        data,
        payment_view,
    )

    payment_view = validate_ledger(
        data,
        payment_view,
    )

    payment_view = build_exception_report(
        payment_view
    )

    # Optional standalone test selection:
    # - pass payment IDs on the command line to test specific cases
    # - otherwise use all currently detected exception payments
    requested_payment_ids = [
        str(value).strip()
        for value in sys.argv[1:]
        if str(value).strip()
    ]

    detected_payment_ids = [
        str(value)
        for value in (
            payment_view.loc[
                payment_view["final_status"] == "EXCEPTION",
                "payment_id",
            ]
            .astype(str)
            .tolist()
        )
        if not str(value).endswith("_DUP")
    ]

    payment_ids = (
        requested_payment_ids
        if requested_payment_ids
        else detected_payment_ids
    )

    results = []

    print(
        "\n========================================"
    )

    print(
        "AI HYPOTHESIS INVESTIGATION BATCH"
    )

    print(
        "========================================"
    )

    for payment_id in payment_ids:

        print(
            f"\n--- Investigating {payment_id} ---"
        )

        matching_rows = payment_view[
            payment_view["payment_id"]
            == payment_id
        ]

        if matching_rows.empty:

            print(
                f"ERROR: No reconciliation result "
                f"found for {payment_id}"
            )

            continue

        row = matching_rows.iloc[0]

        reconciliation = {
            "status": row[
                "reconciliation_status"
            ],

            "reason": row[
                "exception_reason"
            ],

            "expected_settlement": row[
                "expected_settlement"
            ],

            "actual_settlement": row[
                "actual_settlement"
            ],

            "difference": row[
                "difference"
            ],

            "ledger_net": row[
                "ledger_net"
            ],

            "ledger_difference": row[
                "ledger_difference"
            ],

            "ledger_status": row[
                "ledger_status"
            ],

            "final_status": row[
                "final_status"
            ],
        }

        # -------------------------------------------------
        # Retrieve evidence
        # -------------------------------------------------

        evidence = retrieve_payment_evidence(
            data,
            payment_id,
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

        # -------------------------------------------------
        # Build the same canonical controller case
        # used by the orchestrator.
        # -------------------------------------------------

        investigation_case = (
            build_controller_case(
                payment_id=payment_id,

                reconciliation=reconciliation,

                evidence=evidence,

                evidence_completeness=(
                    completeness
                ),

                evidence_consistency=(
                    consistency
                ),
            )
        )

        # -------------------------------------------------
        # AI investigation
        # -------------------------------------------------

        try:

            ai_result = investigate_case(
                investigation_case
            )

        except Exception as error:

            print(
                f"AI ERROR for {payment_id}: "
                f"{error}"
            )

            results.append(
                {
                    "payment_id": payment_id,
                    "status": "AI_ERROR",
                    "error": str(error),
                }
            )

            continue

        hypotheses = ai_result.get(
            "hypotheses",
            [],
        )

        print(
            f"\nNumber of hypotheses: "
            f"{len(hypotheses)}"
        )

        if not hypotheses:

            print(
                "No hypotheses generated."
            )

            results.append(
                {
                    "payment_id": payment_id,
                    "hypothesis_id": None,
                    "status": "NO_HYPOTHESES",
                }
            )

            continue

        # -------------------------------------------------
        # Validate evidence for every hypothesis
        # -------------------------------------------------

        for hypothesis in hypotheses:

            evidence_validation = (
                validate_supporting_evidence(
                    hypothesis,
                    evidence,
                )
            )

            print(
                "\nHypothesis:"
            )

            print(
                hypothesis
            )

            print(
                "\nEvidence Validation:"
            )

            print(
                evidence_validation
            )

            results.append(
                {
                    "payment_id": payment_id,

                    "hypothesis_id": (
                        hypothesis[
                            "hypothesis_id"
                        ]
                    ),

                    "root_cause": (
                        hypothesis[
                            "root_cause"
                        ]
                    ),

                    "relationship_type": (
                        hypothesis[
                            "causal_relationship"
                        ][
                            "type"
                        ]
                    ),

                    "claimed_delta": (
                        hypothesis[
                            "causal_relationship"
                        ][
                            "claimed_delta"
                        ]
                    ),

                    "direction": (
                        hypothesis[
                            "causal_relationship"
                        ][
                            "direction"
                        ]
                    ),

                    "citations_valid": (
                        evidence_validation[
                            "all_citations_valid"
                        ]
                    ),

                    "evidence_completeness": (
                        completeness[
                            "completeness_percentage"
                        ]
                    ),
                }
            )

    # -----------------------------------------------------
    # Summary
    # -----------------------------------------------------

    print(
        "\n========================================"
    )

    print(
        "AI HYPOTHESIS SUMMARY"
    )

    print(
        "========================================"
    )

    if results:

        summary_df = pd.DataFrame(
            results
        )

        print(
            summary_df.to_string(
                index=False
            )
        )

    else:

        print(
            "No investigation results."
        )