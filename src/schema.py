CUSTOMER_COLUMNS = [
    "customer_id",
    "name",
    "email",
]

ORDER_COLUMNS = [
    "order_id",
    "customer_id",
    "order_amount",
    "created_at",
]

PAYMENT_COLUMNS = [
    "payment_id",
    "order_id",
    "customer_id",
    "amount",
    "payment_method",
    "status",
    "created_at",
]

SETTLEMENT_COLUMNS = [
    "settlement_id",
    "payment_id",
    "settlement_amount",
    "settlement_date",
    "status",
]

REFUND_COLUMNS = [
    "refund_id",
    "payment_id",
    "refund_amount",
    "refund_date",
    "status",
]

FEE_COLUMNS = [
    "fee_id",
    "payment_id",
    "fee_amount",
    "fee_type",
    "created_at",
]

LEDGER_COLUMNS = [
    "ledger_id",
    "payment_id",
    "entry_type",
    "amount",
    "created_at",
]