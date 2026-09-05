from pathlib import Path
import sys
from typing import Any


# =========================================================
# Make project root importable for direct execution
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

from src.controller.case import (
    build_controller_case,
)

from src.ai.investigator import (
    investigate_case,
)

from src.ai.evidence_validator import (
    validate_supporting_evidence,
)

from src.controller.causal_verifier import (
    verify_hypothesis as verify_causal_hypothesis,
)

from src.controller.simulator import (
    simulate_hypothesis,
)

from src.controller.deterministic_resolver import (
    generate_deterministic_hypotheses,
)

from src.evidence.completeness import (
    calculate_evidence_completeness,
)

from src.evidence.consistency import (
    check_evidence_consistency,
)

from src.evidence.retriever import (
    load_exception_data,
    retrieve_payment_evidence,
)

from src.reconciliation.engine import (
    build_exception_report,
    build_payment_view,
    calculate_expected_settlement,
    classify_reconciliation,
    identify_exception_reason,
    validate_ledger,
)


# =========================================================
# RECONCILIATION
# =========================================================

def build_reconciliation_view(
    data: dict[str, Any],
):
    """
    Run the deterministic reconciliation engine once.

    The resulting DataFrame is reused for individual cases.
    """

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
            payment_view,
        )
    )

    payment_view = validate_ledger(
        data,
        payment_view,
    )

    payment_view = (
        build_exception_report(
            payment_view
        )
    )

    return payment_view


# =========================================================
# CASE CONSTRUCTION
# =========================================================

def build_controller_case_for_payment(
    data: dict[str, Any],
    payment_view,
    payment_id: str,
) -> dict[str, Any]:
    """
    Build the canonical controller case for one payment.

    This function gathers deterministic facts and evidence.

    It does not ask the AI to make a conclusion.
    """

    # -----------------------------------------------------
    # Find reconciliation result
    # -----------------------------------------------------

    matching_rows = payment_view[
        payment_view[
            "payment_id"
        ]
        == payment_id
    ]

    if matching_rows.empty:
        raise ValueError(
            f"No reconciliation result found "
            f"for {payment_id}."
        )

    row = matching_rows.iloc[0]

    # -----------------------------------------------------
    # Deterministic reconciliation facts
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Evidence retrieval
    # -----------------------------------------------------

    evidence = retrieve_payment_evidence(
        data,
        payment_id,
    )

    # -----------------------------------------------------
    # Evidence quality
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Canonical controller case
    # -----------------------------------------------------

    controller_case = build_controller_case(
        payment_id=payment_id,
        reconciliation=reconciliation,
        evidence=evidence,
        evidence_completeness=completeness,
        evidence_consistency=consistency,
    )

    # -----------------------------------------------------
    # Internal source data for simulation.
    #
    # This is NOT sent to the AI prompt.
    # -----------------------------------------------------

    controller_case[
        "_source_data"
    ] = data

    return controller_case


# =========================================================
# SIMULATION
# =========================================================

def _simulate_hypothesis(
    controller_case: dict[str, Any],
    hypothesis: dict[str, Any],
) -> dict[str, Any]:
    """
    Run counterfactual simulation against the original
    source data through the generic simulator.
    """

    source_data = controller_case.get(
        "_source_data"
    )

    if source_data is None:
        return {
            "status": "FAILED",
            "exception_cleared": False,
            "reason": (
                "Controller case does not contain "
                "internal source data for simulation."
            ),
        }

    return simulate_hypothesis(
        data=source_data,
        payment_id=controller_case[
            "payment_id"
        ],
        hypothesis=hypothesis,
    )
# =========================================================
# HYPOTHESIS MERGING
# =========================================================

def _hypothesis_signature(
    hypothesis: dict[str, Any],
) -> tuple[Any, ...]:
    """
    Build a generic, content-based signature for a
    hypothesis so identical explanations coming from
    different sources (deterministic vs AI) can be
    deduplicated without hardcoding any payment ID.
    """

    records = []

    for record in hypothesis.get(
        "affected_records",
        [],
    ):
        records.append(
            (
                record.get("source"),
                record.get("record_id"),
                record.get("field"),
                record.get("proposed_value"),
            )
        )

    return (
        hypothesis.get(
            "causal_relationship",
            {},
        ).get("type"),
        tuple(sorted(records, key=str)),
    )

def _merge_hypotheses(
    deterministic_hypotheses: list[dict[str, Any]],
    ai_hypotheses: list[dict[str, Any]],
    investigation_mode: str = "DETERMINISTIC",
) -> list[dict[str, Any]]:
    """
    Merge deterministic and AI hypotheses.

    Deterministic hypotheses are never discarded.
    AI hypotheses are added as additional candidates.

    The evidence-support gate, causal verification, and
    counterfactual simulation decide which candidates survive.
    """

    merged = []
    seen = set()

    for hypothesis in (
        deterministic_hypotheses
        + ai_hypotheses
    ):

        signature = _hypothesis_signature(
            hypothesis
        )

        if signature in seen:
            continue

        seen.add(
            signature
        )

        merged.append(
            hypothesis
        )

    return merged



