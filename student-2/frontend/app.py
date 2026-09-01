from flask import Flask, render_template, redirect, session

app = Flask(__name__)

# Must match the shared authentication service
app.secret_key = "temporary-secret-key"


# -------------------------
# Main Entry
# -------------------------

@app.route("/")
def home():
    # Return to the shared homepage where the user
    # can choose Customer or Staff
    return redirect("http://localhost:5100/")


# -------------------------
# Staff - Menu Management
# -------------------------

@app.route("/staff")
def manage():
    if "staff_id" not in session:
        return redirect(
            "http://localhost:5100/shared/auth/staff_login.html"
        )

    return render_template("index.html")

@app.route("/menus")
def menus():
    if "staff_id" not in session:
        return redirect(
            "http://localhost:5100/shared/auth/staff_login.html"
        )

    return render_template("menus.html")


# -------------------------
# Staff - Recipe Management
# -------------------------

@app.route("/recipes")
def recipes():
    if "staff_id" not in session:
        return redirect(
            "http://localhost:5100/shared/auth/staff_login.html"
        )

    return render_template("recipes.html")


# -------------------------
# Staff - Ingredient Management
# -------------------------

@app.route("/ingredients")
def ingredients():
    if "staff_id" not in session:
        return redirect(
            "http://localhost:5100/shared/auth/staff_login.html"
        )

    return render_template("ingredients.html")


# -------------------------
# Customer Menu
# -------------------------

@app.route("/customer-menu")
def customer_menu():
    if "customer_id" not in session:
        return redirect(
            "http://localhost:5100/shared/auth/customer_login.html"
        )

    return render_template("customer_menu.html")


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5200,
        debug=True
    )