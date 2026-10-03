from adapters.student5_adapter import (
    Student5AdapterError,
    get_payment as adapter_get_payment,
    get_payments as adapter_get_payments,
    get_refunds as adapter_get_refunds,
)


def register_student5_tools(mcp):
    """Register read-only Payment & Billing tools on the shared MCP server."""

    @mcp.tool()
    def get_payment_records(status: str = "", limit: int = 20) -> list[dict]:
        """Return recent Student 5 payment records, optionally filtered by status."""
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        try:
            payments = adapter_get_payments()
        except Student5AdapterError as exc:
            raise RuntimeError(str(exc)) from exc

        if status:
            payments = [
                payment for payment in payments
                if payment.get("payment_status") == status
            ]

        return payments[-limit:]

    @mcp.tool()
    def get_payment_record(payment_id: int) -> dict:
        """Return one Student 5 payment by its positive integer ID."""
        if payment_id < 1:
            raise ValueError("payment_id must be a positive integer")

        try:
            return adapter_get_payment(payment_id)
        except Student5AdapterError as exc:
            raise RuntimeError(str(exc)) from exc

    @mcp.tool()
    def get_refund_records(limit: int = 20) -> list[dict]:
        """Return recent Student 5 refund records without modifying any payment."""
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        try:
            refunds = adapter_get_refunds()
        except Student5AdapterError as exc:
            raise RuntimeError(str(exc)) from exc

        return refunds[-limit:]
