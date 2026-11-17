# Lab 03 Bias Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** เพิ่มโหมด Fixed Bias และ Emitter Bias ให้เว็บ Flask จาก Lab 02 พร้อมเลือกโหมดจากฟอร์ม และตรวจรับ A1–A5 ผ่านเบราว์เซอร์จริงโดยผล Divider เดิมไม่เปลี่ยน

**Architecture:** คงโครงเดิม 3 ชั้น — `dc_bias.py` เก็บสมการทุกโหมดเป็น pure functions, `app.py` เลือกฟังก์ชันตาม `mode` ที่ส่งมาและแปลง kΩ→Ω จุดเดียว, `templates/index.html` แสดงเฉพาะช่องของโหมดและ render ผลที่ route ส่งมา การเลือกโหมดใช้ GET reload ฝั่ง server ไม่ใช้ JavaScript

**Tech Stack:** Python 3.15, Flask 3.1.3, Jinja2, unittest

**Spec:** `docs/superpowers/specs/2026-11-17-lab03-bias-modes-design.md`

## Global Constraints

- `dc_bias.py` ห้าม import Flask/HTTP/HTML
- ข้อความไทยห้ามแก้แม้แต่ตัวอักษรเดียว:
  - `ค่าทุกช่องต้องเป็นจำนวนจริงที่จำกัด (finite)`
  - `R1, R2, RC, RE ต้องมากกว่า 0`
  - `VCC ต้องมากกว่า 0`, `beta ต้องมากกว่า 0`, `VBE ต้องมากกว่า 0`
  - warning ทุกข้อลงท้าย `ค่าที่แสดงเชื่อถือไม่ได้`
- ข้อความใหม่ที่กำหนดในแผนนี้ (ใช้ตรงตัว): `RB, RC ต้องมากกว่า 0`, `RB, RC, RE ต้องมากกว่า 0`, `โหมดวงจรไม่ถูกต้อง: ต้องเลือกจาก Voltage Divider Bias, Fixed Bias หรือ Emitter Bias`
- ตัวต้านทานบนฟอร์มเป็น kΩ แปลงเป็น Ω ใน `app.py` ครั้งเดียวต่อช่อง
- route ทุกเส้นคืน HTTP 200 แม้อินพุตผิด
- ห้ามมีตัวเลขผลลัพธ์หรือสมการใน template
- Region ตามลำดับ: `IB ≤ 0` → `Cutoff`; `VCE < 0.2` → `Saturation`; อื่น ๆ → `Forward Active`
- คำสั่งเทสต์: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` (รันจาก repo root)
- Commit style: `feat:`/`docs:` นำหน้า ข้อความสั้นอิงพฤติกรรม

## Review Focus

1. POST ที่ไม่มีช่อง `mode` (ฟอร์ม/เทสต์ Lab 02) → ต้องคำนวณ Divider ตามปกติ ไม่ error
2. `mode` ที่ส่งมาแต่ไม่รู้จัก → HTTP 200 + ข้อความ error, ไม่มีผลลัพธ์, ห้าม fallback ไป Divider
3. ค่าตัวต้านทานของโหมดนั้น ≤ 0 (เช่น `rb=0`, `re=0`) → ข้อความระบุชื่อช่องของโหมด, ไม่มีผลรอบเก่าค้าง
4. ค่า finite ที่ล้นกลางการคำนวณ (เช่น `rb=1e-307`) → ต้องได้ error `จำกัด` ไม่ใช่ `inf`/`nan` บนหน้าเว็บ
5. สลับโหมดทาง GET แล้วส่งค่าที่ไม่เกี่ยวกับโหมดนั้น (เช่นส่ง `r1` ตอน Fixed) → ต้องไม่ crash และไม่ทำให้ผลเปลี่ยน

---

### Task 1: Fixed Bias solver

**Files:**
- Modify: `dc_bias.py`
- Test: `tests/test_dc_bias.py`

**Interfaces:**
- Consumes: ไม่มี
- Produces: `solve_fixed(vcc: float, rb: float, rc: float, beta: float, vbe: float) -> dict` คืนคีย์ `mode` (= `"Fixed Bias"`), `ib, ic, ie, vb, ve, vc, vce, region, warnings` (SI: Ω, V, A)
- คง `validate_inputs(vcc, r1, r2, rc, re, beta, vbe)` และ `solve(vcc, r1, r2, rc, re, beta, vbe)` เดิมทุกประการ

- [ ] **Step 1: เขียนเทสต์ที่ยังไม่ผ่านใน `tests/test_dc_bias.py`**

```python
from dc_bias import solve_fixed


