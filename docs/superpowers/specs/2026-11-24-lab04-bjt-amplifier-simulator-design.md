# Lab 04 — BJT CE Amplifier Simulator v1 (Design)

- Date: 2026-11-24
- Course: ENG29 2121 · Lab 04
- Base: existing Lab 3 Flask app (`app.py`, `dc_bias.py`, `templates/index.html`, 49 tests)
- Handout: `Downloads/Lab04_BJT_Amplifier_Simulator_2-2569.html`

## 1. Intent

Extend the Lab 3 DC-bias web app into a working **Common-Emitter voltage-divider
amplifier simulator** that runs **real ngspice** (`.op`, `.ac`, `.tran`) and shows
the resulting numbers and charts in the browser, without breaking the three
analytical DC-bias modes from Lab 3.

The learner (and TA) must be able to trace every displayed value back to a real
solver run, a named BJT model, and an explicit unit — and see analytical and
SPICE results labelled as different things.

## 2. Goals / non-goals / anti-goals

**Goals**

1. Keep all three Lab 3 modes (`divider`, `fixed`, `emitter`) and their tests
   working unchanged (B1 regression).
2. New `spice_engine.py`: build netlist → run ngspice via `subprocess` → parse
   ASCII rawfile → return plain dicts with SI units.
3. New `/simulate` route for the one reference CE voltage-divider circuit,
   supporting `analysis=dc|ac|tran`.
4. Show DC operating point (VB, VE, VC, VCE, IC), AC Bode (|gain| dB, phase,
   Hz), and transient Vin/Vout vs time, all generated from parsed run data.
5. Show engine provenance and status: binary path/version, model name, run
   result, and clear separation "ngspice (real run)" vs "Analytical reference".
6. Handle every failure mode (binary missing, non-zero exit, timeout, unreadable
   output) with HTTP 200 + Thai error; never render stale data as success.
7. UI polish for desktop (~1280 px) and mobile (~390 px), Impeccable-assisted
   if available.
8. Record B1–B8 evidence in `docs/validation.md` with real values.

**Non-goals (from handout)**

Drag-and-drop circuit editor, free-form netlists, AC/transient for the other
bias modes, FETs, writing our own SPICE solver, animated current overlays,
deployment, emitter-bypass capacitor.

**Anti-goals**

Hard-coded traces or success values; mock plots presented as ngspice output;
merging analytical and SPICE numbers into one table; returning a previous run's
chart after a failed run; `shell=True`; unbounded subprocess.

## 3. Constraints

- `dc_bias.py` stays a pure engineering module (no Flask, no ngspice).
- `app.py` stays the HTTP layer; no circuit equations in it.
- Templates display only; unit display conversion allowed, no re-derivation.
- TDD: failing test first, then implementation.
- Every route returns HTTP 200 on bad input.
- Thai validation strings are asserted verbatim by tests.
- Windows dev machine; ngspice installed at
  `C:\Tools\ngspice\Spice64\bin\ngspice_con.exe` (ngspice-47, 2026-08-11).
  Node 26.13.1 installed for Playwright MCP / Impeccable.

## 4. Approaches considered

| # | Approach | Trade-off | Verdict |
|---|---|---|---|
| A | New `/simulate` route + `spice_engine.py` + server-rendered inline SVG plots, ASCII rawfile parsing | Keeps Lab 3 path untouched; no new runtime dependency; works offline; slightly more Python for chart geometry | **Chosen** |
| B | Extend `/calculate` to branch analytical/SPICE and reuse one form | Fewer routes, but mixes two models in one code path, makes B1 regression and error handling risky, and makes "which model produced this number" ambiguous | Rejected |
| C | Client-side Chart.js (CDN) with JSON payload | Prettier charts with less code, but adds network dependency/CDN in a lab that must be reproducible offline, and puts plotting logic in JS | Rejected |
| D | `.control` block + `wrdata` instead of rawfile | Simple columnar files, but handout warns about mixing `.control` with batch; rawfile ASCII already gives named variables and plot types with no mixing | Rejected after spike |

