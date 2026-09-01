from pathlib import Path
import pandas as pd
import sys
from typing import Any

# ---------------------------------------------------------
# Make project root importable when this file is
# executed directly:
#
# python src/ai/investigator.py
# ---------------------------------------------------------

PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent.parent
)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


# ---------------------------------------------------------
# Project imports
# ---------------------------------------------------------

from src.ai.client import call_groq

from src.ai.response_validator import (
    validate_ai_response,
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

from src.ai.decision_policy import (
    decide_next_action,
)

from src.reconciliation.engine import (
    build_payment_view,
    calculate_expected_settlement,
    classify_reconciliation,
    identify_exception_reason,
    validate_ledger,
    build_exception_report,
)


# ---------------------------------------------------------
# Convert a DataFrame into readable evidence text
# ---------------------------------------------------------

def dataframe_to_text(
    name: str,
    dataframe,
) -> str:

    if dataframe.empty:
        return f"{name}: NO RECORDS"

    return (
        f"{name}:\n"
        f"{dataframe.to_string(index=False)}"
    )


# ---------------------------------------------------------
# Build AI investigation prompt
# ---------------------------------------------------------

def build_investigation_prompt(
    investigation_case: dict[str, Any],
) -> str:

    reconciliation = (
        investigation_case["reconciliation"]
    )

    completeness = (
        investigation_case[
            "evidence_completeness"
        ]
    )

    evidence = (
        investigation_case["evidence"]
    )

    consistency = (
        investigation_case[
            "evidence_consistency"
        ]
    )

    # -----------------------------------------------------
    # Convert every evidence source into text
    # -----------------------------------------------------

    evidence_text = "\n\n".join(
        [
            dataframe_to_text(
                "PAYMENT",
                evidence["payment"],
            ),

            dataframe_to_text(
                "FEES",
                evidence["fees"],
            ),

            dataframe_to_text(
                "REFUNDS",
                evidence["refunds"],
            ),

            dataframe_to_text(
                "SETTLEMENT",
                evidence["settlement"],
            ),

            dataframe_to_text(
                "LEDGER",
                evidence["ledger"],
            ),
        ]
    )

    # -----------------------------------------------------
    # AI prompt
    # -----------------------------------------------------

    prompt = f"""
You are a financial reconciliation investigator.

Your job is to investigate a payment exception
using ONLY the evidence provided below.

STRICT RULES:

- Do not invent records.
- Do not assume missing information exists.
- Do not use hidden ground truth.
- Do not treat the initial exception reason as proven root cause.
- Use the evidence to determine the most defensible explanation.
- If evidence is incomplete or conflicting, do not guess.
- In uncertain cases, recommend HUMAN_REVIEW.

PAYMENT ID:
{investigation_case["payment_id"]}

RECONCILIATION STATUS:
{reconciliation["status"]}

INITIAL REASON:
{reconciliation["reason"]}

EXPECTED SETTLEMENT:
{reconciliation["expected_settlement"]}

ACTUAL SETTLEMENT:
{reconciliation["actual_settlement"]}

DIFFERENCE:
{reconciliation["difference"]}

EVIDENCE COMPLETENESS:
{completeness["completeness_percentage"]}%

AVAILABLE SOURCES:
{completeness["available_sources"]}

MISSING SOURCES:
{completeness["missing_sources"]}

EVIDENCE CONSISTENCY:
{consistency}

IMPORTANT INVESTIGATION SIGNALS:

The deterministic system may identify conflicts or
multiple plausible explanations.

If the evidence contains an
"AMBIGUOUS_EXPLANATIONS" conflict:

- Do not choose one explanation as proven.
- Mark evidence_sufficient as false.
- Recommend HUMAN_REVIEW.
- Explicitly list the competing explanations.

EVIDENCE RECORDS:
{evidence_text}

Your task is to determine:

1. Most likely root cause.
2. Explanation for the discrepancy.
3. Exact supporting evidence.
4. Whether the evidence is sufficient.
5. Confidence from 0 to 1.
6. Recommended action.

Return ONLY valid JSON with exactly these fields:

{
  "root_cause": "string",
  "explanation": "string",
  "supporting_evidence": [
    {
      "source": "string",
      "record_id": "string",
      "field": "string",
      "claimed_value": null,
      "claim_type": "DIRECT_VALUE",
      "reason": "string"
    }
  ],
  "evidence_sufficient": true,
  "confidence": 0.0,
  "recommended_action": "string"
}

For each supporting evidence item:

- claim_type must be one of:
  DIRECT_VALUE
  ABSENCE
  COMPARISON

- claimed_value must be the value being asserted for the specified
  field, or null for ABSENCE claims.

- Do not use natural-language reasoning to hide numerical claims.
"""

    return prompt


# ---------------------------------------------------------
# Investigate one case with Groq
# ---------------------------------------------------------

def investigate_case(
    investigation_case: dict[str, Any],
) -> dict:

    prompt = build_investigation_prompt(
        investigation_case
    )

    response = call_groq(
        prompt
    )

    validated_response = (
        validate_ai_response(
            response
        )
    )

    return validated_response


# ---------------------------------------------------------
# Batch AI investigation test
# ---------------------------------------------------------

if __name__ == "__main__":

    payment_ids = [
        "PAY00001",
        "PAY00002",
        "PAY00003",
        "PAY00004",
        "PAY00005",
        "PAY00006",
        "PAY00007",
    ]

    # -----------------------------------------------------
    # Load exception data once
    # -----------------------------------------------------

    data = load_exception_data()

    results = []

    print(
        "\n========================================"
    )

    print(
        "AI FINANCIAL INVESTIGATION BATCH"
    )

    print(
        "========================================"
    )

    # -----------------------------------------------------
    # Investigate every selected payment
    # -----------------------------------------------------

    for payment_id in payment_ids:

        print(
            f"\n--- Investigating {payment_id} ---"
        )

        # -------------------------------------------------
        # Run reconciliation engine
        # -------------------------------------------------

        payment_view = build_payment_view(
            data
        )

        payment_view = (
            calculate_expected_settlement(
                payment_view
            )
        )

        payment_view = (
            classify_reconciliation(
                payment_view
            )
        )

        payment_view = (
            identify_exception_reason(
                data,
                payment_view
            )
        )

        payment_view = validate_ledger(
            data,
            payment_view
        )

        payment_view = build_exception_report(
            payment_view
        )

        # -------------------------------------------------
        # Find payment reconciliation row
        # -------------------------------------------------

        matching_rows = payment_view[
            payment_view["payment_id"]
            == payment_id
        ]

        if matching_rows.empty:

            print(
                f"ERROR: No reconciliation result "
                f"for {payment_id}"
            )

            continue

        reconciliation_row = (
            matching_rows.iloc[0]
        )

        # -------------------------------------------------
        # Retrieve evidence
        # -------------------------------------------------

        evidence = retrieve_payment_evidence(
            data,
            payment_id
        )

        # -------------------------------------------------
        # Evidence quality
        # -------------------------------------------------

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
        # Build reconciliation information
        # -------------------------------------------------

        reconciliation = {

            "status": (
                reconciliation_row[
                    "reconciliation_status"
                ]
            ),

            "reason": (
                reconciliation_row[
                    "exception_reason"
                ]
            ),

            "expected_settlement": (
                reconciliation_row[
                    "expected_settlement"
                ]
            ),

            "actual_settlement": (
                reconciliation_row[
                    "actual_settlement"
                ]
            ),

            "difference": (
                reconciliation_row[
                    "difference"
                ]
            ),

            "ledger_net": (
                reconciliation_row[
                    "ledger_net"
                ]
            ),

            "ledger_difference": (
                reconciliation_row[
                    "ledger_difference"
                ]
            ),

            "ledger_status": (
                reconciliation_row[
                    "ledger_status"
                ]
            ),

            "final_status": (
                reconciliation_row[
                    "final_status"
                ]
            ),
        }

        # -------------------------------------------------
        # Build investigation case
        # -------------------------------------------------

        investigation_case = {

            "case_id": (
                f"CASE-{payment_id}"
            ),

            "payment_id": payment_id,

            "reconciliation": reconciliation,

            "evidence": evidence,

            "evidence_completeness": (
                completeness
            ),

            "evidence_consistency": (
                consistency
            ),
        }

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

            continue

        # -------------------------------------------------
        # Validate AI citations
        # -------------------------------------------------

        evidence_validation = (
            validate_supporting_evidence(
                ai_result,
                evidence
            )
        )

        # -------------------------------------------------
        # Controller decision
        # -------------------------------------------------
        decision = decide_next_action(
            ai_result,
            completeness,
            consistency,
            evidence_validation,
            reconciliation["reason"],
        )

        # -------------------------------------------------
        # Save compact result
        # -------------------------------------------------

        results.append(
            {
                "payment_id": payment_id,

                "ai_root_cause": (
                    ai_result["root_cause"]
                ),

                "ai_confidence": (
                    ai_result["confidence"]
                ),

                "evidence_sufficient": (
                    ai_result[
                        "evidence_sufficient"
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

                "decision": (
                    decision["decision"]
                ),
            }
        )

        # -------------------------------------------------
        # Display result
        # -------------------------------------------------

        print(
            "\nAI Result:"
        )

        print(
            ai_result
        )

        print(
            "\nEvidence Validation:"
        )

        print(
            evidence_validation
        )

        print(
            "\nController Decision:"
        )

        print(
            decision
        )

    # -----------------------------------------------------
    # Batch summary
    # -----------------------------------------------------

    print(
        "\n========================================"
    )

    print(
        "BATCH INVESTIGATION SUMMARY"
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
            "No successful investigations."
        )

        