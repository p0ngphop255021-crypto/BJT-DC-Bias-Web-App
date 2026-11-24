"""ngspice adapter for the CE voltage-divider amplifier.

Pure engineering module: no Flask, no request/response, no HTML.
Inputs are SI floats; outputs are plain dicts and strings.
"""

import math
import os
import shutil
import subprocess
import tempfile

NGSPICE_BIN_ENV = "NGSPICE_BIN"
KNOWN_WINDOWS_BINARY = r"C:\Tools\ngspice\Spice64\bin\ngspice_con.exe"

BJT_MODEL_NAME = "2N3904"
# Source: ON Semiconductor datasheet 2N3904/D, "Spice Model" line.
BJT_MODEL_CARD = (
    ".model 2N3904 NPN(Is=6.734f Xti=3 Eg=1.11 Vaf=74.03 Bf=416.4 Ne=1.259 "
    "Ise=6.734f Ikf=66.78m Xtb=1.5 Br=.7371 Nc=2 Isc=0 Ikr=0 Rc=1 "
    "Cjc=3.638p Mjc=.3085 Vjc=.75 Fc=.5 Cje=4.493p Mje=.2593 Vje=.75 "
    "Tr=239.5n Tf=301.2p Itf=.4 Vtf=4 Xtf=2 Rb=10)"
)

FINITE_ERROR = "ค่าทุกช่องต้องเป็นจำนวนจริงที่จำกัด (finite)"
PARAM_KEYS = ("vcc", "r1", "r2", "rc", "re", "rl", "cin", "cout", "amp", "freq")


class SpiceError(Exception):
    """An error whose message is safe to show in the UI."""


def _spice_num(value):
    """Compact SPICE-compatible number: 1e-05, 1e+07, 2200, 0.01."""
    return f"{float(value):.6g}"


