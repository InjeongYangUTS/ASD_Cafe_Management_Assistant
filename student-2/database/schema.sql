PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS recipe_ingredients;
DROP TABLE IF EXISTS ingredient_costs;
DROP TABLE IF EXISTS recipes;
DROP TABLE IF EXISTS ingredients;
DROP TABLE IF EXISTS menus;


CREATE TABLE menus (
    menu_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    price REAL NOT NULL CHECK (price >= 0)
);


CREATE TABLE recipes (
    recipe_id INTEGER PRIMARY KEY,
    menu_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    instructions TEXT NOT NULL,

    FOREIGN KEY (menu_id)
        REFERENCES menus(menu_id)
        ON DELETE CASCADE
);


CREATE TABLE ingredients (
    ingredient_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    unit TEXT NOT NULL
);


CREATE TABLE ingredient_costs (
    id INTEGER PRIMARY KEY,
    ingredient_id INTEGER NOT NULL,
    unit_cost REAL NOT NULL CHECK (unit_cost >= 0),

    FOREIGN KEY (ingredient_id)
        REFERENCES ingredients(ingredient_id)
        ON DELETE CASCADE
);


CREATE TABLE recipe_ingredients (
    id INTEGER PRIMARY KEY,
    recipe_id INTEGER NOT NULL,
    ingredient_id INTEGER NOT NULL,
    quantity REAL NOT NULL CHECK (quantity > 0),
    unit TEXT NOT NULL,

    FOREIGN KEY (recipe_id)
        REFERENCES recipes(recipe_id)
        ON DELETE CASCADE,

    FOREIGN KEY (ingredient_id)
        REFERENCES ingredients(ingredient_id)
        ON DELETE CASCADE
);