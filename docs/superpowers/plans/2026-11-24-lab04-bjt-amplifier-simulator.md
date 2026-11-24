# Lab 04 BJT CE Amplifier Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Lab 3 BJT DC-bias Flask app with real ngspice DC/AC/transient simulation of one CE voltage-divider amplifier, shown as numbers and server-rendered SVG charts with visible provenance.

**Architecture:** `spice_engine.py` builds a netlist, runs `ngspice_con -b` with a timeout in a temp dir, parses the ASCII rawfile, and returns SI-unit dicts. `app.py` adds a `/simulate` route next to the untouched `/calculate`. `spice_plots.py` turns result series into SVG geometry for the template.

**Tech Stack:** Python 3.15, Flask 3.1, ngspice-47 (`ngspice_con.exe`), Jinja2 templates, unittest, inline SVG (no JS chart library).

**Spec:** `docs/superpowers/specs/2026-11-24-lab04-bjt-amplifier-simulator-design.md`

## Global Constraints

- `dc_bias.py` must stay Flask-free and ngspice-free; `app.py` must contain no circuit equations.
- TDD: the test is written and seen failing before implementation code.
- Every route returns HTTP 200 for invalid input; no exception may become a 500.
- Thai validation text is asserted verbatim by tests.
- ngspice is called with an argument list, never `shell=True`, always with a timeout and a per-run working directory.
- SPICE results and analytical results are rendered in separate labelled sections; no hard-coded traces or values.
- Form units: V, kΩ, µF, mV peak, Hz. Engine units: V, Ω, F, V peak, Hz.
- Binary discovery order: `NGSPICE_BIN` env → `ngspice_con` → `ngspice` → `C:\Tools\ngspice\Spice64\bin\ngspice_con.exe`.
- Commit style `feat:`/`fix:`/`docs:`; never commit `.venv/`, `__pycache__`, raw run temps.

## Review Focus

- Engine binary missing or is the detaching GUI `ngspice.exe`: the page must show a Thai error, never a chart or a previous run's numbers (Task 4 + Task 6).
- Huge/invalid numbers (`1e309`, `nan`, `inf`): rejected with the shared finite message, no traceback (Task 4 + Task 5).
- Frequency 0 or negative: rejected before transient stop is derived (division by zero), no 500 (Task 4 + Task 5).
- Empty/single-point or truncated rawfile: `SpiceError`, no IndexError in chart code (Task 3 + Task 2).
- Re-submitting after a failed run: the response contains no `<section class="spice-results">` and no `<svg` chart (Task 6).

---

### Task 1: SVG plot helpers (`spice_plots.py`)

**Files:**
- Create: `spice_plots.py`
- Test: `tests/test_spice_plots.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `polyline_points(xs: list[float], ys: list[float], width: int, height: int, pad: int, x_range: tuple[float, float], y_range: tuple[float, float]) -> str` — space-separated `"x,y"` SVG points, y flipped.
  - `nice_range(values: list[float], pad_fraction: float = 0.1) -> tuple[float, float]` — finite min/max padded; equal values get ±1.
  - `bode_svg(freq: list[float], gain_db: list[float], phase_deg: list[float]) -> str` — full `<svg>` with log-frequency x axis, two labelled panels (`Gain (dB)`, `Phase (deg)`), axis text including `Hz`.
  - `wave_svg(time: list[float], vin: list[float], vout: list[float]) -> str` — full `<svg>` with `Time (ms)`, `Voltage (V)`, two polylines (`data-series="vin"` / `"vout"`), legend text.

- [ ] **Step 1: Write failing tests**

```python
def test_polyline_maps_ranges_and_flips_y():
    pts = spice_plots.polyline_points([0, 1], [0, 1], 100, 50, 5, (0, 1), (0, 1))
    assert pts == "5,45 95,5"

def test_nice_range_pads_and_handles_equal_values():
    lo, hi = spice_plots.nice_range([2.0, 2.0])
    assert lo < 2.0 < hi

def test_bode_svg_contains_gain_phase_and_units():
    svg = spice_plots.bode_svg([10, 100, 1000], [0.0, 10.0, 20.0], [180.0, 175.0, 170.0])
    assert svg.startswith("<svg")
    assert "Gain (dB)" in svg and "Phase (deg)" in svg and "Hz" in svg
    assert svg.count("<polyline") >= 2