class TestFixedBias(unittest.TestCase):
    def test_reference_case(self):
        # VCC=12, RB=1M, RC=2.2k, beta=100, VBE=0.7
        r = solve_fixed(12.0, 1_000_000.0, 2_200.0, 100.0, 0.7)
        self.assertAlmostEqual(r["ib"], 1.13e-05, places=9)
        self.assertAlmostEqual(r["ic"], 1.13e-03, places=9)
        self.assertAlmostEqual(r["ie"], 1.1413e-03, places=9)
        self.assertAlmostEqual(r["vb"], 0.7, places=9)
        self.assertAlmostEqual(r["ve"], 0.0, places=9)
        self.assertAlmostEqual(r["vc"], 9.514, places=9)
        self.assertAlmostEqual(r["vce"], 9.514, places=9)
        self.assertEqual(r["mode"], "Fixed Bias")
        self.assertEqual(r["region"], "Forward Active")
        self.assertEqual(r["warnings"], [])

    def test_zero_rb_rejected_names_rb(self):
        with self.assertRaisesRegex(ValueError, "RB, RC ต้องมากกว่า 0"):
            solve_fixed(12.0, 0.0, 2_200.0, 100.0, 0.7)

    def test_non_finite_rejected(self):
        with self.assertRaisesRegex(ValueError, "จำกัด"):
            solve_fixed(12.0, float("inf"), 2_200.0, 100.0, 0.7)

    def test_overflow_rejected(self):
        # rb เล็กมาก: ib finite แต่ beta*ib ล้นเป็น inf -> ต้องถูกปฏิเสธ
        with self.assertRaisesRegex(ValueError, "จำกัด"):
            solve_fixed(12.0, 1e-307, 2_200.0, 100.0, 0.7)

    def test_cutoff_when_vcc_below_vbe(self):
        r = solve_fixed(0.5, 1_000_000.0, 2_200.0, 100.0, 0.7)
        self.assertLess(r["ib"], 0.0)
        self.assertEqual(r["region"], "Cutoff")
        self.assertIn("เชื่อถือไม่ได้", r["warnings"][0])

    def test_saturation(self):
        r = solve_fixed(12.0, 1_000_000.0, 20_000.0, 100.0, 0.7)
        self.assertLess(r["vce"], 0.2)
        self.assertEqual(r["region"], "Saturation")
        self.assertIn("เชื่อถือไม่ได้", r["warnings"][0])
```

- [ ] **Step 2: รันเทสต์ให้เห็นว่า fail**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_dc_bias.TestFixedBias -v`
Expected: FAIL — `ImportError: cannot import name 'solve_fixed'`

- [ ] **Step 3: เพิ่ม validation helper และ `solve_fixed` ใน `dc_bias.py`**

