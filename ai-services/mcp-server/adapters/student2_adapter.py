import os

import requests


STUDENT2_BACKEND_URL = os.getenv(
    "STUDENT2_BACKEND_URL",
    "http://localhost:5201"
).rstrip("/")

HTTP_TIMEOUT = float(os.getenv("MCP_HTTP_TIMEOUT", "10"))


class Student2AdapterError(Exception):
    """Raised when the Student 2 backend service cannot fulfil a request."""

    def __init__(self, message, status_code=502, detail=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


def _get(path, params=None):
    try:
        response = requests.get(
            STUDENT2_BACKEND_URL + path,
            params=params,
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise Student2AdapterError(
            "The Student 2 backend service is unavailable.",
            detail=str(exc),
        ) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise Student2AdapterError(
            "The Student 2 backend service returned unreadable data.",
            detail=str(exc),
        ) from exc

    if response.status_code >= 400:
        raise Student2AdapterError(
            data.get("error", "Student 2 backend request failed."),
            status_code=response.status_code,
            detail=data,
        )

    return data


def get_menus():
    return _get("/api/menus")


def get_menu(menu_id):
    return _get(f"/api/menus/{menu_id}")


def get_menu_price(menu_id):
    return _get(f"/api/menu-prices/{menu_id}")


def get_ingredients():
    return _get("/api/ingredients")


def get_ingredient(ingredient_id):
    return _get(f"/api/ingredients/{ingredient_id}")


def get_recipes():
    return _get("/api/recipes")


def get_recipe(recipe_id):
    return _get(f"/api/recipes/{recipe_id}")


def get_recipe_ingredients(recipe_id):
    return _get(f"/api/recipes/{recipe_id}/ingredients")