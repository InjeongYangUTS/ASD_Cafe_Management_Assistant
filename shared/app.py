from flask import Flask, render_template, send_from_directory

app = Flask(
    __name__,
    template_folder="../templates"
)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/css/<path:filename>")
def css(filename):
    return send_from_directory("css", filename)


@app.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory("assets", filename)


@app.route("/auth/<path:filename>")
def auth(filename):
    return send_from_directory("auth", filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5100, debug=True)