def _hypothesis_has_evidence_support(
    hypothesis: dict[str, Any],
    controller_case: dict[str, Any],
) -> bool:
    """
    Check whether an AI hypothesis is supported by an
    independently observed source relationship.

    This is an evidence-support gate, not a counterfactual
    simulation. Simulation remains the final financial test.

    The gate is intentionally generic:
        - fee hypothesis -> fee/ledger conflict required
        - refund hypothesis -> refund/ledger conflict required
        - settlement hypothesis -> settlement/ledger conflict required
        - ledger hypothesis -> corresponding source conflict required
        - structural hypotheses -> allowed to proceed
    """

    evidence_quality = controller_case.get(
        "evidence_quality",
        {},
    )

    consistency = evidence_quality.get(
        "consistency",
        {},
    )

    checks = consistency.get(
        "checks",
        {},
    )

    conflicts = consistency.get(
        "conflicts",
        [],
    )

    affected_records = hypothesis.get(
        "affected_records",
        [],
    )

    if not affected_records:
        return False

    sources = {
        str(
            record.get(
                "source",
                "",
            )
        )
        .strip()
        .lower()
        for record in affected_records
    }

    roles = {
        str(
            record.get(
                "role",
                "",
            )
        )
        .strip()
        .upper()
        for record in affected_records
    }

    relationship_type = str(
        hypothesis.get(
            "causal_relationship",
            {},
        ).get(
            "type",
            "",
        )
    ).strip().upper()

    # ---------------------------------------------------------
    # Structural hypotheses
    #
    # These are supported by record structure rather than by
    # a source-vs-ledger amount conflict.
    # ---------------------------------------------------------

    if relationship_type in {
        "MISSING_RECORD",
        "DUPLICATE_RECORD",
    }:
        return True

    normalized_roles = {
        role.lower()
        for role in roles
    }

    if "duplicate_fee_record" in normalized_roles:
        return True

    if "missing_record" in normalized_roles:
        return True

    # ---------------------------------------------------------
    # Fee hypothesis
    # ---------------------------------------------------------

    if "fee" in sources:

        if not bool(
            checks.get(
                "fee_ledger_consistent",
                False,
            )
        ):
            return True

        for conflict in conflicts:

            if str(
                conflict.get(
                    "type",
                    "",
                )
            ).upper() == "FEE_LEDGER_CONFLICT":
                return True

        return False

    # ---------------------------------------------------------
    # Refund hypothesis
    # ---------------------------------------------------------

    if "refund" in sources:

        if not bool(
            checks.get(
                "refund_ledger_consistent",
                False,
            )
        ):
            return True

        for conflict in conflicts:

            if str(
                conflict.get(
                    "type",
                    "",
                )
            ).upper() == "REFUND_LEDGER_CONFLICT":
                return True

        return False

    # ---------------------------------------------------------
    # Settlement hypothesis
    #
    # A settlement/ledger conflict is not sufficient by itself
    # when there is also an upstream fee or refund conflict.
    # In that situation the settlement discrepancy may be a
    # downstream symptom of a compound inconsistency, so the
    # controller must require human review.
    # ---------------------------------------------------------

    if "settlement" in sources:

        fee_conflict = (
            not bool(
                checks.get(
                    "fee_ledger_consistent",
                    True,
                )
            )
        )

        refund_conflict = (
            not bool(
                checks.get(
                    "refund_ledger_consistent",
                    True,
                )
            )
        )

        settlement_conflict = (
            not bool(
                checks.get(
                    "settlement_ledger_consistent",
                    True,
                )
            )
        )

        # Compound upstream inconsistency:
        # do not independently support settlement correction.
        if (
            settlement_conflict
            and (
                fee_conflict
                or refund_conflict
            )
        ):
            return False

        # Clean settlement/ledger conflict:
        # settlement remains independently supported.
        if settlement_conflict:
            return True

        for conflict in conflicts:
            if str(
                conflict.get(
                    "type",
                    "",
                )
            ).upper() == "SETTLEMENT_LEDGER_CONFLICT":
                return True

        return False
  


    

    # ---------------------------------------------------------
    # Ledger hypothesis
    #
    # A ledger correction must correspond to a demonstrated
    # source/ledger conflict.
    # ---------------------------------------------------------

    if "ledger" in sources:

        fee_conflict = (
            not bool(
                checks.get(
                    "fee_ledger_consistent",
                    False,
                )
            )
            and (
                "FEE" in roles
                or any(
                    str(
                        conflict.get(
                            "type",
                            "",
                        )
                    ).upper()
                    == "FEE_LEDGER_CONFLICT"
                    for conflict in conflicts
                )
            )
        )

        if fee_conflict:
            return True

        refund_conflict = (
            not bool(
                checks.get(
                    "refund_ledger_consistent",
                    False,
                )
            )
            and (
                "REFUND" in roles
                or any(
                    str(
                        conflict.get(
                            "type",
                            "",
                        )
                    ).upper()
                    == "REFUND_LEDGER_CONFLICT"
                    for conflict in conflicts
                )
            )
        )

        if refund_conflict:
            return True

        settlement_conflict = (
            not bool(
                checks.get(
                    "settlement_ledger_consistent",
                    False,
                )
            )
            and any(
                str(
                    conflict.get(
                        "type",
                        "",
                    )
                ).upper()
                == "SETTLEMENT_LEDGER_CONFLICT"
                for conflict in conflicts
            )
        )

        if settlement_conflict:
            return True

        return False

    # ---------------------------------------------------------
    # Unknown source
    #
    # Do not invent evidence support.
    # Let the normal causal/simulation pipeline evaluate it.
    # ---------------------------------------------------------

    return True


