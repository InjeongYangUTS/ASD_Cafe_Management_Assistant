import os 

import requests 

STUDENT3_DATABASE_URL = os.getenv(
    "STUDENT3_DATABASE_URL",
    "http://localhost:7300"
).rstrip("/")

HTTP_TIMEOUT = float(os.getenv("MCP_HTTP_TIMEOUT", "10"))

class Student3AdapterError(Exception):
    """Raised when the Student 3 database service cannot fulfil a request."""
    
    def __init__(self, message, status_code = 502, detail = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code 
        self.detail = detail 

def _get(path, params = None):
    try: 
        response = requests.get(
            STUDENT3_DATABASE_URL + path,
            params = params, 
            timeout = HTTP_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise Student3AdapterError(
            "The Student 3 database service is unavailable.",
            detail = str(exc),
        ) from exc 
    
    try:
        data = response.json()
    except ValueError as exc:
        raise Student3AdapterError(
            "The Student 3 database service returned unreadable data.",
            detail = str(exc),
        ) from exc 
        
    if response.status_code >= 400:
        raise Student3AdapterError(
            data.get("error", "Student 3 database request failed."),
            status_code = response.status_code,
            detail = data,
        ) 
    
    return data 

def get_items():
    return _get(
        "/db/inventory",
        params = {
            "page": 1, 
            "per_page": 100,
        },
    )

def get_low_stock_items():
    dashboard = _get("/db/dashboard") 
    
    items = dashboard.get("low_stock_items", [])
    
    return {
        "items": items,
        "count": len(items),
    }
    
def get_item(item_id):
    return _get(f"/db/inventory/{item_id}")

def get_suppliers():
    return _get(
        "/db/suppliers",
        params = {
            "page": 1,
            "per_page": 100, 
        },
    )
    
def get_restock_orders():
    return _get(
        "/db/restock-orders",
        params = {
            "page": 1,
            "per_page": 100, 
        }, 
    )