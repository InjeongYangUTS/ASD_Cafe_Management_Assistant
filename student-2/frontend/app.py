from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/menus")
def menus():
    return render_template("menus.html")

@app.route("/recipes")
def recipes():
    return render_template("recipes.html")

@app.route("/ingredients")
def ingredients():
    return render_template("ingredients.html")

@app.route("/customer-menu")
def customer_menu():
    return render_template("customer_menu.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5200, debug=True)