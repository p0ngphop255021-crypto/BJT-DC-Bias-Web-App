"""ngspice adapter for the CE voltage-divider amplifier.

Pure engineering module: no Flask, no request/response, no HTML.
Inputs are SI floats; outputs are plain dicts and strings.
"""

import functools
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


def find_ngspice(env=None):
    """Locate a batch-capable ngspice binary, preferring ngspice_con."""
    env = os.environ if env is None else env
    configured = env.get(NGSPICE_BIN_ENV)
    if configured and os.path.isfile(configured):
        return configured
    console = shutil.which("ngspice_con")
    if console:
        return console
    plain = shutil.which("ngspice")
    if plain:
        # On Windows ngspice.exe is the GUI and detaches immediately in batch.
        sibling = os.path.join(os.path.dirname(plain), "ngspice_con.exe")
        if os.path.isfile(sibling):
            return sibling
        return plain
    if os.path.isfile(KNOWN_WINDOWS_BINARY):
        return KNOWN_WINDOWS_BINARY
    raise SpiceError("ไม่พบ ngspice: กรุณาติดตั้ง ngspice หรือตั้งค่า NGSPICE_BIN")


@functools.lru_cache(maxsize=None)
def ngspice_version(binary):
    """Return e.g. 'ngspice-47'; never fail the whole run over a version."""
    try:
        completed = subprocess.run(
            [binary, "-v"], capture_output=True, text=True, timeout=5
        )
        for line in (completed.stdout + completed.stderr).splitlines():
            if line.startswith("** ngspice-"):
                return line.split(":", 1)[0].lstrip("*").strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def run_netlist(netlist, binary, timeout=20.0):
    """Run one netlist in an isolated temp dir; return (log_text, raw_text)."""
    workdir = tempfile.mkdtemp(prefix="ngspice-lab04-")
    try:
        netlist_path = os.path.join(workdir, "ce.cir")
        log_path = os.path.join(workdir, "run.log")
        raw_path = os.path.join(workdir, "run.raw")
        with open(netlist_path, "w", encoding="utf-8") as handle:
            handle.write(netlist)
        try:
            completed = subprocess.run(
                [binary, "-b", "-o", log_path, "-r", raw_path, netlist_path],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise SpiceError("ngspice ใช้เวลาเกินกำหนด (timeout)") from exc
        except OSError as exc:
            raise SpiceError(f"ไม่พบ ngspice: {exc}") from exc
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()[:200]
            message = f"ngspice ทำงานไม่สำเร็จ (exit code {completed.returncode})"
            raise SpiceError(f"{message}: {detail}" if detail else message)
        try:
            with open(log_path, encoding="utf-8", errors="replace") as handle:
                log_text = handle.read()
            with open(raw_path, encoding="utf-8", errors="replace") as handle:
                raw_text = handle.read()
        except OSError as exc:
            raise SpiceError(f"อ่านผลจาก ngspice ไม่ได้: {exc}") from exc
        if not raw_text.strip():
            raise SpiceError("อ่านผลจาก ngspice ไม่ได้: rawfile ว่าง")
        return log_text, raw_text
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _mean(values):
    return sum(values) / len(values)


def simulate(params, analysis):
    """Run the real engine and return SI-unit results for one analysis."""
    validate_params(params)
    netlist = build_netlist(params, analysis)
    binary = find_ngspice()
    version = ngspice_version(binary)
    _log, raw = run_netlist(netlist, binary)
    plots = parse_raw_ascii(raw)
    plot_key = {"dc": "op", "ac": "ac", "tran": "tran"}[analysis]
    if plot_key not in plots:
        raise SpiceError(f"อ่านผลจาก ngspice ไม่ได้: ไม่มีผล {analysis}")
    plot = plots[plot_key]
    result = {
        "analysis": analysis,
        "model": BJT_MODEL_NAME,
        "binary": binary,
        "version": version,
        "netlist": netlist,
        "raw_summary": f"{plot_key}: {len(plot['points'])} points",
    }

    if analysis == "dc":
        result["values"] = {
            "vb": raw_value(plot, "v(b)").real,
            "ve": raw_value(plot, "v(e)").real,
            "vc": raw_value(plot, "v(c)").real,
            "vce": (raw_value(plot, "v(c)") - raw_value(plot, "v(e)")).real,
            "ic": raw_value(plot, "i(@q1[ic])").real,
            "ib": raw_value(plot, "i(@q1[ib])").real,
        }
        return result

    count = len(plot["points"])
    if analysis == "ac":
        freq = [raw_value(plot, "frequency", i).real for i in range(count)]
        vin = [raw_value(plot, "v(in)", i) for i in range(count)]
        vout = [raw_value(plot, "v(out)", i) for i in range(count)]
        gain_db = []
        phase_deg = []
        for source, load in zip(vin, vout):
            ratio = load / source if source != 0 else complex(float("inf"), 0)
            gain_db.append(20.0 * math.log10(abs(ratio)))
            phase = math.degrees(math.atan2(load.imag, load.real)) - math.degrees(
                math.atan2(source.imag, source.real)
            )
            while phase > 180:
                phase -= 360
            while phase <= -180:
                phase += 360
            phase_deg.append(phase)
        nearest = min(range(count), key=lambda i: abs(math.log10(freq[i]) - 3))
        result.update(
            freq=freq,
            gain_db=gain_db,
            phase_deg=phase_deg,
            gain_1k_db=gain_db[nearest],
            gain_1k_hz=freq[nearest],
        )
        return result

    time = [raw_value(plot, "time", i).real for i in range(count)]
    vin = [raw_value(plot, "v(in)", i).real for i in range(count)]
    vout_raw = [raw_value(plot, "v(out)", i).real for i in range(count)]
    vin_dc = _mean(vin)
    vout_dc = _mean(vout_raw)
    result.update(
        time=time,
        vin=vin,
        vout=[value - vout_dc for value in vout_raw],
        vin_dc=vin_dc,
        vout_dc=vout_dc,
    )
    return result