def _auto_resolution_allowed(
    hypothesis: dict[str, Any],
    controller_case: dict[str, Any],
) -> tuple[bool, str]:
    """
    Final safety gate for automatic resolution.

    A successful simulation proves that a proposed change can
    restore financial balance. It does not, by itself, prove
    that the proposed record is the uniquely justified root cause.

    Automatic resolution is therefore blocked for:
        - explicit conflicting evidence
        - genuine duplicate/overlapping fee records
        - compound fee/refund inconsistencies
        - settlement corrections when the ledger relationship
          is itself the unresolved source of the exception
        - incomplete evidence
        - explicit ambiguity
    """

    evidence_quality = controller_case.get(
        "evidence_quality",
        {},
    )

    consistency = evidence_quality.get(
        "consistency",
        {},
    )

    checks = consistency.get(
        "checks",
        {},
    )

    conflicts = consistency.get(
        "conflicts",
        [],
    )

    reconciliation = (
        controller_case.get(
            "financial_facts",
            {},
        ).get(
            "reconciliation",
            {},
        )
    )

    evidence = controller_case.get(
        "evidence",
        {},
    )

    payment_id = str(
        controller_case.get(
            "payment_id",
            "",
        )
    )

    affected_records = hypothesis.get(
        "affected_records",
        [],
    )

    sources = {
        str(
            record.get(
                "source",
                "",
            )
        ).strip().lower()
        for record in affected_records
    }

    # ---------------------------------------------------------
    # 1. Explicit conflicting-evidence exception
    # ---------------------------------------------------------

    if str(
        reconciliation.get(
            "reason",
            "",
        )
    ).strip().upper() == "CONFLICTING_EVIDENCE":

        return (
            False,
            "Conflicting financial evidence requires human review.",
        )

    # ---------------------------------------------------------
    # 2. Inspect fee records for genuine duplication/overlap.
    #
    # Multiple fee rows are not automatically unsafe.
    # However, multiple fee records with the same payment,
    # fee type, timestamp, and overlapping context indicate
    # that the controller cannot safely decide which record
    # is legitimate.
    # ---------------------------------------------------------

    fees_df = evidence.get(
        "fees"
    )

    if (
        fees_df is not None
        and hasattr(
            fees_df,
            "columns",
        )
        and "payment_id" in fees_df.columns
    ):

        fee_rows = fees_df[
            fees_df["payment_id"]
            .astype(str)
            .eq(payment_id)
        ]

        if len(fee_rows) > 1:

            duplicate_fee = False

            required_columns = {
                "fee_amount",
                "fee_type",
                "created_at",
            }

            if required_columns.issubset(
                fee_rows.columns
            ):

                duplicate_fee = (
                    fee_rows.duplicated(
                        subset=[
                            "fee_amount",
                            "fee_type",
                            "created_at",
                        ],
                        keep=False,
                    ).any()
                )

            if duplicate_fee:

                return (
                    False,
                    (
                        "Duplicate fee evidence exists for "
                        "the payment; automatic correction "
                        "requires human review."
                    ),
                )

            # -------------------------------------------------
            # Multiple non-identical fee records.
            #
            # If the fee total itself conflicts with the ledger,
            # the controller cannot determine automatically which
            # fee is invalid or whether a ledger entry is missing.
            # -------------------------------------------------

            fee_conflict = not bool(
                checks.get(
                    "fee_ledger_consistent",
                    True,
                )
            )

            if fee_conflict:

                return (
                    False,
                    (
                        "Multiple fee records conflict with "
                        "the ledger; the controller cannot "
                        "uniquely attribute the discrepancy."
                    ),
                )

    # ---------------------------------------------------------
    # 3. Compound fee + refund inconsistency
    # ---------------------------------------------------------

    fee_conflict = not bool(
        checks.get(
            "fee_ledger_consistent",
            True,
        )
    )

    refund_conflict = not bool(
        checks.get(
            "refund_ledger_consistent",
            True,
        )
    )

    settlement_conflict = not bool(
        checks.get(
            "settlement_ledger_consistent",
            True,
        )
    )

    if (
        fee_conflict
        and refund_conflict
    ):

        return (
            False,
            (
                "Compound fee and refund inconsistencies "
                "prevent unique causal attribution."
            ),
        )

    # ---------------------------------------------------------
    # 4. Settlement correction safety
    #
    # Do not automatically rewrite a settlement merely because
    # doing so makes settlement == ledger.
    #
    # If the settlement-vs-ledger conflict is the unresolved
    # exception, the settlement is evidence of the discrepancy,
    # not proof that the settlement record itself is wrong.
    # ---------------------------------------------------------

    if "settlement" in sources:

        settlement_conflict_present = (
            any(
                str(
                    conflict.get(
                        "type",
                        "",
                    )
                ).strip().upper()
                == "SETTLEMENT_LEDGER_CONFLICT"
                for conflict in conflicts
            )
        )

        if settlement_conflict_present:

            return (
                False,
                (
                    "Settlement differs from the ledger, but "
                    "the evidence does not independently prove "
                    "the settlement record is the root cause."
                ),
            )

    # ---------------------------------------------------------
    # 5. Compound fee + settlement inconsistency
    # ---------------------------------------------------------

    if (
        "settlement" not in sources
        and fee_conflict
        and settlement_conflict
    ):

        return (
            False,
            (
                "Compound fee and settlement inconsistencies "
                "prevent unique causal attribution."
            ),
        )

    # ---------------------------------------------------------
    # 6. Missing evidence
    # ---------------------------------------------------------

    completeness = evidence_quality.get(
        "completeness",
        {},
    )

    missing_sources = completeness.get(
        "missing_sources",
        [],
    )

    if missing_sources:

        return (
            False,
            "Required financial evidence is incomplete.",
        )

    # ---------------------------------------------------------
    # 7. Explicit ambiguous explanations
    # ---------------------------------------------------------

    for conflict in conflicts:

        conflict_type = str(
            conflict.get(
                "type",
                "",
            )
        ).strip().upper()

        if conflict_type == "AMBIGUOUS_EXPLANATIONS":

            return (
                False,
                (
                    "Multiple materially plausible "
                    "financial explanations remain."
                ),
            )

    # ---------------------------------------------------------
    # 8. Safe to continue
    # ---------------------------------------------------------

    return (
        True,
        (
            "Evidence structure supports a uniquely "
            "defensible correction."
        ),
    )
