"""Flask entry point for the BJT DC Bias web app.

HTTP layer only: parse form input, call the matching solver in dc_bias,
render templates. All engineering math lives in dc_bias.py.
"""
from flask import Flask, render_template, request

from dc_bias import solve, solve_emitter, solve_fixed

app = Flask(__name__)

MODES = {
    "divider": "Voltage Divider Bias",
    "fixed": "Fixed Bias",
    "emitter": "Emitter Bias",
}
DEFAULT_MODE = "divider"

# Resistor fields each mode needs (form values are kΩ).
MODE_RESISTOR_FIELDS = {
    "divider": ("r1", "r2", "rc", "re"),
    "fixed": ("rb", "rc"),
    "emitter": ("rb", "rc", "re"),
}

FIELD_DEFAULTS = {
    "divider": {
        "vcc": "12", "r1": "100", "r2": "22", "rc": "2.2",
        "re": "1", "beta": "100", "vbe": "0.7",
    },
    "fixed": {
        "vcc": "12", "rb": "1000", "rc": "2.2", "beta": "100", "vbe": "0.7",
    },
    "emitter": {
        "vcc": "12", "rb": "1000", "rc": "2.2", "re": "1",
        "beta": "100", "vbe": "0.7",
    },
}

FORM_ERROR = "กรอกข้อมูลให้ครบและเป็นตัวเลข"
UNKNOWN_MODE_ERROR = (
    "โหมดวงจรไม่ถูกต้อง: ต้องเลือกจาก Voltage Divider Bias, Fixed Bias "
    "หรือ Emitter Bias"
)


def _parse_form(mode: str, form) -> tuple:
    """Parse common fields plus the resistors this mode needs (kΩ→Ω)."""
    vcc = float(form["vcc"])
    beta = float(form["beta"])
    vbe = float(form["vbe"])
    resistors = {key: float(form[key]) * 1000 for key in MODE_RESISTOR_FIELDS[mode]}
    return vcc, beta, vbe, resistors


def _solve_for_mode(mode: str, vcc: float, beta: float, vbe: float, res: dict) -> dict:
    if mode == "divider":
        return solve(vcc, res["r1"], res["r2"], res["rc"], res["re"], beta, vbe)
    if mode == "fixed":
        return solve_fixed(vcc, res["rb"], res["rc"], beta, vbe)
    return solve_emitter(vcc, res["rb"], res["rc"], res["re"], beta, vbe)


def _echo_form(mode: str, form) -> dict:
    """Raw submitted values so the form keeps what the user typed."""
    return {
        key: form.get(key, default)
        for key, default in FIELD_DEFAULTS[mode].items()
    }


@app.route("/", methods=["GET"])
def index():
    mode = request.args.get("mode", DEFAULT_MODE)
    error = None
    mode_known = mode in MODES
    if not mode_known:
        error = UNKNOWN_MODE_ERROR
        mode = DEFAULT_MODE
    return render_template(
        "index.html",
        error=error,
        result=None,
        mode=mode,
        mode_label=MODES[mode],
        mode_known=mode_known,
        modes=MODES,
        form=dict(FIELD_DEFAULTS[mode]),
    )


@app.route("/calculate", methods=["POST"])
def calculate():
    """Parse the form (kΩ→Ω), solve, and always render HTTP 200."""
    mode = request.form.get("mode", DEFAULT_MODE)
    error = None
    result = None
    mode_known = mode in MODES

    if not mode_known:
        error = UNKNOWN_MODE_ERROR
        mode = DEFAULT_MODE
    else:
        try:
            vcc, beta, vbe, resistors = _parse_form(mode, request.form)
        except (KeyError, ValueError):
            # Missing field or unparseable text.
            error = FORM_ERROR
        else:
            try:
                result = _solve_for_mode(mode, vcc, beta, vbe, resistors)
            except ValueError as exc:
                # Engineering validation message from dc_bias (Thai, pinned by tests).
                error = str(exc)

    return render_template(
        "index.html",
        error=error,
        result=result,
        mode=mode,
        mode_label=MODES[mode],
        mode_known=mode_known,
        modes=MODES,
        form=_echo_form(mode, request.form),
    )


if __name__ == "__main__":
    app.run(debug=True)