- แยกการตรวจ finite/`VCC`/`beta`/`VBE` เป็น helper ภายในที่ข้อความเดิมทุกตัวอักษร เช่น `_check_common(vcc, beta, vbe)` เรียกจากทั้ง `validate_inputs` และฟังก์ชันใหม่
- ตรวจตัวต้านทานด้วย helper ที่รับ mapping ชื่อ→ค่า แล้วสร้างข้อความ `f"{', '.join(names)} ต้องมากกว่า 0"` เพื่อให้ Divider ยังได้ `R1, R2, RC, RE ต้องมากกว่า 0` ตรงเดิม และ Fixed ได้ `RB, RC ต้องมากกว่า 0`
- `solve_fixed` คำนวณ `IB = (VCC − VBE)/RB`, `IC = βIB`, `IE = (β+1)IB`, `VE = 0`, `VB = VBE`, `VC = VCC − IC·RC`, `VCE = VC` แล้วตรวจ `math.isfinite` ของผลทุกตัวก่อนจำแนก region/คืน dict
- warning ของ Fixed ใช้ข้อความ `"IB <= 0: ทรานซิสเตอร์ตัด (Cutoff) — แบบจำลอง Forward-Active ใช้ไม่ได้ ค่าที่แสดงเชื่อถือไม่ได้"` (Saturation ใช้ข้อความเดิมของ Divider ได้)

- [ ] **Step 4: รันเทสต์ทั้งหมด**

Run: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: PASS ทั้งหมด (22 เดิม + 6 ใหม่)

- [ ] **Step 5: Commit**

```bash
git add dc_bias.py tests/test_dc_bias.py
git commit -m "feat: add fixed bias solver"
```

---

### Task 2: Emitter Bias solver

**Files:**
- Modify: `dc_bias.py`
- Test: `tests/test_dc_bias.py`

**Interfaces:**
- Consumes: helper validation จาก Task 1
- Produces: `solve_emitter(vcc: float, rb: float, rc: float, re: float, beta: float, vbe: float) -> dict` คืนคีย์ชุดเดียวกับ `solve_fixed` โดย `mode` = `"Emitter Bias"`

- [ ] **Step 1: เขียนเทสต์ที่ยังไม่ผ่าน**

```python
from dc_bias import solve_emitter


class TestEmitterBias(unittest.TestCase):
    def test_reference_case(self):
        # A3: VCC=12, RB=1M, RC=2.2k, RE=1k, beta=100, VBE=0.7
        r = solve_emitter(12.0, 1_000_000.0, 2_200.0, 1_000.0, 100.0, 0.7)
        self.assertAlmostEqual(r["ib"], 1.026339691e-05, places=9)
        self.assertAlmostEqual(r["ic"], 1.026339691e-03, places=9)
        self.assertAlmostEqual(r["ie"], 1.036603088e-03, places=9)
        self.assertAlmostEqual(r["vb"], 1.736603088, places=9)
        self.assertAlmostEqual(r["ve"], 1.036603088, places=9)
        self.assertAlmostEqual(r["vc"], 9.742052679, places=9)
        self.assertAlmostEqual(r["vce"], 8.705449591, places=9)
        self.assertEqual(r["mode"], "Emitter Bias")
        self.assertEqual(r["region"], "Forward Active")

    def test_larger_re_lowers_ic(self):
        # A4: RE=2k -> IC ลดจาก A3
        base = solve_emitter(12.0, 1_000_000.0, 2_200.0, 1_000.0, 100.0, 0.7)
        larger = solve_emitter(12.0, 1_000_000.0, 2_200.0, 2_000.0, 100.0, 0.7)
        self.assertLess(larger["ic"], base["ic"])
        self.assertAlmostEqual(larger["ic"], 9.400998336106e-04, places=9)
        self.assertAlmostEqual(larger["vce"], 8.032778702, places=9)

    def test_zero_re_rejected_names_re(self):
        with self.assertRaisesRegex(ValueError, "RB, RC, RE ต้องมากกว่า 0"):
            solve_emitter(12.0, 1_000_000.0, 2_200.0, 0.0, 100.0, 0.7)

    def test_overflow_rejected(self):
        with self.assertRaisesRegex(ValueError, "จำกัด"):
            solve_emitter(12.0, 1e-307, 2_200.0, 1_000.0, 100.0, 0.7)

    def test_cutoff_when_vcc_below_vbe(self):
        r = solve_emitter(0.5, 1_000_000.0, 2_200.0, 1_000.0, 100.0, 0.7)
        self.assertEqual(r["region"], "Cutoff")
        self.assertIn("เชื่อถือไม่ได้", r["warnings"][0])

    def test_saturation(self):
        r = solve_emitter(12.0, 1_000_000.0, 20_000.0, 1_000.0, 100.0, 0.7)
        self.assertEqual(r["region"], "Saturation")
        self.assertIn("เชื่อถือไม่ได้", r["warnings"][0])
```