# =========================================================
# DECISION EXPLANATION
# =========================================================

def _build_decision_explanation(
    controller_case: dict[str, Any],
) -> dict[str, Any]:
    """
    Build a human-readable explanation of the final
    controller decision.

    This explains:
        - investigation mode
        - exception
        - hypotheses considered
        - evidence validation
        - causal verification
        - simulation
        - accepted/rejected reasoning
        - next action
    """

    decision = controller_case.get(
        "final_decision",
        {},
    )

    reconciliation = (
        controller_case[
            "financial_facts"
        ][
            "reconciliation"
        ]
    )

    explanation = {
        "decision": decision.get(
            "decision"
        ),

        "investigation_mode": (
            controller_case.get(
                "investigation_mode"
            )
        ),

        "investigation_mode_detail": (
            controller_case.get(
                "investigation_mode_detail"
            )
        ),

        "exception": {
            "reason": reconciliation.get(
                "reason"
            ),
            "expected_settlement": (
                reconciliation.get(
                    "expected_settlement"
                )
            ),
            "actual_settlement": (
                reconciliation.get(
                    "actual_settlement"
                )
            ),
            "difference": reconciliation.get(
                "difference"
            ),
        },

        "hypotheses": [],
    }

    for result in controller_case.get(
        "verification",
        [],
    ):

        simulation = result.get(
            "simulation"
        ) or {}

        causal = result.get(
            "causal_verification",
            {},
        )

        evidence = result.get(
            "evidence_validation",
            {},
        )

        hypothesis_explanation = {
            "hypothesis_id": result.get(
                "hypothesis_id"
            ),
            "root_cause": result.get(
                "root_cause"
            ),
            "explanation": result.get(
                "explanation"
            ),
                
            "affected_records": result.get(
                "affected_records",
                []
            ),

            "evidence_valid": evidence.get(
                "all_citations_valid"
            ),

            "causal_status": causal.get(
                "status"
            ),

            "simulation_status": simulation.get(
                "status"
            ),

            "exception_cleared": simulation.get(
                "exception_cleared"
            ),

            "difference_improved": simulation.get(
                "difference_improved"
            ),

            "applied_changes": simulation.get(
                "applied_changes",
                [],
            ),
        }

        if (
            simulation.get(
                "exception_cleared"
            )
            is True
        ):

            hypothesis_explanation[
                "result"
            ] = (
                "Accepted because the "
                "counterfactual simulation "
                "cleared the exception."
            )

        elif simulation:

            hypothesis_explanation[
                "result"
            ] = (
                simulation.get(
                    "reason"
                )
                or
                "Rejected because the "
                "counterfactual simulation "
                "did not clear the exception."
            )

        elif (
            causal.get(
                "status"
            )
            == "REJECTED"
        ):

            hypothesis_explanation[
                "result"
            ] = (
                causal.get(
                    "reason"
                )
                or
                "Rejected during causal verification."
            )

        else:

            hypothesis_explanation[
                "result"
            ] = (
                causal.get(
                    "reason"
                )
                or
                "No conclusive verification result."
            )

        explanation[
            "hypotheses"
        ].append(
            hypothesis_explanation
        )

    if (
        decision.get(
            "decision"
        )
        == "RESOLUTION_CANDIDATE"
    ):

        explanation[
            "why"
        ] = (
            "Exactly one hypothesis survived "
            "the verification pipeline and its "
            "counterfactual simulation cleared "
            "the financial exception."
        )

        explanation[
            "next_action"
        ] = (
            "Review the proposed resolution "
            "before applying any real financial change."
        )

    elif (
        decision.get(
            "decision"
        )
        == "HUMAN_REVIEW"
    ):

        explanation[
            "why"
        ] = (
            decision.get(
                "reason"
            )
            or
            "No uniquely defensible resolution "
            "was established."
        )

        explanation[
            "next_action"
        ] = (
            "Human investigation is required."
        )

    elif (
        decision.get(
            "decision"
        )
        == "AUTO_CLOSED"
    ):

        explanation[
            "why"
        ] = (
            "Deterministic reconciliation "
            "confirmed that the records are balanced."
        )

        explanation[
            "next_action"
        ] = (
            "No further investigation required."
        )

    else:

        explanation[
            "why"
        ] = decision.get(
            "reason"
        )

        explanation[
            "next_action"
        ] = (
            "Review the controller result."
        )

    return explanation

# =========================================================
# DETERMINISTIC EVIDENCE RESULT
# =========================================================

def _build_deterministic_evidence_result(
    hypothesis: dict[str, Any],
) -> dict[str, Any]:
    """
    Deterministic hypotheses are generated from controller
    facts/evidence rather than from the AI.

    We therefore do not force them through the AI citation
    validator before simulation.

    The simulator remains the final financial test.
    """

    return {
        "all_citations_valid": True,
        "validation_mode": "DETERMINISTIC",
        "validated_count": len(
            hypothesis.get(
                "affected_records",
                [],
            )
        ),
        "total_citations": len(
            hypothesis.get(
                "affected_records",
                [],
            )
        ),
    }


