def check_evidence_consistency(evidence: dict):

    fees_df = evidence["fees"]
    refunds_df = evidence["refunds"]
    settlement_df = evidence["settlement"]
    ledger_df = evidence["ledger"]

    checks = {}
    conflicts = []

    # -------------------------------------------------
    # Calculate source totals
    # -------------------------------------------------

    fee_total = (
        round(
            fees_df["fee_amount"].sum(),
            2,
        )
        if not fees_df.empty
        else 0.00
    )

    refund_total = (
        round(
            refunds_df["refund_amount"].sum(),
            2,
        )
        if not refunds_df.empty
        else 0.00
    )

    ledger_fee_total = (
        round(
            abs(
                ledger_df.loc[
                    ledger_df["entry_type"] == "FEE",
                    "amount",
                ].sum()
            ),
            2,
        )
        if not ledger_df.empty
        else 0.00
    )

    ledger_refund_total = (
        round(
            abs(
                ledger_df.loc[
                    ledger_df["entry_type"] == "REFUND",
                    "amount",
                ].sum()
            ),
            2,
        )
        if not ledger_df.empty
        else 0.00
    )

    # -------------------------------------------------
    # 1. Fee consistency
    # -------------------------------------------------

    checks["fee_ledger_consistent"] = (
        fee_total == ledger_fee_total
    )

    # -------------------------------------------------
    # 2. Refund consistency
    # -------------------------------------------------

    checks["refund_ledger_consistent"] = (
        refund_total == ledger_refund_total
    )

    # -------------------------------------------------
    # 3. Settlement vs ledger
    # -------------------------------------------------

    settlement_amount = None

    ledger_net = None

    settlement_ledger_difference = None

    if settlement_df.empty:

        checks["settlement_present"] = False

        conflicts.append(
            {
                "type": "SETTLEMENT_MISSING",
            }
        )

    else:

        checks["settlement_present"] = True

        settlement_amount = round(
            settlement_df[
                "settlement_amount"
            ].sum(),
            2,
        )

        ledger_net = round(
            ledger_df["amount"].sum()
            if not ledger_df.empty
            else 0.00,
            2,
        )

        settlement_ledger_difference = round(
            ledger_net - settlement_amount,
            2,
        )

        # -------------------------------------------------
        # The normal situation:
        #
        # Ledger net == settlement
        # -------------------------------------------------

        checks[
            "settlement_ledger_consistent"
        ] = (
            abs(
                settlement_ledger_difference
            ) <= 0.01
        )

    # -------------------------------------------------
    # 4. Detect ambiguous explanations
    # -------------------------------------------------
    #
    # Example:
    #
    # Settlement variance = ₹500
    # Extra fee            = ₹500
    # Unposted refund      = ₹500
    #
    # Both explanations fit the same discrepancy.
    # -------------------------------------------------

    ambiguous_explanations = []

    if (
        settlement_ledger_difference is not None
        and abs(
            settlement_ledger_difference
        ) > 0.01
    ):

        variance = abs(
            settlement_ledger_difference
        )

        # Extra fee not represented in ledger
        extra_fee = round(
            fee_total - ledger_fee_total,
            2,
        )

        if abs(extra_fee - variance) <= 0.01:
            ambiguous_explanations.append(
                "ADDITIONAL_FEE"
            )

        # Refund not represented in ledger
        unposted_refund = round(
            refund_total - ledger_refund_total,
            2,
        )

        if abs(
            unposted_refund - variance
        ) <= 0.01:

            ambiguous_explanations.append(
                "REFUND"
            )

    # -------------------------------------------------
    # If multiple explanations fit,
    # mark as ambiguous rather than generic conflict.
    # -------------------------------------------------

    if len(ambiguous_explanations) >= 2:

        conflicts.append(
            {
                "type": "AMBIGUOUS_EXPLANATIONS",
                "variance": abs(
                    settlement_ledger_difference
                ),
                "possible_causes": (
                    ambiguous_explanations
                ),
            }
        )

    else:

        # -------------------------------------------------
        # Normal fee conflict
        # -------------------------------------------------

        if not checks[
            "fee_ledger_consistent"
        ]:

            conflicts.append(
                {
                    "type": "FEE_LEDGER_CONFLICT",
                    "fee_total": fee_total,
                    "ledger_fee_total": (
                        ledger_fee_total
                    ),
                }
            )

        # -------------------------------------------------
        # Normal refund conflict
        # -------------------------------------------------

        if not checks[
            "refund_ledger_consistent"
        ]:

            conflicts.append(
                {
                    "type": "REFUND_LEDGER_CONFLICT",
                    "refund_total": (
                        refund_total
                    ),
                    "ledger_refund_total": (
                        ledger_refund_total
                    ),
                }
            )

        # -------------------------------------------------
        # Normal settlement/ledger conflict
        # -------------------------------------------------

        if (
            settlement_ledger_difference
            is not None
            and abs(
                settlement_ledger_difference
            ) > 0.01
        ):

            conflicts.append(
                {
                    "type": (
                        "SETTLEMENT_LEDGER_CONFLICT"
                    ),
                    "settlement_amount": (
                        settlement_amount
                    ),
                    "ledger_net": ledger_net,
                }
            )

    # -------------------------------------------------
    # Final result
    # -------------------------------------------------

    is_consistent = (
        len(conflicts) == 0
    )

    return {
        "consistent": is_consistent,
        "checks": checks,
        "conflicts": conflicts,
    }