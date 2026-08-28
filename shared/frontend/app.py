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

    customer_id = request.form.get("customer_id")
    password = request.form.get("password")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM customers
        WHERE customer_id = ? AND password = ?
        """,
        (customer_id, password)
    )

    customer = cursor.fetchone()

    conn.close()

    if customer:
        session["customer_id"] = customer_id
        return redirect("/customer-dashboard")

    return redirect("/shared/auth/customer_login.html?error=1")


@app.route("/customer-dashboard")
def customer_dashboard():

    if "customer_id" not in session:
        return redirect("/shared/auth/customer_login.html")

    return render_template(
        "customer_dashboard.html",
        customer_id=session["customer_id"]
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5100,
        debug=True
    )