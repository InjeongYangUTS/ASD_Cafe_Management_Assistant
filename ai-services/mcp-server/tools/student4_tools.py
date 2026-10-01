from adapters.student4_adapter import (
    Student4AdapterError,
    get_kitchen_queue as adapter_get_kitchen_queue,
    get_order as adapter_get_order,
    get_order_status as adapter_get_order_status,
    get_orders as adapter_get_orders,
)


def register_student4_tools(mcp):

    @mcp.tool()
    def get_orders(status: str = "", limit: int = 100) -> dict:
        """
        Return Student 4 orders, newest first.

        Pass status to filter to one lifecycle state - PENDING, CONFIRMED,
        PREPARING, READY, COMPLETED or CANCELLED. Leave it empty for all.

        Read-only tool.
        Does not create, update, or delete data.
        """
        if limit < 1:
            return {
                "success": False,
                "error": "limit must be a positive integer.",
            }

        try:
            data = adapter_get_orders(status or None, limit)

            orders = data.get("orders", [])

            return {
                "success": True,
                "orders": orders,
                "count": data.get("count", len(orders)),
            }

        except Student4AdapterError as exc:
            return {
                "success": False,
                "error": exc.message,
            }

    @mcp.tool()
    def get_order(order_id: int) -> dict:
        """
        Return one Student 4 order by its positive integer ID, with its
        line items and the prices captured when the order was placed.

        Read-only tool.
        """
        if order_id < 1:
            return {
                "success": False,
                "error": "order_id must be a positive integer.",
            }

        try:
            return {
                "success": True,
                "order": adapter_get_order(order_id),
            }

        except Student4AdapterError as exc:
            return {
                "success": False,
                "error": exc.message,
            }

    @mcp.tool()
    def get_kitchen_queue() -> dict:
        """
        Return the live kitchen queue with its measured metrics - how many
        orders are open, the total workload in minutes, the longest wait
        and the busiest station.

        These numbers are computed by the Order service, not estimated
        here, so they can be quoted directly.

        Read-only tool.
        """
        try:
            return {
                "success": True,
                "queue": adapter_get_kitchen_queue(),
            }

        except Student4AdapterError as exc:
            return {
                "success": False,
                "error": exc.message,
            }

    @mcp.tool()
    def get_order_status(order_id: int) -> dict:
        """
        Return the current status of one Student 4 order and the timeline
        of every status it has passed through.

        Read-only tool.
        """
        if order_id < 1:
            return {
                "success": False,
                "error": "order_id must be a positive integer.",
            }

        try:
            return {
                "success": True,
                "status": adapter_get_order_status(order_id),
            }

        except Student4AdapterError as exc:
            return {
                "success": False,
                "error": exc.message,
            }
