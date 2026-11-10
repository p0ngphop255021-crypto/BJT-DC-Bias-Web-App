"""Flask entry point for the BJT DC Bias web app.

HTTP layer only: parse form input, call dc_bias.solve(), render templates.
All engineering math lives in dc_bias.py.
"""
from flask import Flask, render_template

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", error=None, result=None)


if __name__ == "__main__":
    app.run(debug=True)