def validate_params(params):
    """Validate SI circuit parameters, raising ValueError with Thai text."""
    for key in PARAM_KEYS:
        if key not in params:
            raise ValueError("กรอกข้อมูลให้ครบ")
        value = params[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(FINITE_ERROR)
        if not math.isfinite(float(value)):
            raise ValueError(FINITE_ERROR)

    if params["vcc"] <= 0:
        raise ValueError("VCC ต้องมากกว่า 0")
    if any(params[k] <= 0 for k in ("r1", "r2", "rc", "re", "rl")):
        raise ValueError("R1, R2, RC, RE, RL ต้องมากกว่า 0")
    if params["cin"] <= 0 or params["cout"] <= 0:
        raise ValueError("CIN, COUT ต้องมากกว่า 0")
    if params["amp"] < 0:
        raise ValueError("amplitude ต้องไม่ติดลบ")
    if params["amp"] > 1:
        raise ValueError("amplitude ต้องไม่เกิน 1 V")
    if params["freq"] <= 0:
        raise ValueError("freq ต้องมากกว่า 0")
    if params["freq"] > 1e6:
        raise ValueError("freq ต้องไม่เกิน 1 MHz")


def tran_stop(freq):
    """Return (step, stop) in seconds for a 200-point/period transient."""
    period = 1.0 / freq
    step = period / 200.0
    stop = min(max(5.0 * period, 5e-3), 50e-3)
    return step, stop


PLOT_KEYS = {
    "Operating Point": "op",
    "AC Analysis": "ac",
    "Transient Analysis": "tran",
}


def _parse_number(token, complex_plot):
    try:
        if "," in token:
            real, imag = token.split(",", 1)
            return complex(float(real), float(imag))
        value = float(token)
        return complex(value, 0.0) if complex_plot else value
    except ValueError as exc:
        raise SpiceError(f"อ่านผลจาก ngspice ไม่ได้: {token}") from exc


def parse_raw_ascii(text):
    """Parse an ngspice ASCII rawfile into {plot_key: {variables, points}}."""
    if not text or not text.strip():
        raise SpiceError("อ่านผลจาก ngspice ไม่ได้: rawfile ว่าง")

    blocks = []
    current = None
    for line in text.splitlines():
        if line.startswith("Plotname:"):
            current = {"name": line.split(":", 1)[1].strip(), "lines": []}
            blocks.append(current)
        elif current is not None:
            current["lines"].append(line)
    if not blocks:
        raise SpiceError("อ่านผลจาก ngspice ไม่ได้: ไม่พบ Plotname")

    plots = {}
    for block in blocks:
        key = PLOT_KEYS.get(block["name"])
        if key is None:
            continue
        lines = block["lines"]
        flags = ""
        n_variables = n_points = None
        variables = {}
        values_at = None
        for index, line in enumerate(lines):
            if line.startswith("Flags:"):
                flags = line.split(":", 1)[1].strip()
            elif line.startswith("No. Variables:"):
                n_variables = int(line.split(":", 1)[1].strip())
            elif line.startswith("No. Points:"):
                n_points = int(line.split(":", 1)[1].strip())
            elif line.startswith("Variables:"):
                for var_line in lines[index + 1:]:
                    if not var_line.strip():
                        break
                    fields = var_line.split()
                    if len(fields) < 2 or not fields[0].isdigit():
                        break
                    variables[fields[1]] = int(fields[0])
            elif line.startswith("Values:"):
                values_at = index + 1
                break

        if None in (n_variables, n_points) or not variables or values_at is None:
            raise SpiceError(f"อ่านผลจาก ngspice ไม่ได้: {key} ไม่สมบูรณ์")
        if n_points <= 0 or n_variables <= 0:
            raise SpiceError(f"อ่านผลจาก ngspice ไม่ได้: {key} ไม่มีข้อมูล")

        value_lines = lines[values_at:]
        expected_lines = n_variables * n_points
        if len(value_lines) < expected_lines:
            raise SpiceError(f"อ่านผลจาก ngspice ไม่ได้: {key} ถูกตัด")
        complex_plot = "complex" in flags
        points = []
        for point_index in range(n_points):
            chunk = value_lines[point_index * n_variables:(point_index + 1) * n_variables]
            row = []
            for line in chunk:
                fields = line.strip().split()
                if not fields:
                    raise SpiceError(f"อ่านผลจาก ngspice ไม่ได้: {key} ขาดค่า")
                row.append(_parse_number(fields[-1], complex_plot))
            points.append(row)
        plots[key] = {"variables": variables, "points": points}

    if not plots:
        raise SpiceError("อ่านผลจาก ngspice ไม่ได้: ไม่พบ plot ที่รู้จัก")
    return plots


def raw_value(plot, name, point=0):
    """Return a named variable from one point of a parsed plot."""
    index = plot["variables"].get(name)
    if index is None:
        raise SpiceError(f"อ่านผลจาก ngspice ไม่ได้: ไม่มี {name}")
    try:
        return plot["points"][point][index]
    except IndexError as exc:
        raise SpiceError(f"อ่านผลจาก ngspice ไม่ได้: ไม่มีจุดที่ {point}") from exc


def build_netlist(params, analysis):
    """Build a complete ASCII-raw ngspice deck for the chosen analysis."""
    validate_params(params)
    if analysis == "dc":
        directive = ".op"
    elif analysis == "ac":
        directive = ".ac dec 20 10 1e+07"
    elif analysis == "tran":
        step, stop = tran_stop(params["freq"])
        directive = f".tran {_spice_num(step)} {_spice_num(stop)}"
    else:
        raise ValueError("analysis ต้องเป็น dc, ac หรือ tran")

    lines = [
        "* CE voltage-divider amplifier - generated by spice_engine.py",
        BJT_MODEL_CARD,
        f"VCC vcc 0 DC {_spice_num(params['vcc'])}",
        "VIN in 0 DC 0 AC 1 "
        f"SIN(0 {_spice_num(params['amp'])} {_spice_num(params['freq'])})",
        f"R1 vcc b {_spice_num(params['r1'])}",
        f"R2 b 0 {_spice_num(params['r2'])}",
        f"RC vcc c {_spice_num(params['rc'])}",
        f"RE e 0 {_spice_num(params['re'])}",
        f"Q1 c b e {BJT_MODEL_NAME}",
        f"CIN in b {_spice_num(params['cin'])}",
        f"COUT c out {_spice_num(params['cout'])}",
        f"RL out 0 {_spice_num(params['rl'])}",
        ".save all @q1[ic] @q1[ib]",
        ".option filetype=ascii",
        directive,
        ".end",
    ]
    return "\n".join(lines) + "\n"