Run-mode spike (2026-11-24): `ngspice_con.exe -b -o run.log -r run.raw netlist.cir`
with `.option filetype=ascii` produced three labelled plots (Operating Point,
AC Analysis, Transient Analysis), including `i(@q1[ic])` via `.save`. The GUI
`ngspice.exe` detaches immediately on Windows, so the engine must prefer
`ngspice_con`.

## 5. Architecture

```
Browser form (/simulate)
   ↓ POST
app.py::simulate  ── validate numbers/units ──► spice_engine.simulate_*
   ↓                                              ↓
template: two labelled sections              subprocess (args list, timeout, temp dir)
   ├─ ngspice results (real run)                  ↓
   └─ analytical reference (dc_bias.solve)     ngspice_con -b -o run.log -r run.raw ce.cir
   ↓                                              ↓
spice_plots.py (series → SVG geometry)       ASCII rawfile parser → dicts (SI)
```

Files:

- `spice_engine.py` (new, pure): binary discovery, netlist builder, runner,
  rawfile parser, three result builders, Thai error messages.
- `spice_plots.py` (new, pure): pure functions turning `(x, y)` series into SVG
  path/polyline strings, tick labels, min/max; no I/O.
- `app.py`: `GET /` unchanged semantics; `POST /calculate` unchanged; new
  `POST /simulate`.
- `templates/index.html`: Lab 3 form untouched; new simulation form + results
  sections (SPICE vs analytical).
- `static/style.css`: layout for two-column desktop, stacked mobile.
- `tests/test_spice_engine.py`, `tests/test_spice_plots.py`, additions to
  `tests/test_web.py`.
- `docs/validation.md`, `README.md`, `AGENTS.md` (engine rule note).

## 6. Circuit and netlist

Reference circuit (one topology, fixed node names):

```
VCC ──┬── R1 ──┬── RC ──┬── Cout ── out ── RL ── GND
      │        │        │
      │        b        c
      │        │        │
      │       Q1 (2N3904, C=c B=b E=e)
      │        │
      └── R2 ──┴── RE ── e ── GND

VIN(in) ── Cin ── b
```

Netlist template (values printed in SI with SPICE suffixes):

```
* CE voltage-divider amplifier — generated
.model 2N3904 NPN(Is=6.734f Xti=3 ... Rb=10)
VCC vcc 0 DC {vcc}
VIN in 0 DC 0 AC 1 SIN(0 {amp} {freq})
R1 vcc b {r1}
R2 b 0 {r2}
RC vcc c {rc}
RE e 0 {re}
Q1 c b e 2N3904
CIN in b {cin}
COUT c out {cout}
RL out 0 {rl}
.save all @q1[ic] @q1[ib]
.option filetype=ascii
{analysis directive}
.end
```

- BJT model card: **2N3904**, ON Semiconductor datasheet "Spice Model" line
  (2N3904/D). Card text stored in `spice_engine.py` with the citation comment;
  source also recorded in `docs/validation.md`. No invented parameters.
- `analysis` directives:
  - `dc`: `.op`
  - `ac`: `.ac dec 20 10 10Meg` (fixed, documented in UI)
  - `tran`: `.tran {step} {stop}` with `step = period/200`,
    `stop = min(max(5 periods, 5 ms), 50 ms)`, both documented in UI.
- Units in: V, Ω (converted from kΩ in the route), µF (from form), mV peak, Hz.
- AC reference point: **Vin = node `in` (source node before Cin)**, so
  gain = `V(out)/V(in)`; stated in the chart caption.
- Transient display: Vout DC offset (≈ VC) removed before plotting, with the
  offset value and "AC component" label shown, so phase inversion is readable.

## 7. Engine API and parsing

```python
NGSPICE_BIN_ENV = "NGSPICE_BIN"

class SpiceError(Exception): ...          # Thai message, safe to show

def find_ngspice() -> str                  # env → ngspice_con → ngspice → known paths
def ngspice_version(binary: str) -> str    # cached, from `-v`
def build_netlist(params: dict, analysis: str) -> str
def run_netlist(netlist: str, timeout: float = 20.0) -> tuple[str, str]  # (log, raw)
def parse_raw_ascii(text: str) -> dict[str, RawPlot]   # plotname → variables, points
def simulate_dc(params) -> dict   # vb, ve, vc, vce, ic, model, binary, version
def simulate_ac(params)  -> dict  # freq[], gain_db[], phase_deg[]
def simulate_tran(params)-> dict  # t[], vin[], vout[], vout_dc
```

