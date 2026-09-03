# /shared/frontend/app.py

from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
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


# -------------------------
# Customer Registration
# -------------------------

@app.route("/customer-register", methods=["POST"])
def customer_register():

    name = request.form.get("name")
    username = request.form.get("username")
    email = request.form.get("email")
    password = request.form.get("password")
    confirm_password = request.form.get("confirm_password")

    # Check whether passwords match
    if password != confirm_password:
        return redirect(
            "/shared/auth/customer_register.html?error=password"
        )

    # Convert password to hash
    password_hash = generate_password_hash(password)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO customers
            (name, username, email, password_hash)
            VALUES (?, ?, ?, ?)
            """,
            (
                name,
                username,
                email,
                password_hash
            )
        )
        conn.commit()

    except sqlite3.IntegrityError:
        conn.close()
        return redirect(
            "/shared/auth/customer_register.html?error=exists"
        )

    conn.close()

    return redirect(
        "/shared/auth/customer_login.html?registered=1"
    )

# ------------------------------
# Staff / Admin Registration
# ------------------------------

@app.route("/staff-register", methods=["POST"])
def staff_register():

    name = request.form.get("name")
    username = request.form.get("username")
    email = request.form.get("email")
    role = request.form.get("role", "staff")
    password = request.form.get("password")
    confirm_password = request.form.get("confirm_password")

    # Check whether passwords match
    if password != confirm_password:
        return redirect(
            "/shared/auth/staff_register.html?error=password"
        )

    # Hash password before saving
    password_hash = generate_password_hash(password)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO staff
            (name, username, email, password_hash, role)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                name,
                username,
                email,
                password_hash,
                role
            )
        )
        conn.commit()

    except sqlite3.IntegrityError:
        conn.close()
        return redirect(
            "/shared/auth/staff_register.html?error=exists"
        )

    conn.close()

    return redirect(
        "/shared/auth/staff_login.html?registered=1"
    )

# -------------------------
# Customer Login
# -------------------------

@app.route("/customer-login", methods=["POST"])
def customer_login():

    email = request.form.get("email")
    password = request.form.get("password")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, name, username, email, password_hash
        FROM customers
        WHERE email = ?
        """,
        (email,)
    )

    customer = cursor.fetchone()
    conn.close()

    if customer:
        stored_password_hash = customer[4]

        if check_password_hash(stored_password_hash, password):
            session["customer_id"] = customer[0]
            session["customer_name"] = customer[1]
            session["customer_email"] = customer[3]

            return redirect("/customer-dashboard")

    return redirect(
        "/shared/auth/customer_login.html?error=1"
    )


# -------------------------
# Staff / Admin Login
# -------------------------

@app.route("/staff-login", methods=["POST"])
def staff_login():

    email = request.form.get("email")
    password = request.form.get("password")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, name, username, email, password_hash, role
        FROM staff
        WHERE email = ?
        """,
        (email,)
    )

    staff = cursor.fetchone()
    conn.close()

    if staff:
        stored_password_hash = staff[4]

        if check_password_hash(stored_password_hash, password):
            session["staff_id"] = staff[0]
            session["staff_name"] = staff[1]
            session["staff_email"] = staff[3]
            session["staff_role"] = staff[5]

            return redirect("/staff-dashboard")

    return redirect(
        "/shared/auth/staff_login.html?error=1"
    )

# -------------------------
# Customer Dashboard
# -------------------------

@app.route("/customer-dashboard")
def customer_dashboard():

    if "customer_id" not in session:
        return redirect(
            "/shared/auth/customer_login.html"
        )

    return render_template(
        "customer_dashboard.html",
        customer_email=session.get("customer_email")
    )

# -------------------------
# Staff / Admin Dashboard
# -------------------------

@app.route("/staff-dashboard")
def staff_dashboard():

    if "staff_id" not in session:
        return redirect("/shared/auth/staff_login.html")

    return render_template(
        "staff_dashboard.html",
        staff_name=session.get("staff_name"),
        staff_role=session.get("staff_role")
    )

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5100,
        debug=True
    )