# =========================================================
# SINGLE CASE EXECUTION
# =========================================================

def investigate_controller_case(
    controller_case: dict[str, Any],
) -> dict[str, Any]:
    """
    Run one complete controller investigation.

    Control flow:

        MATCH
            -> AUTO_CLOSED

        EXCEPTION
            -> deterministic hypothesis generation
            -> if competing candidates exist, AI investigation
            -> merge deterministic + AI hypotheses
            -> evidence validation
            -> evidence support gate
            -> deterministic or AI causal verification
            -> counterfactual simulation
            -> final verification
            -> controller decision

    Important safety property:

        A hypothesis is not accepted merely because a
        counterfactual simulation can clear the exception.

        The hypothesis must first have independent evidence
        support, and then survive causal verification and
        counterfactual simulation.
    """

    # -----------------------------------------------------
    # 1. Read reconciliation
    # -----------------------------------------------------

    reconciliation = (
        controller_case[
            "financial_facts"
        ][
            "reconciliation"
        ]
    )

    final_status = str(
        reconciliation.get(
            "final_status",
            "",
        )
    ).strip().upper()

    # -----------------------------------------------------
    # 2. NORMAL CASE
    # -----------------------------------------------------

    if final_status == "MATCH":

        controller_case[
            "investigation_mode"
        ] = "NONE"

        controller_case[
            "ai_analysis"
        ] = None

        controller_case[
            "verification"
        ] = []

        controller_case[
            "resolution"
        ] = None

        controller_case[
            "final_decision"
        ] = {
            "decision": "AUTO_CLOSED",
            "reason": (
                "Deterministic reconciliation "
                "confirmed that the financial "
                "records are balanced."
            ),
        }

        controller_case[
            "decision_explanation"
        ] = _build_decision_explanation(
            controller_case
        )

        return controller_case

    # -----------------------------------------------------
    # 3. INVALID RECONCILIATION STATE
    # -----------------------------------------------------

    if final_status != "EXCEPTION":

        controller_case[
            "investigation_mode"
        ] = "NONE"

        controller_case[
            "ai_analysis"
        ] = None

        controller_case[
            "verification"
        ] = []

        controller_case[
            "resolution"
        ] = None

        controller_case[
            "final_decision"
        ] = {
            "decision": "NO_ACTION",
            "reason": (
                "The deterministic reconciliation "
                "result is neither MATCH nor EXCEPTION."
            ),
        }

        controller_case[
            "decision_explanation"
        ] = _build_decision_explanation(
            controller_case
        )

        return controller_case

    # -----------------------------------------------------
    # 4. DETERMINISTIC INVESTIGATION FIRST
    # -----------------------------------------------------

    try:

        deterministic_hypotheses = (
            generate_deterministic_hypotheses(
                controller_case
            )
        )

    except Exception as error:

        deterministic_hypotheses = []

        controller_case[
            "deterministic_error"
        ] = str(error)

    # -----------------------------------------------------
    # 5. Candidate source
    # -----------------------------------------------------

    deterministic_signatures = {
        _hypothesis_signature(
            hypothesis
        )
        for hypothesis in deterministic_hypotheses
    }

    # =====================================================
    # 5A. DETERMINISTIC HYPOTHESES EXIST
    # =====================================================

    if deterministic_hypotheses:

        # -------------------------------------------------
        # More than one deterministic explanation:
        # use AI as the investigation layer.
        # -------------------------------------------------

        if len(
            deterministic_hypotheses
        ) > 1:

            controller_case[
                "investigation_mode_detail"
            ] = "COMPETING_HYPOTHESES"

            try:

                ai_result = investigate_case(
                    controller_case
                )

                controller_case[
                    "ai_analysis"
                ] = ai_result

                ai_hypotheses = ai_result.get(
                    "hypotheses",
                    [],
                )

                # -------------------------------------------------
                # Preserve BOTH deterministic and AI candidates.
                # The common verification pipeline below decides
                # which candidates actually survive.
                # -------------------------------------------------

                hypotheses = _merge_hypotheses(
                    deterministic_hypotheses,
                    ai_hypotheses,
                    investigation_mode="AI",
                )

                investigation_mode = "AI"

            except Exception as error:

                # -------------------------------------------------
                # Safe fallback:
                # retain deterministic hypotheses.
                # -------------------------------------------------

                hypotheses = (
                    deterministic_hypotheses
                )

                investigation_mode = (
                    "AI_FALLBACK_DETERMINISTIC"
                )

                controller_case[
                    "ai_analysis"
                ] = {
                    "status": "AI_ERROR",
                    "error": str(error),
                }

        else:

            # -------------------------------------------------
            # Exactly one deterministic hypothesis:
            # no AI call is necessary.
            # -------------------------------------------------

            hypotheses = (
                deterministic_hypotheses
            )

            investigation_mode = (
                "DETERMINISTIC"
            )

            controller_case[
                "ai_analysis"
            ] = None

            controller_case[
                "investigation_mode_detail"
            ] = None

    # =====================================================
    # 5B. NO DETERMINISTIC HYPOTHESIS
    # =====================================================

    else:

        controller_case[
            "investigation_mode_detail"
        ] = "NO_DETERMINISTIC_HYPOTHESIS"

        investigation_mode = "AI"

        try:

            ai_result = investigate_case(
                controller_case
            )

        except Exception as error:

            controller_case[
                "ai_analysis"
            ] = {
                "status": "AI_ERROR",
                "error": str(error),
            }

            # -------------------------------------------------
            # Safe deterministic fallback.
            # -------------------------------------------------

            try:

                fallback_hypotheses = (
                    generate_deterministic_hypotheses(
                        controller_case
                    )
                )

            except Exception:

                fallback_hypotheses = []

            if fallback_hypotheses:

                hypotheses = (
                    fallback_hypotheses
                )

                deterministic_signatures = {
                    _hypothesis_signature(
                        hypothesis
                    )
                    for hypothesis in fallback_hypotheses
                }

                investigation_mode = (
                    "AI_FALLBACK_DETERMINISTIC"
                )

            else:

                controller_case[
                    "investigation_mode"
                ] = "AI"

                controller_case[
                    "verification"
                ] = []

                controller_case[
                    "resolution"
                ] = None

                controller_case[
                    "final_decision"
                ] = {
                    "decision": "HUMAN_REVIEW",
                    "reason": (
                        "AI investigation failed and "
                        "no deterministic fallback "
                        "could safely evaluate the exception."
                    ),
                    "error": str(error),
                }

                controller_case[
                    "decision_explanation"
                ] = _build_decision_explanation(
                    controller_case
                )

                return controller_case

        else:

            controller_case[
                "ai_analysis"
            ] = ai_result

            hypotheses = ai_result.get(
                "hypotheses",
                [],
            )

    # -----------------------------------------------------
    # Store investigation mode
    # -----------------------------------------------------

    controller_case[
        "investigation_mode"
    ] = investigation_mode

    # -----------------------------------------------------
    # Fill investigation detail when not already set.
    # -----------------------------------------------------

    if controller_case.get(
        "investigation_mode_detail"
    ) is None and (
        reconciliation.get(
            "reason"
        )
        == "CONFLICTING_EVIDENCE"
    ):

        controller_case[
            "investigation_mode_detail"
        ] = "COMPETING_HYPOTHESES"

    # -----------------------------------------------------
    # 6. No hypotheses
    # -----------------------------------------------------

    if not hypotheses:

        controller_case[
            "verification"
        ] = []

        controller_case[
            "resolution"
        ] = None

        controller_case[
            "final_decision"
        ] = {
            "decision": "HUMAN_REVIEW",
            "reason": (
                "No usable investigation "
                "hypothesis was produced."
            ),
        }

        controller_case[
            "decision_explanation"
        ] = _build_decision_explanation(
            controller_case
        )

        return controller_case

    # =====================================================
    # 7. VALIDATE / VERIFY / SIMULATE
    # =====================================================

    verification_results = []

    for hypothesis in hypotheses:

        hypothesis_signature = (
            _hypothesis_signature(
                hypothesis
            )
        )

        # -------------------------------------------------
        # Determine origin of candidate.
        # -------------------------------------------------

        hypothesis_investigation_mode = (
            "DETERMINISTIC"
            if hypothesis_signature
            in deterministic_signatures
            else investigation_mode
        )

        print(
            "\n----------------------------------------"
        )

        print(
            "HYPOTHESIS BEING INVESTIGATED:"
        )

        print(
            hypothesis
        )

        print(
            "----------------------------------------"
        )

        hypothesis_id = hypothesis.get(
            "hypothesis_id",
            "UNKNOWN",
        )

        relationship_type = str(
            hypothesis.get(
                "causal_relationship",
                {},
            ).get(
                "type",
                "",
            )
        ).strip().upper()

        # =================================================
        # 7A. EVIDENCE VALIDATION
        # =================================================

        if hypothesis_investigation_mode in {
            "DETERMINISTIC",
            "AI_FALLBACK_DETERMINISTIC",
        }:

            evidence_validation = (
                _build_deterministic_evidence_result(
                    hypothesis
                )
            )

        else:

            try:

                evidence_validation = (
                    validate_supporting_evidence(
                        hypothesis,
                        controller_case[
                            "evidence"
                        ],
                    )
                )

            except Exception as error:

                verification_results.append(
                    {
                        "hypothesis_id": hypothesis_id,
                        "root_cause": hypothesis.get(
                            "root_cause"
                        ),
                        "explanation": hypothesis.get(
                            "explanation"
                        ),
                        "affected_records": hypothesis.get(
                            "affected_records",
                            [],
                        ),
                        "investigation_mode": (
                            hypothesis_investigation_mode
                        ),
                        "evidence_validation": {
                            "all_citations_valid": False,
                            "validation_mode": "AI",
                            "error": str(error),
                        },
                        "causal_verification": {
                            "status": "REJECTED",
                            "reason": (
                                "Evidence validation "
                                "raised an error before "
                                "causal verification "
                                "could run."
                            ),
                        },
                        "simulation": None,
                        "final_verification_status": (
                            "REJECTED"
                        ),
                    }
                )

                continue

            # ---------------------------------------------
            # Reject invalid AI evidence.
            # ---------------------------------------------

            if not evidence_validation[
                "all_citations_valid"
            ]:

                verification_results.append(
                    {
                        "hypothesis_id": hypothesis_id,
                        "root_cause": hypothesis.get(
                            "root_cause"
                        ),
                        "explanation": hypothesis.get(
                            "explanation"
                        ),
                        "affected_records": hypothesis.get(
                            "affected_records",
                            [],
                        ),
                        "investigation_mode": (
                            hypothesis_investigation_mode
                        ),
                        "evidence_validation": (
                            evidence_validation
                        ),
                        "causal_verification": {
                            "status": "REJECTED",
                            "reason": (
                                "One or more affected "
                                "records or observed "
                                "values could not be "
                                "independently validated."
                            ),
                        },
                        "simulation": None,
                        "final_verification_status": (
                            "REJECTED"
                        ),
                    }
                )

                continue

        # =================================================
        # 7B. COMMON EVIDENCE SUPPORT GATE
        #
        # IMPORTANT:
        # This runs for deterministic candidates AND
        # AI candidates.
        # =================================================

        evidence_supported = (
            _hypothesis_has_evidence_support(
                hypothesis,
                controller_case,
            )
        )

        if not evidence_supported:

            verification_results.append(
                {
                    "hypothesis_id": hypothesis_id,
                    "root_cause": hypothesis.get(
                        "root_cause"
                    ),
                    "explanation": hypothesis.get(
                        "explanation"
                    ),
                    "affected_records": hypothesis.get(
                        "affected_records",
                        [],
                    ),
                    "investigation_mode": (
                        hypothesis_investigation_mode
                    ),
                    "evidence_validation": (
                        evidence_validation
                    ),
                    "causal_verification": {
                        "status": "NOT_SUPPORTED",
                        "reason": (
                            "The proposed hypothesis does not "
                            "have independent evidence supporting "
                            "the cited source as the cause."
                        ),
                    },
                    "simulation": None,
                    "final_verification_status": (
                        "NOT_CAUSAL"
                    ),
                }
            )

            continue

        # =================================================
        # 7C. CAUSAL VERIFICATION
        # =================================================

        if hypothesis_investigation_mode in {
            "DETERMINISTIC",
            "AI_FALLBACK_DETERMINISTIC",
        }:

            causal_result = {
                "status": "DETERMINISTIC_CANDIDATE",
                "reason": (
                    "Candidate was generated by "
                    "deterministic financial rules. "
                    "Counterfactual simulation is "
                    "required to verify the proposed "
                    "correction."
                ),
                "relationship_type": relationship_type,
            }

        else:

            try:

                causal_result = (
                    verify_causal_hypothesis(
                        hypothesis,
                        controller_case,
                    )
                )

            except Exception as error:

                verification_results.append(
                    {
                        "hypothesis_id": hypothesis_id,
                        "root_cause": hypothesis.get(
                            "root_cause"
                        ),
                        "explanation": hypothesis.get(
                            "explanation"
                        ),
                        "affected_records": hypothesis.get(
                            "affected_records",
                            [],
                        ),
                        "investigation_mode": (
                            hypothesis_investigation_mode
                        ),
                        "evidence_validation": (
                            evidence_validation
                        ),
                        "causal_verification": {
                            "status": "REJECTED",
                            "reason": (
                                "Causal verification "
                                "failed."
                            ),
                            "error": str(error),
                        },
                        "simulation": None,
                        "final_verification_status": (
                            "REJECTED"
                        ),
                    }
                )

                continue

        # =================================================
        # 7D. COUNTERFACTUAL SIMULATION
        # =================================================

        simulation_result = None

        simulation_allowed = (
            hypothesis_investigation_mode in {
                "DETERMINISTIC",
                "AI_FALLBACK_DETERMINISTIC",
            }
            or causal_result.get(
                "status"
            ) in {
                "CAUSAL_CANDIDATE",
                "PENDING_SIMULATION",
                "PENDING_DUPLICATE_VERIFICATION",
            }
        )

        if simulation_allowed:

            try:

                simulation_result = (
                    _simulate_hypothesis(
                        controller_case,
                        hypothesis,
                    )
                )

                print(
                    "\nSIMULATION RESULT:"
                )

                print(
                    simulation_result
                )

            except Exception as error:

                simulation_result = {
                    "status": "FAILED",
                    "exception_cleared": False,
                    "reason": (
                        "Counterfactual simulation "
                        "failed."
                    ),
                    "error": str(error),
                }

                print(
                    "\nSIMULATION ERROR:"
                )

                print(
                    simulation_result
                )

        # =================================================
        # 7E. FINAL VERIFICATION STATUS
        # =================================================

        if (
            simulation_result is not None
            and simulation_result.get(
                "exception_cleared"
            ) is True
        ):

            # -------------------------------------------------
            # Deterministic candidates keep the original
            # deterministic behavior.
            # -------------------------------------------------

            if hypothesis_investigation_mode in {
                "DETERMINISTIC",
                "AI_FALLBACK_DETERMINISTIC",
            }:

                final_verification_status = (
                    "DETERMINISTICALLY_SUPPORTED"
                )

            # -------------------------------------------------
            # Genuine AI candidates must pass the additional
            # auto-resolution safety gate.
            # -------------------------------------------------

            else:

                (
                    auto_resolution_allowed,
                    auto_resolution_reason,
                ) = _auto_resolution_allowed(
                    hypothesis,
                    controller_case,
                )

                if not auto_resolution_allowed:

                    final_verification_status = (
                        "SUPPORTED_BUT_REQUIRES_REVIEW"
                    )

                else:

                    final_verification_status = (
                        "CAUSALLY_SUPPORTED"
                    )

        elif (
            simulation_result is not None
            and simulation_result.get(
                "exception_cleared"
            ) is False
        ):

            final_verification_status = (
                "NOT_CAUSAL"
            )

        else:

            final_verification_status = (
                causal_result.get(
                    "status",
                    "UNVERIFIED",
                )
            )

        # =================================================
        # 7F. STORE RESULT
        # =================================================

        verification_results.append(
            {
                "hypothesis_id": hypothesis_id,

                "root_cause": hypothesis.get(
                    "root_cause"
                ),

                "explanation": hypothesis.get(
                    "explanation"
                ),

                "affected_records": hypothesis.get(
                    "affected_records",
                    [],
                ),

                "investigation_mode": (
                    hypothesis_investigation_mode
                ),

                "evidence_validation": (
                    evidence_validation
                ),

                "causal_verification": (
                    causal_result
                ),

                "simulation": (
                    simulation_result
                ),

                "final_verification_status": (
                    final_verification_status
                ),
            }
        )

    # =====================================================
    # 8. FIND SUCCESSFUL HYPOTHESES
    # =====================================================

    successful_hypotheses = [
        result
        for result in verification_results
        if result[
            "final_verification_status"
        ] in {
            "CAUSALLY_SUPPORTED",
            "DETERMINISTICALLY_SUPPORTED",
        }
    ]

    print(
        "\nSuccessful hypotheses:"
    )

    for result in successful_hypotheses:

        print(
            result[
                "hypothesis_id"
            ]
        )

    # =====================================================
    # 9. CONTROLLER DECISION
    # =====================================================

    if len(
        successful_hypotheses
    ) == 1:

        selected = (
            successful_hypotheses[0]
        )

        controller_case[
            "resolution"
        ] = {
            "status": (
                "RESOLUTION_CANDIDATE"
            ),
            "hypothesis_id": (
                selected[
                    "hypothesis_id"
                ]
            ),
            "investigation_mode": (
                selected[
                    "investigation_mode"
                ]
            ),
            "verification_status": (
                selected[
                    "final_verification_status"
                ]
            ),
            "simulation": (
                selected[
                    "simulation"
                ]
            ),
        }

        controller_case[
            "final_decision"
        ] = {
            "decision": (
                "RESOLUTION_CANDIDATE"
            ),
            "reason": (
                "Exactly one hypothesis "
                "survived the evidence/verification "
                "pipeline and cleared counterfactual "
                "simulation."
            ),
        }

    elif len(
        successful_hypotheses
    ) > 1:

        controller_case[
            "resolution"
        ] = None

        controller_case[
            "final_decision"
        ] = {
            "decision": "HUMAN_REVIEW",
            "reason": (
                "Multiple hypotheses survived "
                "counterfactual simulation. "
                "The controller cannot safely "
                "select one explanation."
            ),
        }

    else:

        controller_case[
            "resolution"
        ] = None

        controller_case[
            "final_decision"
        ] = {
            "decision": "HUMAN_REVIEW",
            "reason": (
                "No hypothesis successfully "
                "cleared counterfactual simulation."
            ),
        }

    # =====================================================
    # 10. STORE RESULTS
    # =====================================================

    controller_case[
        "verification"
    ] = verification_results

    controller_case[
        "decision_explanation"
    ] = _build_decision_explanation(
        controller_case
    )

    return controller_case

