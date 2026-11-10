"""Flask entry point for the BJT DC Bias web app.

HTTP layer only: parse form input, call dc_bias.solve(), render templates.
All engineering math lives in dc_bias.py.
"""
from flask import Flask, render_template, request

from dc_bias import solve

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", error=None, result=None)


FORM_ERROR = "กรอกข้อมูลให้ครบและเป็นตัวเลข"


@app.route("/calculate", methods=["POST"])
def calculate():
    """Parse the form (kΩ→Ω), solve, and always render HTTP 200."""
    error = None
    result = None
    try:
        vcc = float(request.form["vcc"])
        beta = float(request.form["beta"])
        vbe = float(request.form["vbe"])
        # Resistors are entered in kΩ, converted to SI ohms here.
        r1 = float(request.form["r1"]) * 1000
        r2 = float(request.form["r2"]) * 1000
        rc = float(request.form["rc"]) * 1000
        re = float(request.form["re"]) * 1000
    except (KeyError, ValueError):
        # Missing field or unparseable text.
        error = FORM_ERROR
    else:
        try:
            result = solve(vcc, r1, r2, rc, re, beta, vbe)
        except ValueError as exc:
            # Engineering validation message from dc_bias (Thai, pinned by tests).
            error = str(exc)
    return render_template("index.html", error=error, result=result)


if __name__ == "__main__":
    app.run(debug=True)
