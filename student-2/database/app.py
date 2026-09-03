from flask import Flask, jsonify, request
import sqlite3
from pathlib import Path

app = Flask(__name__)

DB_PATH = Path(__file__).parent / "menu_recipe.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "student2-database"
    })


@app.route("/api/database/menus")
def database_menus():

    conn = get_db_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM menus
        ORDER BY menu_id
        """
    ).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in rows
    ])

@app.route("/api/database/menus/<int:menu_id>", methods=["GET"])
def database_menu(menu_id):
    conn = get_db_connection()

    menu = conn.execute(
        """
        SELECT *
        FROM menus
        WHERE menu_id = ?
        """,
        (menu_id,)
    ).fetchone()

    conn.close()

    if menu is None:
        return jsonify({"error": "Menu item not found"}), 404

    return jsonify(dict(menu))


@app.route("/api/database/menus", methods=["POST"])
def create_database_menu():
    data = request.get_json()

    conn = get_db_connection()

    cursor = conn.execute(
        """
        INSERT INTO menus (name, category, description, price)
        VALUES (?, ?, ?, ?)
        """,
        (
            data["name"],
            data["category"],
            data.get("description", ""),
            data["price"]
        )
    )

    conn.commit()

    menu_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "message": "Menu item created",
        "menu_id": menu_id
    }), 201


@app.route("/api/database/menus/<int:menu_id>", methods=["PUT"])
def update_database_menu(menu_id):
    data = request.get_json()

    conn = get_db_connection()

    cursor = conn.execute(
        """
        UPDATE menus
        SET name = ?, category = ?, description = ?, price = ?
        WHERE menu_id = ?
        """,
        (
            data["name"],
            data["category"],
            data.get("description", ""),
            data["price"],
            menu_id
        )
    )

    conn.commit()
    updated = cursor.rowcount
    conn.close()

    if updated == 0:
        return jsonify({"error": "Menu item not found"}), 404

    return jsonify({"message": "Menu item updated"})


@app.route("/api/database/menus/<int:menu_id>", methods=["DELETE"])
def delete_database_menu(menu_id):
    conn = get_db_connection()

    cursor = conn.execute(
        """
        DELETE FROM menus
        WHERE menu_id = ?
        """,
        (menu_id,)
    )

    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if deleted == 0:
        return jsonify({"error": "Menu item not found"}), 404

    return jsonify({"message": "Menu item deleted"})


@app.route("/api/database/recipes")
def database_recipes():
    conn = get_db_connection()

    rows = conn.execute(
        """
        SELECT
            r.recipe_id,
            r.menu_id,
            r.name,
            r.instructions,
            m.name AS menu_name
        FROM recipes r
        JOIN menus m
            ON r.menu_id = m.menu_id
        ORDER BY r.recipe_id
        """
    ).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


@app.route("/api/database/recipes/<int:recipe_id>", methods=["GET"])
def database_recipe(recipe_id):
    conn = get_db_connection()

    recipe = conn.execute(
        """
        SELECT
            r.recipe_id,
            r.menu_id,
            r.name,
            r.instructions,
            m.name AS menu_name
        FROM recipes r
        JOIN menus m
            ON r.menu_id = m.menu_id
        WHERE r.recipe_id = ?
        """,
        (recipe_id,)
    ).fetchone()

    conn.close()

    if recipe is None:
        return jsonify({
            "error": "Recipe not found"
        }), 404

    return jsonify(dict(recipe))


@app.route("/api/database/recipes", methods=["POST"])
def create_database_recipe():
    data = request.get_json()

    conn = get_db_connection()

    cursor = conn.execute(
        """
        INSERT INTO recipes
        (menu_id, name, instructions)
        VALUES (?, ?, ?)
        """,
        (
            data["menu_id"],
            data["name"],
            data["instructions"]
        )
    )

    recipe_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Recipe created",
        "recipe_id": recipe_id
    }), 201


@app.route("/api/database/recipes/<int:recipe_id>", methods=["PUT"])
def update_database_recipe(recipe_id):
    data = request.get_json()

    conn = get_db_connection()

    recipe = conn.execute(
        """
        SELECT recipe_id
        FROM recipes
        WHERE recipe_id = ?
        """,
        (recipe_id,)
    ).fetchone()

    if recipe is None:
        conn.close()

        return jsonify({
            "error": "Recipe not found"
        }), 404

    conn.execute(
        """
        UPDATE recipes
        SET
            menu_id = ?,
            name = ?,
            instructions = ?
        WHERE recipe_id = ?
        """,
        (
            data["menu_id"],
            data["name"],
            data["instructions"],
            recipe_id
        )
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Recipe updated"
    })


@app.route("/api/database/recipes/<int:recipe_id>", methods=["DELETE"])
def delete_database_recipe(recipe_id):
    conn = get_db_connection()

    recipe = conn.execute(
        """
        SELECT recipe_id
        FROM recipes
        WHERE recipe_id = ?
        """,
        (recipe_id,)
    ).fetchone()

    if recipe is None:
        conn.close()

        return jsonify({
            "error": "Recipe not found"
        }), 404

    conn.execute(
        """
        DELETE FROM recipes
        WHERE recipe_id = ?
        """,
        (recipe_id,)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Recipe deleted"
    })


@app.route(
    "/api/database/recipes/<int:recipe_id>/ingredients",
    methods=["GET"]
)
def database_recipe_ingredients(recipe_id):
    conn = get_db_connection()

    recipe = conn.execute(
        """
        SELECT recipe_id
        FROM recipes
        WHERE recipe_id = ?
        """,
        (recipe_id,)
    ).fetchone()

    if recipe is None:
        conn.close()

        return jsonify({
            "error": "Recipe not found"
        }), 404

    rows = conn.execute(
        """
        SELECT
            ri.id,
            ri.recipe_id,
            ri.ingredient_id,
            i.name AS ingredient_name,
            ri.quantity,
            ri.unit
        FROM recipe_ingredients ri
        JOIN ingredients i
            ON ri.ingredient_id = i.ingredient_id
        WHERE ri.recipe_id = ?
        ORDER BY ri.id
        """,
        (recipe_id,)
    ).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


@app.route(
    "/api/database/recipes/<int:recipe_id>/ingredients",
    methods=["POST"]
)
def create_database_recipe_ingredient(recipe_id):
    data = request.get_json()

    conn = get_db_connection()

    cursor = conn.execute(
        """
        INSERT INTO recipe_ingredients
        (recipe_id, ingredient_id, quantity, unit)
        VALUES (?, ?, ?, ?)
        """,
        (
            recipe_id,
            data["ingredient_id"],
            data["quantity"],
            data["unit"]
        )
    )

    recipe_ingredient_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Ingredient added to recipe",
        "recipe_ingredient_id": recipe_ingredient_id
    }), 201


@app.route(
    "/api/database/recipe-ingredients/<int:recipe_ingredient_id>",
    methods=["GET"]
)
def database_recipe_ingredient(recipe_ingredient_id):
    conn = get_db_connection()

    row = conn.execute(
        """
        SELECT
            ri.id,
            ri.recipe_id,
            ri.ingredient_id,
            i.name AS ingredient_name,
            ri.quantity,
            ri.unit
        FROM recipe_ingredients ri
        JOIN ingredients i
            ON ri.ingredient_id = i.ingredient_id
        WHERE ri.id = ?
        """,
        (recipe_ingredient_id,)
    ).fetchone()

    conn.close()

    if row is None:
        return jsonify({
            "error": "Recipe ingredient not found"
        }), 404

    return jsonify(dict(row))


@app.route(
    "/api/database/recipe-ingredients/<int:recipe_ingredient_id>",
    methods=["PUT"]
)
def update_database_recipe_ingredient(recipe_ingredient_id):
    data = request.get_json()

    conn = get_db_connection()

    existing = conn.execute(
        """
        SELECT id
        FROM recipe_ingredients
        WHERE id = ?
        """,
        (recipe_ingredient_id,)
    ).fetchone()

    if existing is None:
        conn.close()

        return jsonify({
            "error": "Recipe ingredient not found"
        }), 404

    conn.execute(
        """
        UPDATE recipe_ingredients
        SET
            ingredient_id = ?,
            quantity = ?,
            unit = ?
        WHERE id = ?
        """,
        (
            data["ingredient_id"],
            data["quantity"],
            data["unit"],
            recipe_ingredient_id
        )
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Recipe ingredient updated"
    })


@app.route(
    "/api/database/recipe-ingredients/<int:recipe_ingredient_id>",
    methods=["DELETE"]
)
def delete_database_recipe_ingredient(recipe_ingredient_id):
    conn = get_db_connection()

    existing = conn.execute(
        """
        SELECT id
        FROM recipe_ingredients
        WHERE id = ?
        """,
        (recipe_ingredient_id,)
    ).fetchone()

    if existing is None:
        conn.close()

        return jsonify({
            "error": "Recipe ingredient not found"
        }), 404

    conn.execute(
        """
        DELETE FROM recipe_ingredients
        WHERE id = ?
        """,
        (recipe_ingredient_id,)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Recipe ingredient deleted"
    })


@app.route("/api/database/ingredients")
def database_ingredients():
    conn = get_db_connection()

    rows = conn.execute(
        """
        SELECT
            i.ingredient_id,
            i.name,
            i.unit,
            ic.unit_cost
        FROM ingredients i
        LEFT JOIN ingredient_costs ic
            ON i.ingredient_id = ic.ingredient_id
        ORDER BY i.ingredient_id
        """
    ).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


@app.route("/api/database/ingredients/<int:ingredient_id>", methods=["GET"])
def database_ingredient(ingredient_id):
    conn = get_db_connection()

    ingredient = conn.execute(
        """
        SELECT
            i.ingredient_id,
            i.name,
            i.unit,
            ic.unit_cost
        FROM ingredients i
        LEFT JOIN ingredient_costs ic
            ON i.ingredient_id = ic.ingredient_id
        WHERE i.ingredient_id = ?
        """,
        (ingredient_id,)
    ).fetchone()

    conn.close()

    if ingredient is None:
        return jsonify({
            "error": "Ingredient not found"
        }), 404

    return jsonify(dict(ingredient))


@app.route("/api/database/ingredients", methods=["POST"])
def create_database_ingredient():
    data = request.get_json()

    conn = get_db_connection()

    cursor = conn.execute(
        """
        INSERT INTO ingredients (name, unit)
        VALUES (?, ?)
        """,
        (
            data["name"],
            data["unit"]
        )
    )

    ingredient_id = cursor.lastrowid

    conn.execute(
        """
        INSERT INTO ingredient_costs
        (ingredient_id, unit_cost)
        VALUES (?, ?)
        """,
        (
            ingredient_id,
            data["unit_cost"]
        )
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Ingredient created",
        "ingredient_id": ingredient_id
    }), 201


@app.route("/api/database/ingredients/<int:ingredient_id>", methods=["PUT"])
def update_database_ingredient(ingredient_id):
    data = request.get_json()

    conn = get_db_connection()

    ingredient = conn.execute(
        """
        SELECT ingredient_id
        FROM ingredients
        WHERE ingredient_id = ?
        """,
        (ingredient_id,)
    ).fetchone()

    if ingredient is None:
        conn.close()

        return jsonify({
            "error": "Ingredient not found"
        }), 404

    conn.execute(
        """
        UPDATE ingredients
        SET
            name = ?,
            unit = ?
        WHERE ingredient_id = ?
        """,
        (
            data["name"],
            data["unit"],
            ingredient_id
        )
    )

    conn.execute(
        """
        UPDATE ingredient_costs
        SET unit_cost = ?
        WHERE ingredient_id = ?
        """,
        (
            data["unit_cost"],
            ingredient_id
        )
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Ingredient updated"
    })


@app.route("/api/database/ingredients/<int:ingredient_id>", methods=["DELETE"])
def delete_database_ingredient(ingredient_id):
    conn = get_db_connection()

    ingredient = conn.execute(
        """
        SELECT ingredient_id
        FROM ingredients
        WHERE ingredient_id = ?
        """,
        (ingredient_id,)
    ).fetchone()

    if ingredient is None:
        conn.close()

        return jsonify({
            "error": "Ingredient not found"
        }), 404

    conn.execute(
        """
        DELETE FROM ingredient_costs
        WHERE ingredient_id = ?
        """,
        (ingredient_id,)
    )

    conn.execute(
        """
        DELETE FROM ingredients
        WHERE ingredient_id = ?
        """,
        (ingredient_id,)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Ingredient deleted"
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5202,
        debug=True
    )