Parsing rules: split on `Plotname:` blocks; read `Flags`, `No. Variables`,
`No. Points`, `Variables:` list, `Values:` rows; rows are `index value` with
complex `re,im` for AC; map raw names (`v(b)`, `i(@q1[ic])`) to result keys.
Reject missing plots, wrong point counts, non-finite numbers, and empty files —
never silently return partial data.

Error messages (pinned by tests):

- `ไม่พบ ngspice: ...`
- `ngspice ทำงานไม่สำเร็จ (exit code ...)`
- `ngspice ใช้เวลาเกินกำหนด (timeout)`
- `อ่านผลจาก ngspice ไม่ได้: ...`
- `ค่าทุกช่องต้องเป็นจำนวนจริงที่จำกัด (finite)` (reuse wording)

## 8. Validation (form)

Common: finite numbers; `vcc > 0`; `r1, r2, rc, re, rl > 0`;
`cin, cout > 0`; `amp >= 0`; `freq > 0`; frequency upper bound 1 MHz;
amplitude upper bound 1 V; transient stop capped (see §6). Errors are returned
as rendered text with HTTP 200 and the submitted values echoed.

## 9. Routes and UI

- `GET /` and `POST /calculate`: unchanged (Lab 3 regression).
- `POST /simulate`: parses `analysis` + circuit/source fields; on success renders
  `spice` results and the analytical `dc_bias.solve(...)` reference for the same
  resistors; on failure renders only the error (no charts, no old numbers).
- Result blocks:
  1. `ngspice — DC operating point (.op)` table + model + binary/version + status.
  2. `AC frequency response` SVG (log-frequency, dB gain, phase in second panel)
     + gain at 1 kHz read from the run.
  3. `Transient` SVG (Vin/Vout, ms/V) + phase-inversion note.
  4. `Analytical reference (dc_bias.py)` collapsed block with a note that the
     β/VBE model differs from the 2N3904 model and values need not match.
- A status line always states which engine produced the visible numbers.

## 10. Tests (TDD order)

1. `test_spice_plots`: line geometry, axis ranges, empty/single-point series.
2. `test_spice_engine` netlist: units/formatting, model card present, directive
   per analysis, `.save` line, no `shell=True` usage (source grep).
3. `test_spice_engine` parser: real captured `run.raw` fixture (checked in under
   `tests/fixtures/`, provenance in validation.md) → OP/AC/TRAN values; malformed
   and truncated files raise `SpiceError`.
4. Failure paths with monkeypatched runner: binary missing, exit code ≠ 0,
   timeout, empty raw.
5. `test_web` `/simulate`: invalid input → 200 + Thai error, no SPICE section;
   success with monkeypatched engine → labels/units/values rendered; analytical
   section present and distinct; B3/B6 semantics (different input → different
   rendered values).
6. Optional integration test: skipped when ngspice absent; runs the real binary
   and asserts finite OP values and IC > 0.

## 11. Validation plan (handout B1–B8)

B1 Lab 3 regression (A1–A5 replay), B2 DC SPICE values + log, B3 change RE,
B4 AC Bode axes/units, B5 transient 10 mV/1 kHz phase inversion, B6 change
amplitude/frequency, B7 invalid RE=0 and (if possible) engine-unavailable,
B8 desktop/mobile screenshots. Record method, expected (independent
calculation or real log), observed, units, status (PASS/FAIL/NOT RUN) in
`docs/validation.md`. Playwright MCP after Node install; fall back to the
built-in browser with the method named honestly.

## 12. Left to the builder

Chart aesthetics/colors, exact copy, responsive breakpoints, how much of the AC
sweep to label, whether to add a table of a few sampled points, and the order of
UI polish. Any change to the circuit topology or model requires a new design
round.
