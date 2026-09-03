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
        SELECT *
        FROM recipes
        ORDER BY recipe_id
        """
    ).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


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