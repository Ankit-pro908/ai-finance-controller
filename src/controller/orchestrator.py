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
) -> list[dict[str, Any]]:
    """
    Combine deterministic and AI-proposed hypotheses,
    preserving deterministic candidates even when the AI
    response omits or reformulates them.

    Deduplication is by content signature, not by
    hypothesis_id, so a stochastic AI re-labeling of the
    same explanation does not produce a duplicate.
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

        seen.add(signature)
        merged.append(hypothesis)

    return merged


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

    Pipeline:

        Controller Case
              ↓
        Deterministic Reconciliation
              ↓
        MATCH
              ↓
        AUTO_CLOSED

        EXCEPTION
              ↓
        Deterministic Resolver
              ↓
        Candidate found?
           /       \
         YES       NO
          ↓         ↓
     Simulation     AI
                    ↓
              Evidence Validation
                    ↓
              Causal Verification
                    ↓
                Simulation
                    ↓
               Final Decision

    The AI never makes the final financial decision.
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
        ] = (
            _build_decision_explanation(
                controller_case
            )
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

    if deterministic_hypotheses:

        # -------------------------------------------------
        # First inspect whether the deterministic resolver
        # produced more than one competing explanation.
        #
        # If yes, use AI to compare the hypotheses instead
        # of automatically selecting a deterministic path.
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

                # -------------------------------------
                # Preserve deterministic candidates.
                #
                # The AI acts as a comparator, not the
                # sole source of truth: its hypotheses
                # are merged with (not substituted for)
                # the deterministic candidates already
                # found, so a stochastic/partial AI
                # response can never silently drop a
                # valid deterministic explanation.
                # -------------------------------------

                hypotheses = _merge_hypotheses(
                    deterministic_hypotheses,
                    ai_hypotheses,
                )
                investigation_mode = "AI"

            except Exception as error:

                # -------------------------------------------------
                # Safe fallback:
                # keep deterministic candidates so the controller
                # can still test them through simulation.
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
            # no API call is necessary.
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

    else:

        # -----------------------------------------------------
        # 6. AI FALLBACK
        # -----------------------------------------------------

        investigation_mode = "AI"

        controller_case[
            "investigation_mode_detail"
        ] = "NO_DETERMINISTIC_HYPOTHESIS"

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
            # SAFE DETERMINISTIC FALLBACK
            # -------------------------------------------------

            fallback_hypotheses = (
                generate_deterministic_hypotheses(
                    controller_case
                )
            )

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

    controller_case[
        "investigation_mode"
    ] = investigation_mode

    # -----------------------------------------------------
    # Fill in investigation_mode_detail only if the
    # candidate-source logic above did not already set a
    # more specific signal. This keeps PAY00007-style
    # CONFLICTING_EVIDENCE cases labeled even when they
    # arrive through a path that didn't already flag them,
    # without clobbering "COMPETING_HYPOTHESES" or
    # "NO_DETERMINISTIC_HYPOTHESIS" set above.
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
    # 7. No hypotheses
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

    # -----------------------------------------------------
    # 8. Validate / verify / simulate
    # -----------------------------------------------------

    verification_results = []

    for hypothesis in hypotheses:
        hypothesis_signature = (
            _hypothesis_signature(
            hypothesis
            )
        )

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

        # -------------------------------------------------
        # 8A. Evidence validation
        # -------------------------------------------------

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
                        "hypothesis_id": (
                            hypothesis_id
                        ),

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
                            investigation_mode
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
            # Reject invalid AI evidence
            # ---------------------------------------------

            if not evidence_validation[
                "all_citations_valid"
            ]:

                verification_results.append(
                    {
                        "hypothesis_id": (
                            hypothesis_id
                        ),

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
                            investigation_mode
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

        # -------------------------------------------------
        # 8B. DETERMINISTIC CANDIDATE
        #
        # Deterministic resolver has already established
        # the financial relationship.
        #
        # Do NOT force single-record corrections through
        # the AI RECORD_DELTA verifier.
        # -------------------------------------------------

        if hypothesis_investigation_mode in {
            "DETERMINISTIC",
            "AI_FALLBACK_DETERMINISTIC",
        }:
        

            causal_result = {
                "status": (
                    "DETERMINISTIC_CANDIDATE"
                ),
                "reason": (
                    "Candidate was generated by "
                    "deterministic financial rules. "
                    "Counterfactual simulation is "
                    "required to verify the proposed "
                    "correction."
                ),
                "relationship_type": (
                    relationship_type
                ),
            }

        else:

            # -------------------------------------------------
            # 8C. AI causal verification
            # -------------------------------------------------

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
                        "hypothesis_id": (
                            hypothesis_id
                        ),

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
                            investigation_mode
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

        # -------------------------------------------------
        # 8D. Determine whether simulation should run
        # -------------------------------------------------

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

        # -------------------------------------------------
        # 8E. Final verification status
        # -------------------------------------------------

        if (
            simulation_result is not None
            and simulation_result.get(
                "exception_cleared"
            ) is True
        ):
            if hypothesis_investigation_mode in {
                    "DETERMINISTIC",
                    "AI_FALLBACK_DETERMINISTIC",
            }:

                final_verification_status = (
                    "DETERMINISTICALLY_SUPPORTED"
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

        # -------------------------------------------------
        # 8F. Store result
        # -------------------------------------------------

        verification_results.append(
            {
                "hypothesis_id": (
                    hypothesis_id
                ),

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

    # -----------------------------------------------------
    # 9. Find successful hypotheses
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Debug visibility
    # -----------------------------------------------------

    print(
        "\nSuccessful hypotheses:"
    )

    for result in successful_hypotheses:

        print(
            result[
                "hypothesis_id"
            ]
        )

    # -----------------------------------------------------
    # 10. Controller decision
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # 11. Store all verification results
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Run every exception dynamically.
    #
    # No payment IDs are hardcoded here.
    # -----------------------------------------------------

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