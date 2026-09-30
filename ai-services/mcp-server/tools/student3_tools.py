from adapters.student3_adapter import (
    Student3AdapterError,
    get_item as adapter_get_item,
    get_items as adapter_get_items, 
    get_low_stock_items as adapter_get_low_stock_items,
    get_restock_orders as adapter_get_restock_orders,
    get_suppliers as adapter_get_suppliers,
)

def register_student3_tools(mcp):
    
    @mcp.tool()
    def get_inventory_items() -> dict:
        """
        Return all current Student 3 items.
        
        Read-only tool.
        Does not create, update, or delete data. 
        """
        
        try: 
            data = adapter_get_items()
            
            return {
                "success": True,
                "items": data.get("items", []),
                "count": data.get(
                    "total", 
                    len(data.get("items", [])),
                )
            }
            
        except Student3AdapterError as exc:
            return {
                "success": False,
                "error": exc.message,
            }
        
    @mcp.tool()
    def get_low_stock_items() -> dict:
        """ 
        Return Student 3 items currently marked as low stock
        or out of stock.
        
        Read-only tool.
        """
        try: 
            data = adapter_get_low_stock_items()
            
            return {
                "success": True,
                "items": data["items"],
                "count": data["count"],
            }
            
        except Student3AdapterError as exc:
            return {
                "success": False,
                "error": exc.message,
            }
            
    @mcp.tool()
    def get_inventory_item(item_id: int) -> dict:
        """ 
        Return one Student 3 item by its positive integer ID.
        
        Read-only tool.
        """
        if item_id < 1:
            return {
                "success": False,
                "error": "item_id must be a positive integer.",
            }
            
        try: 
            item = adapter_get_item(item_id)
            
            return {
                "success": True,
                "item": item,
            }
            
        except Student3AdapterError as exc: 
            return {
                "success": False, 
                "error": exc.message,
            }
            
    @mcp.tool()
    def get_suppliers() -> dict:
        """ 
        Return all suppliers registered in Student 3.
        
        Read-only tool.
        """
        try:
            data = adapter_get_suppliers()
            
            return {
                "success": True,
                "suppliers": data.get("suppliers", []),
                "count": data.get(
                    "total",
                    len(data.get("suppliers", [])),
                ),
            }
        
        except Student3AdapterError as exc:
            return {
                "success": False,
                "error": exc.message,
            }
            
    @mcp.tool()
    def get_restock_orders() -> dict:
        """ 
        Return all existing Student 3 restock orders. 
        
        Read-only tool.
        """
        try: 
            data = adapter_get_restock_orders() 
            
            return {
                "success": True,
                "orders": data.get("orders", []),
                "count": data.get(
                    "total",
                    len(data.get("orders", [])),
                ),
            }
            
        except Student3AdapterError as exc:
            return {
                "success": False,
                "error": exc.message,
            }
        