# =========================================================
# END-TO-END BATCH TEST
# =========================================================

if __name__ == "__main__":

    data = load_exception_data()

    payment_view = (
        build_reconciliation_view(
            data
        )
    )

    exception_rows = payment_view[
        payment_view[
            "final_status"
        ]
        == "EXCEPTION"
    ]
    payment_ids = [
    payment_id
    for payment_id in (
        exception_rows[
            "payment_id"
        ]
        .astype(str)
        .tolist()
    )
    if not payment_id.endswith("_DUP")
    ]
    print(
        "\n========================================"
    )

    print(
        "END-TO-END CONTROLLER BATCH TEST"
    )

    print(
        "========================================"
    )

    summary = []

    for payment_id in payment_ids:

        print(
            f"\n\nProcessing {payment_id}"
        )

        try:

            case = (
                build_controller_case_for_payment(
                    data,
                    payment_view,
                    payment_id,
                )
            )

            result = (
                investigate_controller_case(
                    case
                )
            )

            decision = result[
                "final_decision"
            ]

            summary.append(
                {
                    "payment_id": payment_id,

                    "exception_reason": (
                        result[
                            "financial_facts"
                        ][
                            "reconciliation"
                        ][
                            "reason"
                        ]
                    ),

                    "investigation_mode": (
                        result.get(
                            "investigation_mode"
                        )
                    ),

                    "decision": (
                        decision.get(
                            "decision"
                        )
                    ),

                    "resolution_hypothesis": (
                        (
                            result.get(
                                "resolution"
                            )
                            or {}
                        ).get(
                            "hypothesis_id"
                        )
                    ),
                }
            )

            print(
                "\nFinal Decision:"
            )

            print(
                decision
            )

            print(
                "\nDecision Explanation:"
            )

            print(
                result.get(
                    "decision_explanation",
                    {},
                )
            )

        except Exception as error:

            print(
                f"ERROR processing "
                f"{payment_id}: {error}"
            )

            summary.append(
                {
                    "payment_id": payment_id,
                    "exception_reason": "ERROR",
                    "investigation_mode": "ERROR",
                    "decision": "ERROR",
                    "resolution_hypothesis": None,
                    "error": str(error),
                }
            )

    # -----------------------------------------------------
    # Batch summary
    # -----------------------------------------------------

    print(
        "\n========================================"
    )

    print(
        "CONTROLLER SUMMARY"
    )

    print(
        "========================================"
    )

    for item in summary:

        print(
            f"{item['payment_id']} | "
            f"{item['exception_reason']} | "
            f"{item['investigation_mode']} | "
            f"{item['decision']} | "
            f"{item['resolution_hypothesis']}"
        )