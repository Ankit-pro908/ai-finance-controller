from typing import Any

import pandas as pd

from src.reconciliation.engine import (
    build_payment_view,
    calculate_expected_settlement,
    classify_reconciliation,
    identify_exception_reason,
    validate_ledger,
    build_exception_report,
)


TOLERANCE = 0.01


# =========================================================
# SOURCE MAP
# =========================================================

SOURCE_MAP = {
    "payment": (
        "payments",
        "payment_id",
    ),
    "fee": (
        "fees",
        "fee_id",
    ),
    "refund": (
        "refunds",
        "refund_id",
    ),
    "settlement": (
        "settlements",
        "settlement_id",
    ),
    "ledger": (
        "ledger",
        "ledger_id",
    ),
}


# =========================================================
# NUMERIC HELPERS
# =========================================================

def _close(
    first: Any,
    second: Any,
) -> bool:
    """
    Compare two numeric values using financial tolerance.
    """

    try:
        return (
            abs(
                float(first)
                - float(second)
            )
            <= TOLERANCE
        )

    except (
        TypeError,
        ValueError,
    ):
        return False


def _to_float(
    value: Any,
) -> float | None:
    """
    Safely convert a value to float.
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


# =========================================================
# RECONCILIATION
# =========================================================

def _reconcile_payment(
    data: dict[str, pd.DataFrame],
    payment_id: str,
) -> dict[str, Any]:
    """
    Run the real reconciliation engine against the
    supplied dataset.

    The dataset may be the original data or a simulated
    deep copy.
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

    return {
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


# =========================================================
# RECORD HELPERS
# =========================================================

def _find_record(
    data: dict[str, pd.DataFrame],
    source: str,
    record_id: str,
) -> tuple[pd.DataFrame | None, Any, Any]:
    """
    Find one source record.

    Returns:

        dataframe
        row_index
        row

    or:

        None, None, None
    """

    if source not in SOURCE_MAP:
        return (
            None,
            None,
            None,
        )

    dataframe_name, id_column = (
        SOURCE_MAP[source]
    )

    dataframe = data.get(
        dataframe_name
    )

    if dataframe is None:
        return (
            None,
            None,
            None,
        )

    if dataframe.empty:
        return (
            dataframe,
            None,
            None,
        )

    if id_column not in dataframe.columns:
        return (
            dataframe,
            None,
            None,
        )

    matching_rows = dataframe[
        dataframe[
            id_column
        ].astype(str)
        == str(record_id)
    ]

    if matching_rows.empty:
        return (
            dataframe,
            None,
            None,
        )

    if len(matching_rows) > 1:
        raise ValueError(
            f"Multiple records found for "
            f"{source}/{record_id}."
        )

    row_index = (
        matching_rows.index[0]
    )

    return (
        dataframe,
        row_index,
        dataframe.loc[
            row_index
        ],
    )


def _next_record_id(
    dataframe: pd.DataFrame,
    prefix: str,
) -> str:
    """
    Create a deterministic new record ID.
    """

    if dataframe.empty:
        return (
            f"{prefix}00001"
        )

    numbers = []

    for value in dataframe.iloc[:, 0]:

        text = str(value)

        digits = ""

        for character in text[::-1]:

            if character.isdigit():
                digits = (
                    character
                    + digits
                )

            else:
                break

        if digits:
            numbers.append(
                int(digits)
            )

    next_number = (
        max(numbers) + 1
        if numbers
        else 1
    )

    return (
        f"{prefix}{next_number:05d}"
    )

def _normalize_proposed_changes(
    data: dict[str, pd.DataFrame],
    payment_id: str,
    hypothesis: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """
    Convert a hypothesis into generic simulation operations.

    Supported operations:

        SET_VALUE
        ADD_RECORD
        REMOVE_RECORD

    The operation is derived from the hypothesis relationship
    type rather than from a payment-specific rule.
    """

    causal_relationship = (
        hypothesis.get(
            "causal_relationship",
            {},
        )
    )

    relationship_type = str(
        causal_relationship.get(
            "type",
            "RECORD_DELTA",
        )
    ).strip().upper()

    affected_records = (
        hypothesis.get(
            "affected_records",
            [],
        )
    )

    valid_changes = []
    errors = []

    # -----------------------------------------------------
    # SET_VALUE
    # -----------------------------------------------------

    if relationship_type == "RECORD_DELTA":

        for index, record in enumerate(
            affected_records,
            start=1,
        ):

            source = str(
                record.get(
                    "source",
                    "",
                )
            ).strip().lower()

            record_id = record.get(
                "record_id"
            )

            field = str(
                record.get(
                    "field",
                    "",
                )
            ).strip()

            observed_value = record.get(
                "observed_value"
            )

            proposed_value = record.get(
                "proposed_value"
            )

            if proposed_value is None:
                continue

            if record_id is None:
                errors.append(
                    {
                        "index": index,
                        "operation": "SET_VALUE",
                        "reason": (
                            "SET_VALUE requires "
                            "an existing record_id."
                        ),
                    }
                )
                continue

            if source not in SOURCE_MAP:
                errors.append(
                    {
                        "index": index,
                        "operation": "SET_VALUE",
                        "reason": (
                            f"Unsupported source: "
                            f"{source}"
                        ),
                    }
                )
                continue

            if not field:
                errors.append(
                    {
                        "index": index,
                        "operation": "SET_VALUE",
                        "reason": (
                            "SET_VALUE requires "
                            "a field."
                        ),
                    }
                )
                continue

            if _close(
                observed_value,
                proposed_value,
            ):
                continue

            valid_changes.append(
                {
                    "operation": "SET_VALUE",
                    "source": source,
                    "record_id": str(
                        record_id
                    ),
                    "field": field,
                    "observed_value": (
                        observed_value
                    ),
                    "proposed_value": (
                        proposed_value
                    ),
                }
            )

        return (
            valid_changes,
            errors,
        )

    # -----------------------------------------------------
    # ADD_RECORD
    # -----------------------------------------------------

    if relationship_type == "MISSING_RECORD":

        if not affected_records:
            errors.append(
                {
                    "operation": "ADD_RECORD",
                    "reason": (
                        "MISSING_RECORD does not "
                        "identify the missing event."
                    ),
                }
            )

            return (
                valid_changes,
                errors,
            )

        payment_df = data.get(
            "payments",
            pd.DataFrame(),
        )

        payment_rows = (
            payment_df[
                payment_df[
                    "payment_id"
                ].astype(str)
                == str(payment_id)
            ]
            if (
                not payment_df.empty
                and "payment_id"
                in payment_df.columns
            )
            else pd.DataFrame()
        )

        if payment_rows.empty:
            errors.append(
                {
                    "operation": "ADD_RECORD",
                    "reason": (
                        f"Payment {payment_id} "
                        "not found."
                    ),
                }
            )

            return (
                valid_changes,
                errors,
            )

        payment_row = (
            payment_rows.iloc[0]
        )

        expected_amount = _to_float(
            causal_relationship.get(
                "claimed_delta"
            )
        )

        if expected_amount is None:

            expected_amount = _to_float(
                hypothesis.get(
                    "expected_amount"
                )
            )

        if expected_amount is None:

            expected_amount = 0.0

        # -------------------------------------------------
        # Determine missing source from the hypothesis.
        # -------------------------------------------------

        source = "settlement"

        for record in affected_records:

            candidate_source = str(
                record.get(
                    "source",
                    "",
                )
            ).strip().lower()

            role = str(
                record.get(
                    "role",
                    "",
                )
            ).upper()

            # -------------------------------------------------
            # Missing ledger record
            # -------------------------------------------------

            if candidate_source == "ledger":

                source = "ledger"

                # ---------------------------------------------
                # Missing payment ledger entry
                # ---------------------------------------------

                if "PAYMENT" in role:

                    entry_type = "PAYMENT"

                    amount = _to_float(
                        payment_row.get(
                            "amount"
                        )
                    )

                    if amount is None:
                        amount = expected_amount

                # ---------------------------------------------
                # Missing refund ledger entry
                # ---------------------------------------------

                elif "REFUND" in role:

                    entry_type = "REFUND"

                    amount = -abs(
                        expected_amount
                    )

                # ---------------------------------------------
                # Missing settlement ledger entry
                # ---------------------------------------------

                elif "SETTLEMENT" in role:

                    entry_type = "SETTLEMENT"

                    amount = _to_float(
                        hypothesis.get(
                            "settlement_amount"
                        )
                    )

                    if amount is None:
                        amount = expected_amount

                # ---------------------------------------------
                # Unknown ledger event
                # ---------------------------------------------

                else:

                    entry_type = "SETTLEMENT"

                    amount = expected_amount

                valid_changes.append(
                    {
                        "operation": "ADD_RECORD",
                        "source": "ledger",
                        "record_id": None,
                        "field": "amount",
                        "observed_value": None,
                        "proposed_value": amount,
                        "entry_type": entry_type,
                        "payment_id": payment_id,
                    }
                )

                break

            # -------------------------------------------------
            # Missing settlement record
            # -------------------------------------------------

            if candidate_source == "settlement":

                valid_changes.append(
                    {
                        "operation": "ADD_RECORD",
                        "source": "settlement",
                        "record_id": None,
                        "field": "settlement_amount",
                        "observed_value": None,
                        "proposed_value": expected_amount,
                        "payment_id": payment_id,
                    }
                )

                break

        return (
            valid_changes,
            errors,
        )

    # -----------------------------------------------------
    # REMOVE_RECORD
    # -----------------------------------------------------

    if relationship_type == "DUPLICATE_RECORD":

        if len(affected_records) < 2:
            errors.append(
                {
                    "operation": "REMOVE_RECORD",
                    "reason": (
                        "DUPLICATE_RECORD requires "
                        "at least two records."
                    ),
                }
            )

            return (
                valid_changes,
                errors,
            )

        # The deterministic resolver marks the survivor
        # with proposed_value=None. Other records become
        # duplicate candidates.
        for index, record in enumerate(
            affected_records,
            start=1,
        ):

            record_id = record.get(
                "record_id"
            )

            if record_id is None:
                continue

            proposed_value = record.get(
                "proposed_value"
            )

            role = str(
                record.get(
                    "role",
                    "",
                )
            ).upper()

            # Never remove the record explicitly marked as the
            # survivor. Only an actual duplicate record may be
            # converted into REMOVE_RECORD.
            if "SURVIVOR" in role:
                continue

            if (
                "DUPLICATE" in role
                or proposed_value is not None
            ):

                valid_changes.append(
                    {
                        "operation": (
                            "REMOVE_RECORD"
                        ),
                        "source": str(
                            record.get(
                                "source",
                                "",
                            )
                        ).strip().lower(),
                        "record_id": str(
                            record_id
                        ),
                        "field": str(
                            record.get(
                                "field",
                                "",
                            )
                        ).strip(),
                    }
                )

        return (
            valid_changes,
            errors,
        )

    errors.append(
        {
            "operation": None,
            "reason": (
                f"Unsupported relationship type: "
                f"{relationship_type}"
            ),
        }
    )

    return (
        valid_changes,
        errors,
    )

# =========================================================
# APPLY SET_VALUE
# =========================================================

def _apply_set_value(
    data: dict[str, pd.DataFrame],
    change: dict[str, Any],
) -> dict[str, Any]:
    """
    Apply SET_VALUE to an existing record.
    """

    source = change[
        "source"
    ]

    record_id = change[
        "record_id"
    ]

    field = change[
        "field"
    ]

    proposed_value = change[
        "proposed_value"
    ]

    dataframe, row_index, row = (
        _find_record(
            data,
            source,
            record_id,
        )
    )

    if dataframe is None:
        return {
            "status": "FAILED",
            "reason": (
                f"Unsupported source: {source}"
            ),
        }

    if row_index is None:
        return {
            "status": "FAILED",
            "reason": (
                f"Record not found: "
                f"{source}/{record_id}"
            ),
        }

    if field not in dataframe.columns:
        return {
            "status": "FAILED",
            "reason": (
                f"Field '{field}' not found "
                f"in {source}."
            ),
        }

    old_value = dataframe.at[
        row_index,
        field,
    ]

    dataframe.at[
        row_index,
        field,
    ] = proposed_value

    return {
        "status": "APPLIED",
        "operation": "SET_VALUE",
        "source": source,
        "record_id": record_id,
        "field": field,
        "old_value": old_value,
        "new_value": proposed_value,
    }


# =========================================================
# APPLY ADD_RECORD
# =========================================================

def _apply_add_record(
    data: dict[str, pd.DataFrame],
    payment_id: str,
    change: dict[str, Any],
) -> dict[str, Any]:
    """
    Add a missing settlement or ledger record.

    Record identity and timestamps are generated by the
    simulator rather than by the AI.
    """

    source = change[
        "source"
    ]

    proposed_value = _to_float(
        change.get(
            "proposed_value"
        )
    )

    if proposed_value is None:
        return {
            "status": "FAILED",
            "reason": (
                "ADD_RECORD requires "
                "a numeric proposed value."
            ),
        }

    dataframe_name, _ = (
        SOURCE_MAP[source]
    )

    dataframe = data.get(
        dataframe_name
    )

    if dataframe is None:
        return {
            "status": "FAILED",
            "reason": (
                f"Dataset not found: "
                f"{dataframe_name}"
            ),
        }

    payment_df = data.get(
        "payments",
        pd.DataFrame(),
    )

    payment_rows = (
        payment_df[
            payment_df[
                "payment_id"
            ].astype(str)
            == str(payment_id)
        ]
        if (
            not payment_df.empty
            and "payment_id"
            in payment_df.columns
        )
        else pd.DataFrame()
    )

    if payment_rows.empty:
        return {
            "status": "FAILED",
            "reason": (
                f"Payment {payment_id} "
                "not found."
            ),
        }

    payment_row = (
        payment_rows.iloc[0]
    )

    # -----------------------------------------------------
    # ADD settlement
    # -----------------------------------------------------

    if source == "settlement":

        new_id = _next_record_id(
            dataframe,
            "SET",
        )

        created_at = payment_row.get(
            "created_at"
        )

        new_row = {
            "settlement_id": new_id,
            "payment_id": payment_id,
            "settlement_amount": proposed_value,
            "settlement_date": created_at,
            "status": "SETTLED",
        }

        data[dataframe_name] = pd.concat(
            [
                dataframe,
                pd.DataFrame(
                    [new_row]
                ),
            ],
            ignore_index=True,
        )

        return {
            "status": "APPLIED",
            "operation": "ADD_RECORD",
            "source": "settlement",
            "record_id": new_id,
            "new_record": new_row,
        }

    # -----------------------------------------------------
    # ADD ledger
    # -----------------------------------------------------

    if source == "ledger":

        new_id = _next_record_id(
            dataframe,
            "LED",
        )

        entry_type = change.get(
            "entry_type",
            "SETTLEMENT",
        )

        created_at = payment_row.get(
            "created_at"
        )

        new_row = {
            "ledger_id": new_id,
            "payment_id": payment_id,
            "entry_type": entry_type,
            "amount": proposed_value,
            "created_at": created_at,
        }

        data[dataframe_name] = pd.concat(
            [
                dataframe,
                pd.DataFrame(
                    [new_row]
                ),
            ],
            ignore_index=True,
        )

        return {
            "status": "APPLIED",
            "operation": "ADD_RECORD",
            "source": "ledger",
            "record_id": new_id,
            "new_record": new_row,
        }

    return {
        "status": "FAILED",
        "reason": (
            f"ADD_RECORD is not supported "
            f"for source '{source}'."
        ),
    }


# =========================================================
# APPLY REMOVE_RECORD
# =========================================================

def _apply_remove_record(
    data: dict[str, pd.DataFrame],
    change: dict[str, Any],
) -> dict[str, Any]:
    """
    Remove an existing duplicate record from the simulation
    copy.
    """

    source = change[
        "source"
    ]

    record_id = change[
        "record_id"
    ]

    dataframe_name, id_column = (
        SOURCE_MAP[source]
    )

    dataframe = data.get(
        dataframe_name
    )

    if dataframe is None:
        return {
            "status": "FAILED",
            "reason": (
                f"Dataset not found: "
                f"{dataframe_name}"
            ),
        }

    matching_rows = dataframe[
        dataframe[
            id_column
        ].astype(str)
        == str(record_id)
    ]

    if matching_rows.empty:
        return {
            "status": "FAILED",
            "reason": (
                f"Record not found: "
                f"{source}/{record_id}"
            ),
        }

    if len(matching_rows) > 1:
        return {
            "status": "FAILED",
            "reason": (
                f"Multiple records found for "
                f"{source}/{record_id}"
            ),
        }

    row_index = matching_rows.index[0]

    removed_record = (
        dataframe.loc[
            row_index
        ].to_dict()
    )

    data[dataframe_name] = (
        dataframe.drop(
            index=row_index
        ).reset_index(
            drop=True
        )
    )

    return {
        "status": "APPLIED",
        "operation": "REMOVE_RECORD",
        "source": source,
        "record_id": record_id,
        "removed_record": removed_record,
    }


# =========================================================
# APPLY GENERIC CHANGE
# =========================================================

def _apply_change(
    data: dict[str, pd.DataFrame],
    payment_id: str,
    change: dict[str, Any],
) -> dict[str, Any]:
    """
    Dispatch one generic simulation operation.
    """

    operation = change.get(
        "operation"
    )

    if operation == "SET_VALUE":

        return _apply_set_value(
            data,
            change,
        )

    if operation == "ADD_RECORD":

        return _apply_add_record(
            data,
            payment_id,
            change,
        )

    if operation == "REMOVE_RECORD":

        return _apply_remove_record(
            data,
            change,
        )

    return {
        "status": "FAILED",
        "reason": (
            f"Unsupported simulation "
            f"operation: {operation}"
        ),
    }


# =========================================================
# MAIN SIMULATOR
# =========================================================

def simulate_hypothesis(
    data: dict[str, pd.DataFrame],
    payment_id: str,
    hypothesis: dict[str, Any],
) -> dict[str, Any]:
    """
    Perform a full counterfactual simulation.

    Supported operations:

        SET_VALUE
        ADD_RECORD
        REMOVE_RECORD

    The original dataset is never mutated.
    """

    # -----------------------------------------------------
    # 1. Convert hypothesis into operations
    # -----------------------------------------------------

    changes, extraction_errors = (
        _normalize_proposed_changes(
            data=data,
            payment_id=payment_id,
            hypothesis=hypothesis,
        )
    )

    if extraction_errors:
        return {
            "status": "FAILED",
            "exception_cleared": False,
            "reason": (
                "One or more proposed changes "
                "could not be interpreted."
            ),
            "errors": extraction_errors,
        }

    if not changes:
        return {
            "status": "NOT_SIMULATABLE",
            "exception_cleared": False,
            "reason": (
                "Hypothesis contains no "
                "simulatable changes."
            ),
        }

    # -----------------------------------------------------
    # 2. Deep copy all source datasets
    # -----------------------------------------------------

    simulated_data = {
        key: dataframe.copy(
            deep=True
        )
        for key, dataframe in data.items()
    }

    # -----------------------------------------------------
    # 3. Reconcile BEFORE changes
    # -----------------------------------------------------

    before = _reconcile_payment(
        simulated_data,
        payment_id,
    )

    # -----------------------------------------------------
    # 4. Apply every operation
    # -----------------------------------------------------

    applied_changes = []

    for change in changes:

        result = _apply_change(
            simulated_data,
            payment_id,
            change,
        )

        if result[
            "status"
        ] != "APPLIED":

            return {
                "status": "FAILED",
                "exception_cleared": False,
                "reason": (
                    "A proposed simulation "
                    "operation could not "
                    "be applied."
                ),
                "before": before,
                "applied_changes": (
                    applied_changes
                ),
                "failed_change": change,
                "failure": result,
            }

        applied_changes.append(
            result
        )

    # -----------------------------------------------------
    # 5. Reconcile AFTER changes
    # -----------------------------------------------------

    after = _reconcile_payment(
        simulated_data,
        payment_id,
    )

    # -----------------------------------------------------
    # 6. Determine outcome
    # -----------------------------------------------------

    exception_cleared = (
        after[
            "final_status"
        ]
        == "MATCH"
    )

    before_difference = before.get(
        "difference"
    )

    after_difference = after.get(
        "difference"
    )

    difference_improved = False

    if (
        before_difference is not None
        and after_difference is not None
    ):

        try:

            difference_improved = (
                abs(
                    float(
                        after_difference
                    )
                )
                <
                abs(
                    float(
                        before_difference
                    )
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            difference_improved = False

    return {
        "status": (
            "SUCCESS"
            if exception_cleared
            else "NO_RESOLUTION"
        ),
        "exception_cleared": (
            exception_cleared
        ),
        "difference_improved": (
            difference_improved
        ),
        "change_count": len(
            applied_changes
        ),
        "applied_changes": (
            applied_changes
        ),
        "before": before,
        "after": after,
    }


# =========================================================
# BACKWARD COMPATIBILITY
# =========================================================

def simulate_direct_value_change(
    data: dict[str, pd.DataFrame],
    payment_id: str,
    affected_record: dict[str, Any],
    target_value: Any,
) -> dict[str, Any]:
    """
    Backward-compatible wrapper for the old simulator API.
    """

    simulation_record = {
        **affected_record,
        "proposed_value": target_value,
    }

    hypothesis = {
        "hypothesis_id": (
            "DIRECT_CHANGE"
        ),
        "affected_records": [
            simulation_record
        ],
        "causal_relationship": {
            "type": "RECORD_DELTA",
            "claimed_delta": None,
            "direction": "UNKNOWN",
        },
    }

    return simulate_hypothesis(
        data=data,
        payment_id=payment_id,
        hypothesis=hypothesis,
    )