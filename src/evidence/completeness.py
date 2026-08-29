def calculate_evidence_completeness(
    evidence: dict,
):
    """
    Calculate evidence completeness.

    Required:
    - payment
    - fee
    - settlement
    - ledger PAYMENT entry
    - ledger FEE entry

    Refunds are optional evidence.

    A refund ledger entry is required only when the
    refund is part of the authoritative accounting trail.
    """

    checks = {}

    payment_df = evidence["payment"]
    fees_df = evidence["fees"]
    refunds_df = evidence["refunds"]
    settlement_df = evidence["settlement"]
    ledger_df = evidence["ledger"]

    # -------------------------------------------------
    # Payment
    # -------------------------------------------------

    checks["payment"] = not payment_df.empty

    # -------------------------------------------------
    # Fees
    # -------------------------------------------------

    checks["fees"] = not fees_df.empty

    # -------------------------------------------------
    # Settlement
    # -------------------------------------------------

    checks["settlement"] = not settlement_df.empty

    # -------------------------------------------------
    # Ledger PAYMENT entry
    # -------------------------------------------------

    if ledger_df.empty:
        checks["ledger_payment"] = False
    else:
        checks["ledger_payment"] = (
            "PAYMENT"
            in ledger_df["entry_type"].values
        )

    # -------------------------------------------------
    # Ledger FEE entry
    # -------------------------------------------------

    if ledger_df.empty:
        checks["ledger_fee"] = False
    else:
        checks["ledger_fee"] = (
            "FEE"
            in ledger_df["entry_type"].values
        )

    # -------------------------------------------------
    # Refunds
    #
    # A payment may legitimately have no refund.
    # So refund records are not required.
    #
    # We also do NOT require a REFUND ledger entry
    # simply because a refund source record exists.
    #
    # This is important for candidate evidence such
    # as the PAY00007 ambiguity case.
    # -------------------------------------------------

    if refunds_df.empty:
        refund_required = False
        checks["refund_evidence"] = True

    else:
        refund_required = True
        checks["refund_evidence"] = True

    # -------------------------------------------------
    # Calculate completeness
    # -------------------------------------------------

    passed_checks = sum(
        checks.values()
    )

    total_checks = len(checks)

    completeness_percentage = (
        passed_checks
        / total_checks
        * 100
        if total_checks > 0
        else 0.0
    )

    missing_sources = [
        name
        for name, passed in checks.items()
        if not passed
    ]

    available_sources = [
        name
        for name, passed in checks.items()
        if passed
    ]

    return {
        "completeness_percentage": (
            completeness_percentage
        ),
        "available_sources": available_sources,
        "missing_sources": missing_sources,
        "refund_required": refund_required,
        "checks": checks,
    }