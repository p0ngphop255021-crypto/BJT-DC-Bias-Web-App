"""Flask entry point for the BJT DC Bias web app.

HTTP layer only: parse form input, call the matching solver in dc_bias,
render templates. All engineering math lives in dc_bias.py.
"""
from flask import Flask, render_template, request

import spice_engine
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

SIM_ANALYSES = ("dc", "ac", "tran")
SIM_FIELD_DEFAULTS = {
    "vcc": "12", "r1": "100", "r2": "22", "rc": "2.2", "re": "1",
    "rl": "10", "cin": "10", "cout": "10", "amp": "10", "freq": "1000",
    "beta": "100", "vbe": "0.7",
}
SIM_INPUT_FIELDS = tuple(SIM_FIELD_DEFAULTS)


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


def _parse_sim_form(form) -> tuple:
    """Parse the amplifier form (kΩ→Ω, µF→F, mV→V) and validate the analysis."""
    analysis = form.get("analysis", "dc")
    if analysis not in SIM_ANALYSES:
        raise ValueError("analysis ต้องเป็น dc, ac หรือ tran")
    if any(key not in form for key in SIM_INPUT_FIELDS):
        raise ValueError(FORM_ERROR)
    try:
        values = {key: float(form[key]) for key in SIM_INPUT_FIELDS}
    except ValueError:
        raise ValueError(FORM_ERROR) from None
    params = {
        "vcc": values["vcc"],
        "r1": values["r1"] * 1000,
        "r2": values["r2"] * 1000,
        "rc": values["rc"] * 1000,
        "re": values["re"] * 1000,
        "rl": values["rl"] * 1000,
        "cin": values["cin"] / 1e6,
        "cout": values["cout"] / 1e6,
        "amp": values["amp"] / 1000,
        "freq": values["freq"],
        "beta": values["beta"],
        "vbe": values["vbe"],
    }
    return analysis, params


def _echo_sim_form(form) -> dict:
    """Raw submitted values so the amplifier form keeps what the user typed."""
    echoed = {key: form.get(key, default) for key, default in SIM_FIELD_DEFAULTS.items()}
    echoed["analysis"] = form.get("analysis", "dc")
    return echoed


def _simulation_context(**overrides) -> dict:
    defaults = {
        "simulation": None,
        "sim_error": None,
        "sim_form": dict(SIM_FIELD_DEFAULTS, analysis="dc"),
        "analytical": None,
    }
    defaults.update(overrides)
    return defaults


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
        **_simulation_context(),
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
        **_simulation_context(),
    )


@app.route("/simulate", methods=["POST"])
def simulate():
    """Run ngspice for the CE amplifier and always render HTTP 200."""
    analysis = request.form.get("analysis", "dc")
    sim_error = None
    simulation = None
    analytical = None
    try:
        analysis, params = _parse_sim_form(request.form)
        simulation = spice_engine.simulate(params, analysis)
    except (KeyError, ValueError, spice_engine.SpiceError) as exc:
        sim_error = str(exc)

    if simulation is not None and analysis == "dc":
        analytical = solve(
            params["vcc"], params["r1"], params["r2"], params["rc"],
            params["re"], params["beta"], params["vbe"],
        )

    return render_template(
        "index.html",
        error=None,
        result=None,
        mode=DEFAULT_MODE,
        mode_label=MODES[DEFAULT_MODE],
        mode_known=True,
        modes=MODES,
        form=dict(FIELD_DEFAULTS[DEFAULT_MODE]),
        **_simulation_context(
            simulation=simulation,
            sim_error=sim_error,
            sim_form=_echo_sim_form(request.form),
            analytical=analytical,
        ),
    )


if __name__ == "__main__":
    app.run(debug=True)