def test_wave_svg_has_both_series_and_time_axis():
    svg = spice_plots.wave_svg([0.0, 0.001, 0.002], [0.0, 0.01, 0.0], [0.0, -0.5, 0.0])
    assert 'data-series="vin"' in svg and 'data-series="vout"' in svg
    assert "Time (ms)" in svg and "Voltage (V)" in svg

def test_plots_reject_empty_series():
    with pytest.raises(ValueError):
        spice_plots.bode_svg([], [], [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m unittest tests.test_spice_plots -v`
Expected: FAIL (`ModuleNotFoundError: spice_plots`).

- [ ] **Step 3: Implement `spice_plots.py`**

Pure functions only (no Flask, no file I/O). `bode_svg` uses `math.log10` with a guard for `freq <= 0`; `wave_svg` converts seconds to ms. Return strings built with f-strings; escape labels with `html.escape`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m unittest tests.test_spice_plots -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add spice_plots.py tests/test_spice_plots.py
git commit -m "feat: add SVG plot helpers for simulation results"
```

---

### Task 2: Netlist builder and validation (`spice_engine.py`)

**Files:**
- Create: `spice_engine.py`
- Test: `tests/test_spice_engine.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `BJT_MODEL_NAME = "2N3904"`, `BJT_MODEL_CARD` (ON Semi datasheet card, citation comment above).
  - `validate_params(params: dict) -> None` raising `ValueError` with Thai text.
  - `build_netlist(params: dict, analysis: str) -> str` with keys `vcc, r1, r2, rc, re, rl, cin, cout, amp, freq` in SI; analysis in `{"dc", "ac", "tran"}`.
  - `tran_stop(freq: float) -> tuple[float, float]` returning `(step, stop)` seconds: `step = period/200`, `stop = min(max(5*period, 5e-3), 50e-3)`.

- [ ] **Step 1: Write failing tests**

```python
PARAMS = dict(vcc=12, r1=100e3, r2=22e3, rc=2.2e3, re=1e3, rl=10e3,
              cin=10e-6, cout=10e-6, amp=0.01, freq=1e3)

def test_netlist_has_circuit_elements_in_si_units():
    n = spice_engine.build_netlist(PARAMS, "dc")
    assert "R1 vcc b 100000" in n
    assert "RC vcc c 2200" in n
    assert "CIN in b 1e-05" in n
    assert "Q1 c b e 2N3904" in n
    assert "VIN in 0 DC 0 AC 1 SIN(0 0.01 1000)" in n

def test_netlist_directive_per_analysis():
    assert ".op" in spice_engine.build_netlist(PARAMS, "dc")
    assert ".ac dec 20 10 1e+07" in spice_engine.build_netlist(PARAMS, "ac")
    assert ".tran" in spice_engine.build_netlist(PARAMS, "tran")

def test_netlist_saves_transistor_currents_and_ascii_raw():
    n = spice_engine.build_netlist(PARAMS, "dc")
    assert ".save all @q1[ic] @q1[ib]" in n
    assert ".option filetype=ascii" in n
    assert spice_engine.BJT_MODEL_CARD in n

def test_validation_rejects_non_positive_and_non_finite():
    for bad in ({"vcc": 0}, {"re": -1}, {"freq": 0}, {"r1": float("inf")}):
        p = {**PARAMS, **bad}
        with pytest.raises(ValueError):
            spice_engine.validate_params(p)

def test_unknown_analysis_rejected():
    with pytest.raises(ValueError):
        spice_engine.build_netlist(PARAMS, "noise")

def test_tran_stop_scales_with_frequency_and_is_capped():
    step, stop = spice_engine.tran_stop(1e3)
    assert step == pytest.approx(5e-6) and stop == pytest.approx(5e-3)
    assert spice_engine.tran_stop(1e6)[1] <= 50e-3
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv\Scripts\python.exe -m unittest tests.test_spice_engine -v`
Expected: FAIL (`ModuleNotFoundError: spice_engine`).

- [ ] **Step 3: Implement builder + validation**

Validation order: finite check for all keys → report first offending group with the shared messages: `VCC ต้องมากกว่า 0`, `R1, R2, RC, RE, RL ต้องมากกว่า 0`, `CIN, COUT ต้องมากกว่า 0`, `amplitude ต้องไม่ติดลบ`, `freq ต้องมากกว่า 0`. Format numbers with `repr(float(v))` so tests see `1e-05`.

- [ ] **Step 4: Run to verify pass**

Run: `.venv\Scripts\python.exe -m unittest tests.test_spice_engine -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add spice_engine.py tests/test_spice_engine.py
git commit -m "feat: build and validate CE amplifier netlists"
```

---

### Task 3: ASCII rawfile parser + real fixture

**Files:**
- Modify: `spice_engine.py`
- Create: `tests/fixtures/ce_reference.raw`, `tests/fixtures/ce_reference.log`
- Test: `tests/test_spice_engine.py`

**Interfaces:**
- Consumes: `build_netlist` from Task 2.
- Produces:
  - `parse_raw_ascii(text: str) -> dict[str, dict]` mapping `"op"`, `"ac"`, `"tran"` to `{"variables": dict[str, int], "points": list[list[complex | float]]}`.
  - `raw_value(plot: dict, name: str, point: int = 0) -> complex`.

- [ ] **Step 1: Capture the fixture from the real binary**

Run the netlist from Task 2 with `ngspice_con -b -o tests/fixtures/ce_reference.log -r tests/fixtures/ce_reference.raw`, then confirm the raw has three `Plotname:` blocks (Operating Point, AC Analysis, Transient Analysis) and record the exact binary path/version in `docs/validation.md`.

- [ ] **Step 2: Write failing parser tests**

```python
def test_reference_fixture_parses_all_three_plots():
    plots = spice_engine.parse_raw_ascii(RAW.read_text(encoding="utf-8"))
    assert set(plots) == {"op", "ac", "tran"}
    assert len(plots["ac"]["points"]) == 121
    assert "v(out)" in plots["ac"]["variables"]

def test_op_voltage_and_transistor_current_available():
    plots = spice_engine.parse_raw_ascii(RAW.read_text(encoding="utf-8"))
    vb = spice_engine.raw_value(plots["op"], "v(b)")
    ic = spice_engine.raw_value(plots["op"], "i(@q1[ic])")
    assert 1.0 < vb.real < 3.0 and 0.5e-3 < ic.real < 5e-3

def test_truncated_or_empty_raw_raises():
    for text in ("", "Title: x\nPlotname: AC Analysis\n"):
        with pytest.raises(spice_engine.SpiceError):
            spice_engine.parse_raw_ascii(text)
```

- [ ] **Step 3: Run to verify failure**

Run: `.venv\Scripts\python.exe -m unittest tests.test_spice_engine -v`
Expected: FAIL (`AttributeError: module has no attribute 'parse_raw_ascii'`).

- [ ] **Step 4: Implement parser**

Split on lines starting `Plotname:`; read `Flags`, `No. Variables`, `No. Points`, `Variables:` (index→name), `Values:`; parse `index value[,value]`; complex when `Flags: complex` or a comma is present. Raise `SpiceError("อ่านผลจาก ngspice ไม่ได้: ...")` for missing keys, count mismatch, or unparsable numbers.

- [ ] **Step 5: Run to verify pass, commit**

Run: `.venv\Scripts\python.exe -m unittest tests.test_spice_engine -v` → PASS.

```bash
git add spice_engine.py tests/test_spice_engine.py tests/fixtures
git commit -m "feat: parse ngspice ASCII rawfile output"
```

---

### Task 4: Runner, discovery, and `simulate()`

**Files:**
- Modify: `spice_engine.py`
- Test: `tests/test_spice_engine.py`

**Interfaces:**
- Consumes: builder + parser above.
- Produces:
  - `find_ngspice(env=os.environ) -> str` (raises `SpiceError` when nothing is found).
  - `run_netlist(netlist: str, binary: str, timeout: float = 20.0) -> tuple[str, str]` → `(log_text, raw_text)`, using `tempfile.mkdtemp`, `subprocess.run([...], timeout=timeout, cwd=tmp, capture_output=True, text=True)`.
  - `simulate(params: dict, analysis: str) -> dict` with common keys `analysis`, `model`, `binary`, `version`, `netlist`, `raw_summary`; `dc` adds `values` (`vb, ve, vc, vce, ic, ib` floats); `ac` adds `freq, gain_db, phase_deg, gain_1k_db`; `tran` adds `time, vin, vout, vin_dc, vout_dc`.

- [ ] **Step 1: Write failing tests**

```python
def test_missing_binary_raises_thai_error(monkeypatch):
    monkeypatch.setattr(spice_engine.shutil, "which", lambda name: None)
    with pytest.raises(spice_engine.SpiceError, match="ไม่พบ ngspice"):
        spice_engine.find_ngspice({})

def test_timeout_becomes_spice_error(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="ngspice", timeout=1)
    monkeypatch.setattr(spice_engine.subprocess, "run", boom)
    with pytest.raises(spice_engine.SpiceError, match="timeout"):
        spice_engine.run_netlist("net", "ngspice_con", timeout=1)

def test_nonzero_exit_and_empty_raw_are_errors(monkeypatch):
    # fake run writes nothing / returns code 1; assert SpiceError with exit code text
    ...

def test_simulate_dc_reads_reference_fixture(monkeypatch):
    # monkeypatch run_netlist to return the fixture log/raw
    result = spice_engine.simulate(PARAMS, "dc")
    assert result["analysis"] == "dc"
    assert result["values"]["vce"] == pytest.approx(result["values"]["vc"] - result["values"]["ve"])
    assert 0.5e-3 < result["values"]["ic"] < 5e-3

def test_simulate_ac_and_tran_shapes(monkeypatch):
    ac = spice_engine.simulate(PARAMS, "ac")
    assert len(ac["freq"]) == len(ac["gain_db"]) == len(ac["phase_deg"]) == 121
    tr = spice_engine.simulate(PARAMS, "tran")
    assert len(tr["time"]) == len(tr["vin"]) == len(tr["vout"])
    assert tr["vout_dc"] > 1.0
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv\Scripts\python.exe -m unittest tests.test_spice_engine -v`
Expected: FAIL (`simulate` not defined).

- [ ] **Step 3: Implement runner + simulate**

Discovery checks `env["NGSPICE_BIN"]` exists, else `shutil.which("ngspice_con")`, `shutil.which("ngspice")`, then the known Windows path. Reject a discovered path whose stem is `ngspice` when `ngspice_con` exists next to it (GUI detach). Non-zero exit → `SpiceError(f"ngspice ทำงานไม่สำเร็จ (exit code {code})")`. Empty/short raw → parser error. Version line from `ngspice_con -v` first `** ngspice-` line, cached.

- [ ] **Step 4: Run to verify pass**

Run: `.venv\Scripts\python.exe -m unittest tests.test_spice_engine -v` → PASS.

- [ ] **Step 5: Real-binary smoke test (skipped when absent)**

```python
@unittest.skipUnless(spice_engine.find_ngspice() if available else False, "ngspice not installed")
```

Assert finite DC values and `IC > 0` for `PARAMS`.

- [ ] **Step 6: Commit**

```bash
git add spice_engine.py tests/test_spice_engine.py
git commit -m "feat: run ngspice with timeout and return SI results"
```

---

### Task 5: `/simulate` route and form parsing

**Files:**
- Modify: `app.py`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `spice_engine.simulate`, `spice_engine.SpiceError`.
- Produces: `POST /simulate` rendering `index.html` with `simulation` dict or `sim_error`/`sim_form` context.

- [ ] **Step 1: Write failing route tests**

```python
def test_simulate_rejects_zero_re_with_200(client):
    r = client.post("/simulate", data=SIM_FORM | {"re": "0", "analysis": "dc"})
    assert r.status_code == 200
    assert "RE" in r.get_data(as_text=True) and "มากกว่า 0" in r.get_data(as_text=True)
    assert 'class="spice-results"' not in r.get_data(as_text=True)

def test_simulate_rejects_missing_or_text_field(client):
    r = client.post("/simulate", data={k: v for k, v in SIM_FORM.items() if k != "rl"})
    assert r.status_code == 200 and "กรอกข้อมูลให้ครบ" in r.get_data(as_text=True)

def test_simulate_renders_engine_error_without_charts(client, monkeypatch):
    monkeypatch.setattr(app.spice_engine, "simulate", lambda *a, **k: (_ for _ in ()).throw(app.spice_engine.SpiceError("ไม่พบ ngspice: test")))
    html = client.post("/simulate", data=SIM_FORM).get_data(as_text=True)
    assert "ไม่พบ ngspice: test" in html and "<svg" not in html

def test_simulate_renders_dc_values_and_provenance(client, monkeypatch):
    # fake simulate returns DC dict; assert VB/VE/VC/VCE/IC, "ngspice", model, units
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv\Scripts\python.exe -m unittest tests.test_web -v` → FAIL (404/route missing).

- [ ] **Step 3: Implement route**

`_parse_sim_form(form) -> (analysis, params)` converts kΩ→Ω (`*1000`), µF→F (`*1e-6`), mV→V (`/1000`); raises `ValueError(FORM_ERROR)` on missing/unparsable. Catch `ValueError`/`SpiceError`, always render with HTTP 200 and echo raw form values. Analytical reference computed only when DC succeeds via `dc_bias.solve(...)`.

- [ ] **Step 4: Run to verify pass, commit**

Run: `.venv\Scripts\python.exe -m unittest tests.test_web -v` → PASS.

```bash
git add app.py tests/test_web.py
git commit -m "feat: add ngspice simulation route"
```

---

### Task 6: Template, CSS, charts, provenance

**Files:**
- Modify: `templates/index.html`, `static/style.css`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `simulation` context (`analysis`, `values`/series, `model`, `binary`, `version`), `spice_plots.bode_svg`, `spice_plots.wave_svg`, `analytical` dict.
- Produces: sections with classes `spice-results`, `analytical-reference`; charts carry `data-series` attributes.

- [ ] **Step 1: Write failing rendering tests**

```python
def test_dc_page_separates_spice_and_analytical(client, monkeypatch):
    html = client.post("/simulate", data=SIM_FORM | {"analysis": "dc"}).get_data(as_text=True)
    assert 'class="spice-results"' in html and 'class="analytical-reference"' in html
    assert "ngspice" in html and "Analytical" in html
    assert "2N3904" in html

def test_ac_page_has_bode_svg_with_axes(client, monkeypatch):
    html = client.post("/simulate", data=SIM_FORM | {"analysis": "ac"}).get_data(as_text=True)
    assert "<svg" in html and "Gain (dB)" in html and "Phase (deg)" in html

def test_tran_page_has_waveform_and_dc_offset_note(client, monkeypatch):
    html = client.post("/simulate", data=SIM_FORM | {"analysis": "tran"}).get_data(as_text=True)
    assert 'data-series="vout"' in html and "DC offset" in html

def test_changing_source_changes_rendered_chart(client, monkeypatch):
    # fake engine echoes amp into vout values; assert two runs produce different polyline data
```

- [ ] **Step 2: Run to verify failure** → FAIL.

- [ ] **Step 3: Implement template sections + CSS**

Keep the Lab 3 form untouched. Add: simulation form (analysis radio, circuit fields, source fields), status line (engine/model/version), DC table, AC chart, transient chart + offset note, collapsible analytical reference. CSS: two-column grid ≥ 900 px, stacked below; charts `width:100%`, readable labels.

- [ ] **Step 4: Run full suite** → PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add templates/index.html static/style.css tests/test_web.py
git commit -m "feat: show SPICE results and charts with provenance"
```

---

### Task 7: Docs and reproducibility

**Files:**
- Modify: `README.md`, `docs/validation.md`, `AGENTS.md`
- Test: none (manual read-through against handout checklist)

- [ ] **Step 1: README** — ngspice install path/version, `NGSPICE_BIN`, run commands, simulation usage, model citation.
- [ ] **Step 2: `docs/validation.md`** — independent reference calculations for DC (analytical + model note), fixture provenance, B1–B8 table with observed values and statuses.
- [ ] **Step 3: `AGENTS.md`** — add the engine rule (no Flask/HTML in `spice_engine.py`; SPICE vs analytical separation).
- [ ] **Step 4: Commit**

```bash
git add README.md docs/validation.md AGENTS.md
git commit -m "docs: record ngspice setup and B1-B8 validation"
```

---

### Task 8: Browser acceptance, UI polish, publish

**Files:** `docs/validation.md`, `docs/captures/*` (screenshots), possibly template/CSS tweaks.

- [ ] **Step 1: Restart Flask, replay B1–B8 with real browser tools**, recording actual values (and ngspice log evidence).
- [ ] **Step 2: Screenshot desktop (~1280) and mobile (~390).**
- [ ] **Step 3: Fix only issues found; re-run affected cases.**
- [ ] **Step 4: Review `git diff`, commit, push to `origin/main`** so GitHub Desktop shows the branch up to date.
- [ ] **Step 5: Report repo URL + commit SHA + honest PASS/FAIL/NOT RUN table.**
