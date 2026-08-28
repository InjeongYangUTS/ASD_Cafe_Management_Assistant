from flask import Flask, render_template, request, redirect, session
import sqlite3
import os


app = Flask(
    __name__,
    static_folder="../",
    static_url_path="/shared"
)

app.secret_key = "temporary-secret-key"


DB_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "database",
    "users.db"
)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/customer-login", methods=["POST"])
def customer_login():

    login_value = request.form.get("login")
    password = request.form.get("password")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM customers
        WHERE (username = ? OR email = ?)
        AND password = ?
        """,
        (login_value, login_value, password)
    )

    customer = cursor.fetchone()

    conn.close()

    if customer:
        session["customer_username"] = customer[1]
        session["customer_name"] = customer[4]

        return redirect("/customer-dashboard")

    return redirect("/shared/auth/customer_login.html?error=1")

@app.route("/staff-login", methods=["POST"])
def staff_login():

    login_value = request.form.get("login")
    password = request.form.get("password")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM staff
        WHERE (username = ? OR email = ?)
        AND password = ?
        """,
        (login_value, login_value, password)
    )

    staff = cursor.fetchone()

    conn.close()

    if staff:
        session["staff_username"] = staff[1]
        session["staff_name"] = staff[4]
        session["staff_role"] = staff[5]

        return redirect("/staff-dashboard")

    return redirect("/shared/auth/staff_login.html?error=1")

@app.route("/customer-dashboard")
def customer_dashboard():

    if "customer_username" not in session:
        return redirect("/shared/auth/customer_login.html")

    return render_template(
        "customer_dashboard.html",
        customer_name=session["customer_name"]
    )

@app.route("/staff-dashboard")
def staff_dashboard():

    if "staff_username" not in session:
        return redirect("/shared/auth/staff_login.html")

    return render_template(
        "staff_dashboard.html",
        staff_name=session["staff_name"],
        staff_role=session["staff_role"]
    )

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5100,
        debug=True
    )