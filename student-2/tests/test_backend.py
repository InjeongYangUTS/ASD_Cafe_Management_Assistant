import sys
from pathlib import Path

# Allow the test file to import the Student 2 backend
BACKEND_PATH = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_PATH))

from app import app


def test_get_menus():
    client = app.test_client()

    response = client.get("/api/menus")

    assert response.status_code == 200

    data = response.get_json()

    assert isinstance(data, list)
    assert len(data) >= 10


def test_get_menu_by_id():
    client = app.test_client()

    response = client.get("/api/menus/1")

    assert response.status_code == 200

    data = response.get_json()

    assert data["menu_id"] == 1
    assert "name" in data
    assert "price" in data


def test_menu_not_found():
    client = app.test_client()

    response = client.get("/api/menus/99999")

    assert response.status_code == 404


def test_negative_menu_price_rejected():
    client = app.test_client()

    response = client.post(
        "/api/menus",
        json={
            "name": "Test Coffee",
            "category": "Coffee",
            "description": "Automated test",
            "price": -5
        }
    )

    assert response.status_code == 400


def test_invalid_menu_price_rejected():
    client = app.test_client()

    response = client.post(
        "/api/menus",
        json={
            "name": "Test Coffee",
            "category": "Coffee",
            "description": "Automated test",
            "price": "hello"
        }
    )

    assert response.status_code == 400

#Ingredients

def test_get_ingredients():
    client = app.test_client()

    response = client.get("/api/ingredients")

    assert response.status_code == 200

    data = response.get_json()

    assert isinstance(data, list)
    assert len(data) >= 10


def test_get_ingredient_by_id():
    client = app.test_client()

    response = client.get("/api/ingredients/1")

    assert response.status_code == 200

    data = response.get_json()

    assert data["ingredient_id"] == 1
    assert "name" in data
    assert "unit" in data


def test_ingredient_not_found():
    client = app.test_client()

    response = client.get("/api/ingredients/99999")

    assert response.status_code == 404

#Recipes

def test_get_recipes():
    client = app.test_client()

    response = client.get("/api/recipes")

    assert response.status_code == 200

    data = response.get_json()

    assert isinstance(data, list)
    assert len(data) >= 10


def test_get_recipe_by_id():
    client = app.test_client()

    response = client.get("/api/recipes/1")

    assert response.status_code == 200

    data = response.get_json()

    assert data["recipe_id"] == 1
    assert "name" in data
    assert "instructions" in data


def test_recipe_not_found():
    client = app.test_client()

    response = client.get("/api/recipes/99999")

    assert response.status_code == 404

#Recipe ingredients

def test_get_recipe_ingredients():
    client = app.test_client()

    response = client.get("/api/recipes/1/ingredients")

    assert response.status_code == 200

    data = response.get_json()

    assert isinstance(data, list)
    assert len(data) > 0

#Menu pricing

def test_get_menu_price():
    client = app.test_client()

    response = client.get("/api/menu-prices/1")

    assert response.status_code == 200

    data = response.get_json()

    assert data["menu_id"] == 1
    assert "price" in data