- [ ] **Step 2: รันให้เห็น fail**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_dc_bias.TestEmitterBias -v`
Expected: FAIL — `ImportError: cannot import name 'solve_emitter'`

- [ ] **Step 3: เพิ่ม `solve_emitter` ใน `dc_bias.py`**

`IB = (VCC − VBE)/[RB + (β+1)RE]` แล้ว `IC = βIB`, `IE = (β+1)IB`, `VE = IE·RE`, `VB = VE + VBE`, `VC = VCC − IC·RC`, `VCE = VC − VE`; ใช้ helper validation และ finite guard เดียวกับ Task 1 (ชื่อช่อง `RB, RC, RE`)

- [ ] **Step 4: รันเทสต์ทั้งหมด**

Run: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: PASS ทั้งหมด

- [ ] **Step 5: Commit**

```bash
git add dc_bias.py tests/test_dc_bias.py
git commit -m "feat: add emitter bias solver"
```

---

### Task 3: เลือกฟังก์ชันตามโหมดใน route

**Files:**
- Modify: `app.py`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `solve`, `solve_fixed`, `solve_emitter` จาก `dc_bias.py`
- Produces: `MODES = {"divider": "Voltage Divider Bias", "fixed": "Fixed Bias", "emitter": "Emitter Bias"}`, `DEFAULT_MODE = "divider"`, `UNKNOWN_MODE_ERROR` (ข้อความใน Global Constraints); `POST /calculate` รับฟิลด์ `mode` แบบไม่บังคับ

- [ ] **Step 1: เขียนเทสต์ที่ยังไม่ผ่านใน `tests/test_web.py`**

```python
class TestModeRouting(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_missing_mode_defaults_to_divider(self):
        resp = self.client.post("/calculate", data={
            "vcc": "12", "r1": "100", "r2": "22", "rc": "2.2",
            "re": "1", "beta": "100", "vbe": "0.7"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("8.052", resp.get_data(as_text=True))

    def test_unknown_mode_shows_error_not_divider_fallback(self):
        resp = self.client.post("/calculate", data={
            "mode": "bogus", "vcc": "12", "r1": "100", "r2": "22", "rc": "2.2",
            "re": "1", "beta": "100", "vbe": "0.7"})
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("โหมดวงจรไม่ถูกต้อง", html)
        self.assertNotIn("8.052", html)

    def test_fixed_post_reference(self):
        resp = self.client.post("/calculate", data={
            "mode": "fixed", "vcc": "12", "rb": "1000", "rc": "2.2",
            "beta": "100", "vbe": "0.7"})
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("9.514", html)   # VCE [V]
        self.assertIn("1.130", html)   # IC [mA]
        self.assertIn("Forward Active", html)

    def test_fixed_ignores_unrelated_fields(self):
        resp = self.client.post("/calculate", data={
            "mode": "fixed", "vcc": "12", "rb": "1000", "rc": "2.2",
            "beta": "100", "vbe": "0.7", "r1": "abc", "r2": "", "re": "-5"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("9.514", resp.get_data(as_text=True))

    def test_emitter_post_reference(self):
        resp = self.client.post("/calculate", data={
            "mode": "emitter", "vcc": "12", "rb": "1000", "rc": "2.2",
            "re": "1", "beta": "100", "vbe": "0.7"})
        html = resp.get_data(as_text=True)
        self.assertIn("8.705", html)   # VCE [V]
        self.assertIn("1.026", html)   # IC [mA]

    def test_emitter_re_change_moves_ic_down(self):
        resp = self.client.post("/calculate", data={
            "mode": "emitter", "vcc": "12", "rb": "1000", "rc": "2.2",
            "re": "2", "beta": "100", "vbe": "0.7"})
        html = resp.get_data(as_text=True)
        self.assertIn("8.033", html)
        self.assertIn("0.940", html)

    def test_fixed_zero_rb_shows_error_without_stale_result(self):
        resp = self.client.post("/calculate", data={
            "mode": "fixed", "vcc": "12", "rb": "0", "rc": "2.2",
            "beta": "100", "vbe": "0.7"})
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("RB, RC ต้องมากกว่า 0", html)
        self.assertNotIn("9.514", html)
```

- [ ] **Step 2: รันให้เห็น fail**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_web.TestModeRouting -v`
Expected: FAIL — เทสต์ fixed/emitter ได้ error เรื่องฟิลด์ขาดหรือค่าไม่ตรง, unknown mode ได้ผล Divider

- [ ] **Step 3: แก้ `app.py`**

- เพิ่ม `MODES`, `DEFAULT_MODE`, `UNKNOWN_MODE_ERROR`
- เขียน helper แปลงฟอร์มเป็น float ตามรายชื่อฟิลด์ (raise `ValueError`/`KeyError` เดิมของ route) และ helper แปลงตัวต้านทาน `* 1000`
- `POST /calculate`: `mode = request.form.get("mode", DEFAULT_MODE)`; ถ้า `mode not in MODES` → `error = UNKNOWN_MODE_ERROR`; ไม่งั้น parse เฉพาะฟิลด์ของโหมดนั้น (`divider`: vcc,r1,r2,rc,re · `fixed`: vcc,rb,rc · `emitter`: vcc,rb,rc,re) แล้วเรียกฟังก์ชันนั้น
- ส่ง `mode` และ `mode_label` เข้า template ด้วย; คง `render_template(..., error=..., result=...)` และ HTTP 200 ทุกกรณี

- [ ] **Step 4: รันเทสต์ทั้งหมด**

Run: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: PASS ทั้งหมด (เทสต์ Lab 02 เดิมต้องไม่พัง)

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_web.py
git commit -m "feat: select bias solver from form mode"
```

---

### Task 4: ฟอร์มเลือกโหมดและแสดงเฉพาะช่องที่ใช้

**Files:**
- Modify: `templates/index.html`, `static/style.css`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `MODES`, `mode`, `mode_label`, `error`, `result`, `form` จาก Task 3
- Produces: หน้าเว็บที่มี `<select name="mode">` (ฟอร์ม GET ไป `/`), ฟอร์ม `<form action="/calculate" method="post">` ที่มี `<input type="hidden" name="mode">` และช่องเฉพาะโหมด, หัวผลลัพธ์ `DC Operating Point — {{ result.mode }}`

- [ ] **Step 1: เขียนเทสต์ที่ยังไม่ผ่าน**

```python
class TestModeForm(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_default_get_shows_divider_fields(self):
        html = self.client.get("/").get_data(as_text=True)
        for field in ("vcc", "r1", "r2", "rc", "re", "beta", "vbe"):
            self.assertIn(f'name="{field}"', html)
        self.assertIn('<select name="mode"', html)

    def test_fixed_get_shows_only_fixed_fields(self):
        html = self.client.get("/?mode=fixed").get_data(as_text=True)
        self.assertIn('name="rb"', html)
        self.assertNotIn('name="r1"', html)
        self.assertNotIn('name="re"', html)

    def test_emitter_get_shows_rb_and_re(self):
        html = self.client.get("/?mode=emitter").get_data(as_text=True)
        self.assertIn('name="rb"', html)
        self.assertIn('name="re"', html)
        self.assertNotIn('name="r1"', html)

    def test_unknown_mode_get_shows_error(self):
        resp = self.client.get("/?mode=bogus")
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("โหมดวงจรไม่ถูกต้อง", html)

    def test_result_header_names_mode(self):
        html = self.client.post("/calculate", data={
            "mode": "emitter", "vcc": "12", "rb": "1000", "rc": "2.2",
            "re": "1", "beta": "100", "vbe": "0.7"}).get_data(as_text=True)
        self.assertIn("Emitter Bias", html)

    def test_error_keeps_entered_value(self):
        html = self.client.post("/calculate", data={
            "mode": "fixed", "vcc": "12", "rb": "0", "rc": "2.2",
            "beta": "100", "vbe": "0.7"}).get_data(as_text=True)
        self.assertIn('value="0"', html)
```

- [ ] **Step 2: รันให้เห็น fail**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_web.TestModeForm -v`
Expected: FAIL — ยังไม่มี select, ยังแสดงทุกช่อง, ไม่มีหัวผลระบุโหมด

- [ ] **Step 3: แก้ template และ CSS**

- เพิ่มการ์ดเลือกโหมด: `<form method="get" action="/">` + `<label for="mode">โหมดวงจร</label>` + `<select id="mode" name="mode">` ที่เลือกค่าปัจจุบัน และปุ่ม `เลือกโหมด`
- คงบรรทัด `<form action="/calculate" method="post">` ตรงตามเดิม (มีเทสต์เดิม assert ข้อความนี้)
- ในฟอร์มคำนวณ: `<input type="hidden" name="mode" value="{{ mode }}">` และ render ช่องตามโหมด
  - divider: vcc, r1, r2, rc, re, beta, vbe
  - fixed: vcc, rb, rc, beta, vbe
  - emitter: vcc, rb, rc, re, beta, vbe
- ทุกช่องมี `id` และ `<label for="...">` ตรงกัน, `value` มาจาก `form` dict (ค่าเริ่มต้นเมื่อ GET)
- error block แสดง `{{ mode_label }}: {{ error }}`
- หัวผล: `DC Operating Point — {{ result.mode }}`
- CSS: สไตล์ `select` ให้เข้าชุดกับ `input` และ `.mode-picker` เป็นการ์ดแยก

- [ ] **Step 4: รันเทสต์ทั้งหมด**

Run: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: PASS ทั้งหมด รวมเทสต์เดิม `test_get_index_returns_200_with_form`

- [ ] **Step 5: ตรวจด้วยตาในเบราว์เซอร์ (ไม่นับเป็น A1–A5)**

เปิด `http://127.0.0.1:5000/` สลับสามโหมด ดูว่าช่องเปลี่ยนจริงและค่าที่กรอกยังอยู่หลังกดคำนวณ

- [ ] **Step 6: Commit**

```bash
git add templates/index.html static/style.css tests/test_web.py app.py
git commit -m "feat: add bias mode picker and per-mode form"
```

---

### Task 5: ตรวจรับ A1–A5 ผ่านเบราว์เซอร์และบันทึกหลักฐาน

**Files:**
- Modify: `docs/validation.md`
- Create: `docs/evidence/lab03-a3.png` (หรือชื่อไฟล์ภาพที่ใช้จริง)

**Interfaces:**
- Consumes: เว็บที่รันจาก Task 1–4
- Produces: ตาราง A1–A5 ใน `docs/validation.md` พร้อมวิธีจริง/สถานะ/ค่าอ้างอิงอิสระ

- [ ] **Step 1: รีสตาร์ท Flask ด้วยโค้ดใหม่**

Run (background): `.\.venv\Scripts\python.exe -m flask --app app run`
Expected: `Running on http://127.0.0.1:5000`

- [ ] **Step 2: ตรวจ A1–A5 ผ่านเบราว์เซอร์ในแอป (OpenCode Browser)**

ค่าคงที่: VCC=12, RC=2.2, β=100, VBE=0.70 (ฟอร์มรับตัวต้านทานเป็น kΩ)

| กรณี | อินพุต | คาดหมาย | tolerance |
|---|---|---|---|
| A1 | divider: R1=100, R2=22, RE=1 | IC 1.230 mA · VCE 8.052 V | IC ≤0.01 mA, VCE ≤0.02 V |
| A2 | fixed: RB=1000 | IC 1.130 mA · VCE 9.514 V | เท่ากัน |
| A3 | emitter: RB=1000, RE=1 | IC 1.026 mA · VCE 8.705 V | เท่ากัน |
| A4 | emitter: RB=1000, RE=2 | IC 0.940 mA · VCE 8.033 V (ลดจาก A3) | เท่ากัน |
| A5 | fixed: RB=0 | ข้อความให้แก้ RB, HTTP 200, ไม่มีผลค้าง | — |

ทุกกรณี: เปิดหน้า → อ่าน snapshot → เลือกโหมด → กรอก → submit → อ่าน snapshot ใหม่ (ห้ามใช้ snapshot ก่อน submit) → เก็บ screenshot อย่างน้อย A3

- [ ] **Step 3: บันทึกผลลง `docs/validation.md`**

เพิ่มหัวข้อ `## Lab 03 — สามโหมดไบอัส` ประกอบด้วย: สมการที่ใช้ต่อโหมด, ตารางค่าอ้างอิงอิสระ A1–A5 (จาก spec §8), ตารางผลจริง (อินพุต/คาดหมาย/เห็นจริง/วิธี/สถานะ PASS|FAIL|NOT RUN), และ path ของ screenshot

- [ ] **Step 4: Commit**

```bash
git add docs/validation.md docs/evidence
git commit -m "docs: record lab 3 browser acceptance A1-A5"
```

---

### Task 6: README และ Commit SHA

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: SHA จาก `git rev-parse --short HEAD` ของ Task 1–5
- Produces: README ที่บอกสามโหมด, วิธีรัน, GitHub URL, Commit SHA, ส่วนที่ AI ช่วย/นักศึกษาตรวจ

- [ ] **Step 1: อัปเดต README**

เพิ่ม: สามโหมดและช่องอินพุตของแต่ละโหมด, ตัวอย่าง `?mode=fixed`, ผล A1 ต้องเท่า Lab 02, GitHub URL (`https://github.com/p0ngphop255021-crypto/BJT-DC-Bias-Web-App`), Commit SHA, และย่อหน้าสั้น ๆ ว่า AI เขียนส่วนไหน นักศึกษาตรวจอะไร (สมการ/หน่วย/การเลือกฟังก์ชัน/การแปลง kΩ→Ω)

- [ ] **Step 2: ตรวจ diff ก่อน commit**

Run: `git diff --staged` (หลัง `git add README.md`)
Expected: ไม่มี `.venv`, `__pycache__`, `.env`

- [ ] **Step 3: Commit เอกสาร**

```bash
git add README.md
git commit -m "docs: describe three bias modes and run steps"
```

- [ ] **Step 4: Push และรายงาน**

Run: `git push`
Expected: สำเร็จ (ถ้าไม่มี remote/สิทธิ์ ให้รายงาน URL + SHA และแจ้งว่า push ยังไม่สำเร็จ)

---

## Self-Review

- Spec G1–G6 → Task 4 (G1), Task 3 (G2), Task 1–2 (G3), Task 3 (G4), Task 3 test `missing_mode` + Task 4 default GET (G5), Task 5–6 (G6)
- Review Focus 1 → Task 3 `test_missing_mode_defaults_to_divider`; 2 → Task 3 `test_unknown_mode…` + Task 4 `test_unknown_mode_get…`; 3 → Tasks 1/2/3 validation tests; 4 → Tasks 1/2 `test_overflow_rejected` + `test_non_finite_rejected`; 5 → Task 3 `test_fixed_ignores_unrelated_fields` + Task 4 GET tests
- ชื่อ/ชนิดข้อมูลตรงกันทั้งแผน: `solve_fixed(vcc, rb, rc, beta, vbe)`, `solve_emitter(vcc, rb, rc, re, beta, vbe)`, คีย์ `mode, ib, ic, ie, vb, ve, vc, vce, region, warnings`
