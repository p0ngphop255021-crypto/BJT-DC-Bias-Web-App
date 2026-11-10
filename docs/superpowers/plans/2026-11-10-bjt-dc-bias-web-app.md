# BJT DC Bias Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** สร้าง Flask Web App คำนวณ DC Operating Point ของวงจร BJT Common Emitter แบบ Voltage-Divider Bias พร้อม validation, region warnings, automated tests และ README ที่รันซ้ำได้

**Architecture:** Flask multi-file — `app.py` เป็น HTTP layer เบาง, `dc_bias.py` เป็น pure engineering module (ไม่รู้จัก Flask/HTML), template Jinja แสดงผลเท่านั้น ไม่มีสมการฝังอยู่ ข้อมูลไหล: form → POST /calculate → parse + แปลง kΩ→Ω → solve() → dict → render

**Tech Stack:** Python 3.15.2, Flask 3.1.3, unittest (ไม่ใช่ pytest), Jinja2 template, HTML/CSS

**Spec:** `docs/design-note.md` (อนุมัติแล้ว) — สมการอ้างอิงอยู่ที่ Spec §7, ข้อกำหนด UI/หน่วยที่ §6

## Global Constraints

- คำสั่งรัน Tests ทุกครั้ง: `.venv\Scripts\python.exe -m unittest discover -s tests -v` (รันจาก root ของ repo)
- คำสั่งรันเว็บ: `.venv\Scripts\python.exe -m flask --app app run --debug` → `http://127.0.0.1:5000/`
- `requirements.txt` ต้องเป็น `Flask==3.1.3` (pin ตรงตัวเพื่อ A7 reproducibility)
- `dc_bias.py` ห้าม import flask หรือรับ request/response — รับ/คืน float/dict เท่านั้น
- หน่วย: `solve()` รับและคืนหน่วย SI (Ω, V, A); อินพุตบนเว็บเป็น **kΩ** แปลงเป็น Ω ใน route (`ohm = kohm * 1000`)
- ข้อความ error/warning ต้องตรงตามตัวอักษรที่กำหนดในแผนนี้ — tests assert ข้อความเหล่านี้โดยตรง (ห้ามแก้สำนวนโดยไม่แก้ test)
- ห้าม commit: `.venv/`, `__pycache__/`, `.env`, API keys (มี `.gitignore` ใน Task 3)
- Commit ปิดแต่ละ Task ด้วย `git add` + `git commit` (git CLI); ผู้เรียนตรวจ diff ทุกครั้งใน GitHub Desktop และเป็นผู้กด **Push** เมื่อจบท้ายคาบ
- เกณฑ์รับ A6: ต้องมี ≥3 unit tests (engineering math) + ≥1 Flask HTTP test — แผนนี้มีมากกว่านั้น ห้ามลบออก

## Review Focus

สิ่งที่ spec ไม่ได้บอกชัดแต่คนใช้จริงจะเจอ — แต่ละข้อมี test ปักหมุดใน Task ที่เป็นเจ้าของ:

1. **พิมพ์ `nan`, `inf`, `1e999` ในช่องตัวเลข** → float() ผ่านแต่ผลลัพธ์เป็น nan/inf แสดงบนหน้า → ต้องได้ข้อความ error — ปักหมุดด้วย `test_validate_rejects_non_finite` (Task 1) และ `test_post_nan_shows_error` (Task 4)
2. **สลับหน่วย kΩ/Ω (ป้อน 100 แต่คิดเป้าง 100 Ω)** → ผล VCE ผิดไกล — ปักหมุดด้วย `test_solve_reference_case` (Task 2, หน่วย SI) และ `test_post_reference_shows_values` (Task 5, ป้อนเป็น kΩ แล้วได้ 8.052)
3. **Cutoff/Saturation แสดงเป็น Forward Active โดยไม่ตั้งใจ** (ลำดับการตรวจ region) — ปักหมุดด้วย `test_solve_cutoff` + `test_solve_saturation` (Task 2) และ `test_post_cutoff_shows_warning` (Task 5)
4. **input ผิดทำให้ HTTP 500 (exception หลุดจาก route)** → หน้าเว็บล้ม (ขัด A4) — ปักหมุดด้วย `test_post_invalid_inputs_return_200` (Task 4) ที่ assert ทุกเคสผิดเป็น status 200
5. **ข้อความ error/warning เปลี่ยนสำนวนแล้ว test ไม่รู้** → assert ด้วยข้อความเต็มตามที่กำหนดใน Task 1/2 — ถ้าจะแก้สำนวนต้องแก้ test พร้อมกัน

---

### Task 1: Engineering Validation Module

**Files:**
- Create: `dc_bias.py`
- Create: `tests/__init__.py` (ไฟล์ว่าง)
- Test: `tests/test_dc_bias.py`

**Interfaces:**
- Produces: `validate_inputs(vcc: float, r1: float, r2: float, rc: float, re: float, beta: float, vbe: float) -> None` — raise `ValueError` พร้อมข้อความไทยด้านล่างเมื่อค่าไม่ผ่าน; return แบบเงียบ ๆ เมื่อผ่านทุกข้อ
- ลำดับการตรวจ: (1) ทุกค่าต้อง `math.isfinite` → (2) `r1, r2, rc, re > 0` → (3) `vcc > 0` → (4) `beta > 0` → (5) `vbe > 0`
- ข้อความ error ที่แน่นอน (tests assert เต็มข้อความ):
  - non-finite: `ค่าทุกช่องต้องเป็นจำนวนจริงที่จำกัด (finite)`
  - ตัวต้านทาน: `R1, R2, RC, RE ต้องมากกว่า 0`
  - VCC: `VCC ต้องมากกว่า 0`
  - beta: `beta ต้องมากกว่า 0`
  - VBE: `VBE ต้องมากกว่า 0`

- [ ] **Step 1: เขียน failing tests ใน `tests/test_dc_bias.py`**

```python
import math
import unittest

from dc_bias import validate_inputs


class TestValidateInputs(unittest.TestCase):
    def test_valid_values_pass(self):
        validate_inputs(12.0, 100_000.0, 22_000.0, 2_200.0, 1_000.0, 100.0, 0.7)

    def test_zero_resistor_rejected(self):
        with self.assertRaisesRegex(ValueError, "R1, R2, RC, RE ต้องมากกว่า 0"):
            validate_inputs(12.0, 0.0, 22_000.0, 2_200.0, 1_000.0, 100.0, 0.7)

    def test_negative_resistor_rejected(self):
        with self.assertRaisesRegex(ValueError, "R1, R2, RC, RE ต้องมากกว่า 0"):
            validate_inputs(12.0, 100_000.0, 22_000.0, -2_200.0, 1_000.0, 100.0, 0.7)

    def test_zero_vcc_rejected(self):
        with self.assertRaisesRegex(ValueError, "VCC ต้องมากกว่า 0"):
            validate_inputs(0.0, 100_000.0, 22_000.0, 2_200.0, 1_000.0, 100.0, 0.7)

    def test_zero_beta_rejected(self):
        with self.assertRaisesRegex(ValueError, "beta ต้องมากกว่า 0"):
            validate_inputs(12.0, 100_000.0, 22_000.0, 2_200.0, 1_000.0, 0.0, 0.7)

    def test_zero_vbe_rejected(self):
        with self.assertRaisesRegex(ValueError, "VBE ต้องมากกว่า 0"):
            validate_inputs(12.0, 100_000.0, 22_000.0, 2_200.0, 1_000.0, 100.0, 0.0)

    def test_validate_rejects_non_finite(self):
        with self.assertRaisesRegex(ValueError, "จำกัด"):
            validate_inputs(float("inf"), 100_000.0, 22_000.0, 2_200.0, 1_000.0, 100.0, 0.7)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: รัน test ให้ FAIL**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v` (ยังไม่มี venv → ใช้ `python -m unittest discover -s tests -v` ชั่วคราวใน Task นี้)
Expected: FAIL ด้วย `ModuleNotFoundError: No module named 'dc_bias'`

- [ ] **Step 3:  implement `validate_inputs(...)` ใน `dc_bias.py`**

ใช้ `math.isfinite` ตรวจกลุ่มแรกตามลำดับที่ Interfaces กำหนด แล้ว raise `ValueError(<ข้อความตามที่ pin ไว้>)` — ตัวฟังก์ชันไม่ import flask และไม่แตะสมการใด ๆ (สมการอยู่ใน Task 2)

- [ ] **Step 4: รัน test ให้ PASS**

Run: `python -m unittest discover -s tests -v`
Expected: 7 tests PASS, 0 failures

- [ ] **Step 5: Commit**

```bash
git add dc_bias.py tests/__init__.py tests/test_dc_bias.py
git commit -m "feat: add input validation for DC bias parameters"
```

---

### Task 2: Forward-Active Solver with Region Warnings

**Files:**
- Modify: `dc_bias.py`
- Modify: `tests/test_dc_bias.py`

**Interfaces:**
- Consumes: `validate_inputs(...)` จาก Task 1
- Produces: `solve(vcc: float, r1: float, r2: float, rc: float, re: float, beta: float, vbe: float) -> dict` — หน่วย SI ทั้งเข้าและออก; เรียก `validate_inputs` ก่อนเสมอ
- คืน dict พร้อม key แน่นอน (Task 4/5 จะใช้ชื่อเหล่านี้):
  `"vth"`, `"rth"`, `"ib"`, `"ic"`, `"ie"`, `"vb"`, `"ve"`, `"vc"`, `"vce"` (float) และ `"region"` (str), `"warnings"` (list[str])
- สมการ: ตาม Spec §7 (Thevenin + forward-active) — ห้ามเดาเอง
- กฎ region (ตรวจลำดับนี้): ถ้า `vth <= vbe` → `"Cutoff"`; ไม่งั้นถ้า `vce < 0.2` → `"Saturation"`; ไม่งั้น → `"Forward Active"`
- `warnings`: ค่าว่าง `[]` เมื่อ Forward Active มิฉะนั้น 1 ข้อความตรงตัวอักษร:
  - Cutoff: `VTH <= VBE: ทรานซิสเตอร์ตัด (Cutoff) — แบบจำลอง Forward-Active ใช้ไม่ได้ ค่าที่แสดงเชื่อถือไม่ได้`
  - Saturation: `VCE ต่ำกว่า 0.2 V: ทรานซิสเตอร์อิ่มตัว (Saturation) — แบบจำลอง Forward-Active ใช้ไม่ได้ ค่าที่แสดงเชื่อถือไม่ได้`

- [ ] **Step 1: เขียน failing tests เพิ่มใน `tests/test_dc_bias.py`**

ค่า expected มาจากการคำนวณอิสระด้วยสมการตรง ๆ (ไม่ใช่โค้ดที่กำลังจะเขียน — ผลคำนวณ: VTH=2.163934, IB=1.229858146e-05 A, VCE=8.052155 V):

```python
from dc_bias import solve


class TestSolveReferenceCase(unittest.TestCase):
    """VCC=12V, R1=100k, R2=22k, RC=2.2k, RE=1k, beta=100, VBE=0.7"""

    def setUp(self):
        self.r = solve(12.0, 100_000.0, 22_000.0, 2_200.0, 1_000.0, 100.0, 0.7)

    def test_solve_reference_case(self):
        self.assertAlmostEqual(self.r["vth"], 2.163934, places=6)
        self.assertAlmostEqual(self.r["ib"], 1.229858146e-05, places=9)
        self.assertAlmostEqual(self.r["ic"], 1.229858146e-03, places=9)
        self.assertAlmostEqual(self.r["ie"], 1.242156728e-03, places=9)
        self.assertAlmostEqual(self.r["vb"], 1.942157, places=6)
        self.assertAlmostEqual(self.r["ve"], 1.242157, places=6)
        self.assertAlmostEqual(self.r["vc"], 9.294312, places=6)
        self.assertAlmostEqual(self.r["vce"], 8.052155, places=6)

    def test_reference_region_is_forward_active(self):
        self.assertEqual(self.r["region"], "Forward Active")
        self.assertEqual(self.r["warnings"], [])

    def test_solve_rejects_invalid_values(self):
        with self.assertRaisesRegex(ValueError, "VCC ต้องมากกว่า 0"):
            solve(0.0, 100_000.0, 22_000.0, 2_200.0, 1_000.0, 100.0, 0.7)


class TestSolveRegions(unittest.TestCase):
    def test_solve_cutoff(self):
        # VCC=5V, R2=10k -> VTH=0.454545 <= VBE
        r = solve(5.0, 100_000.0, 10_000.0, 2_200.0, 1_000.0, 100.0, 0.7)
        self.assertLess(r["ib"], 0.0)
        self.assertEqual(r["region"], "Cutoff")
        self.assertEqual(len(r["warnings"]), 1)
        self.assertIn("เชื่อถือไม่ได้", r["warnings"][0])

    def test_solve_saturation(self):
        # reference case with RC=10k -> VCE=-1.540738 < 0.2
        r = solve(12.0, 100_000.0, 22_000.0, 10_000.0, 1_000.0, 100.0, 0.7)
        self.assertLess(r["vce"], 0.2)
        self.assertEqual(r["region"], "Saturation")
        self.assertEqual(len(r["warnings"]), 1)
        self.assertIn("เชื่อถือไม่ได้", r["warnings"][0])
```

- [ ] **Step 2: รัน test ให้ FAIL**

Run: `python -m unittest discover -s tests -v`
Expected: FAIL ด้วย `ImportError: cannot import name 'solve'`

- [ ] **Step 3: implement `solve(...)` ใน `dc_bias.py`**

เรียก `validate_inputs` ก่อน แล้วคำนวณตามสมการ Spec §7 (ผลลัพธ์ float หน่วย SI) ตามด้วยกฎ region + warnings ตาม Interfaces — ค่าคงที่ `0.2` (VCE sat) ใส่เป็นชื่อ constant เช่น `VCE_SAT = 0.2`

- [ ] **Step 4: รัน test ให้ PASS**

Run: `python -m unittest discover -s tests -v`
Expected: ทุก test PASS (7 เดิม + 6 ใหม่ = 13), 0 failures

- [ ] **Step 5: Commit**

```bash
git add dc_bias.py tests/test_dc_bias.py
git commit -m "feat: add forward-active DC bias solver with region warnings"
```

---

### Task 3: Flask Scaffold + GET /

**Files:**
- Create: `app.py`, `templates/index.html`, `requirements.txt`, `.gitignore`, `tests/test_web.py`
- Modify: (none — สร้างใหม่ทั้งหมด)

**Interfaces:**
- Produces: object `app` (Flask instance) ใน `app.py` — tests จะ import จาก `app`
- Route: `GET /` → render `templates/index.html` → HTTP 200
- Template ต้องมี: `<form action="/calculate" method="post">` พร้อม input fields ชื่อ `vcc, r1, r2, rc, re, beta, vbe` (label ระบุหน่วย: V, kΩ, kΩ, kΩ, kΩ, -, V ตามลำดับ) และ `<button>Calculate DC Bias</button>`
- `requirements.txt`: `Flask==3.1.3`
- `.gitignore`: `.venv/`, `__pycache__/`, `*.pyc`, `.env`

- [ ] **Step 1: เขียน failing test ใน `tests/test_web.py`**

```python
import unittest

from app import app


class TestIndex(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_get_index_returns_200_with_form(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('<form action="/calculate" method="post">', html)
        self.assertIn("Calculate DC Bias", html)
        for field in ("vcc", "r1", "r2", "rc", "re", "beta", "vbe"):
            self.assertIn(f'name="{field}"', html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: รัน test ให้ FAIL**

Run: `python -m unittest discover -s tests -v`
Expected: FAIL ด้วย `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: ติดตั้ง environment + เขียน scaffold**

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt   # (สร้าง requirements.txt ก่อน: Flask==3.1.3)
```

แล้วสร้าง `app.py` (Flask(__name__), route GET / render index.html), `templates/index.html` (ฟอร์มตาม Interfaces — ยังไม่ต้องมีส่วนผลลัพธ์), `.gitignore`

- [ ] **Step 4: รัน test ทั้งชุดให้ PASS ด้วย venv**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: ทุก test PASS (13 เดิม + 1 ใหม่), 0 failures

- [ ] **Step 5: Commit**

```bash
git add app.py templates/index.html requirements.txt .gitignore tests/test_web.py
git commit -m "feat: add Flask scaffold with input form"
```

---

### Task 4: POST /calculate — Input Parsing and Error Display

**Files:**
- Modify: `app.py` (เพิ่ม route), `templates/index.html` (เพิ่ม error banner), `tests/test_web.py`

**Interfaces:**
- Consumes: `solve(...)` จาก Task 2 (รับหน่วย Ω)
- Produces: route `POST /calculate`:
  1. อ่านทุก field จาก `request.form`; แปลง `r1, r2, rc, re` จาก kΩ→Ω ด้วย `* 1000`; `vcc, beta, vbe` คงหน่วยเดิม
  2. parse ไม่ได้ / field หายไป → error = `กรอกข้อมูลให้ครบและเป็นตัวเลข`
  3. `solve()` raise `ValueError` → error = `str(err)` (ข้อความไทยจาก Task 1/2)
  4. render `index.html` โดยส่ง `error` (และ `result=None`) — **HTTP 200 เสมอ** ไม่มี exception หลุด
- Template: แสดง `<div class="error">{{ error }}</div>` เมื่อ error ไม่ใช่ None

- [ ] **Step 1: เขียน failing tests เพิ่มใน `tests/test_web.py`**

```python
class TestPostValidation(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.valid = {
            "vcc": "12", "r1": "100", "r2": "22", "rc": "2.2",
            "re": "1", "beta": "100", "vbe": "0.7",
        }

    def post(self, overrides=None):
        data = dict(self.valid)
        if overrides:
            data.update(overrides)
        return self.client.post("/calculate", data=data)

    def test_post_non_numeric_shows_error(self):
        resp = self.post({"r1": "abc"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("กรอกข้อมูลให้ครบและเป็นตัวเลข", resp.get_data(as_text=True))

    def test_post_zero_resistor_shows_error(self):
        resp = self.post({"r1": "0"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("R1, R2, RC, RE ต้องมากกว่า 0", resp.get_data(as_text=True))

    def test_post_missing_field_shows_error(self):
        resp = self.client.post("/calculate", data={"vcc": "12"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("กรอกข้อมูลให้ครบและเป็นตัวเลข", resp.get_data(as_text=True))

    def test_post_nan_shows_error(self):
        resp = self.post({"vcc": "nan"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("จำกัด", resp.get_data(as_text=True))
```

- [ ] **Step 2: รัน test ให้ FAIL**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: 4 tests ใหม่ FAIL ด้วย 404 (route ยังไม่มี)

- [ ] **Step 3: implement route `POST /calculate` ใน `app.py` + error banner ใน template**

ตามลำดับใน Interfaces — ครอบด้วย try/except (ValueError, KeyError) ที่เปลี่ยนเป็นข้อความ error แล้ว render 200

- [ ] **Step 4: รัน test ทั้งชุดให้ PASS**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: ทุก test PASS (14 เดิม + 4 ใหม่), 0 failures

- [ ] **Step 5: Commit**

```bash
git add app.py templates/index.html tests/test_web.py
git commit -m "feat: handle POST calculation with input errors"
```

---

### Task 5: Results Table with Units and Region Warnings

**Files:**
- Modify: `app.py` (ส่ง `result` เข้า template), `templates/index.html` (ตารางผล + region + warnings), `tests/test_web.py`

**Interfaces:**
- Consumes: `solve()` dict (keys ตาม Task 2)
- Produces: template ส่วนผลลัพธ์ — ตารางแสดง: `VB, VE, VC, VCE` เป็น V ด้วย format `%.3f`; `IC` = `result.ic * 1000` (mA); `IB` = `result.ib * 1000000` (µA); `IE` = `result.ie * 1000` (mA) — ทุกช่อง format `%.3f`; แสดง `region` เป็นหัวข้อ และแสดงรายการ `warnings` ทุกข้อเมื่อมี
- รูปแบบ: ปุ่ม Calculate ส่ง POST แล้วหน้าเดิมแสดงผลใต้ฟอร์ม (ไม่ redirect)

- [ ] **Step 1: เขียน failing tests เพิ่มใน `tests/test_web.py`**

```python
class TestPostResults(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.valid = {
            "vcc": "12", "r1": "100", "r2": "22", "rc": "2.2",
            "re": "1", "beta": "100", "vbe": "0.7",
        }

    def test_post_reference_shows_values(self):
        resp = self.client.post("/calculate", data=self.valid)
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("8.052", html)    # VCE [V]
        self.assertIn("12.299", html)   # IB [uA]
        self.assertIn("1.230", html)    # IC [mA]
        self.assertIn("Forward Active", html)

    def test_post_saturation_shows_warning(self):
        data = dict(self.valid, rc="10")
        resp = self.client.post("/calculate", data=data)
        html = resp.get_data(as_text=True)
        self.assertIn("Saturation", html)
        self.assertIn("เชื่อถือไม่ได้", html)
        self.assertNotIn("Forward Active", html)

    def test_post_cutoff_shows_warning(self):
        data = dict(self.valid, vcc="5", r2="10")
        resp = self.client.post("/calculate", data=data)
        html = resp.get_data(as_text=True)
        self.assertIn("Cutoff", html)
        self.assertIn("เชื่อถือไม่ได้", html)
        self.assertNotIn("Forward Active", html)
```

- [ ] **Step 2: รัน test ให้ FAIL**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: 3 tests ใหม่ FAIL (ค่า "8.052" ยังไม่ถูก render)

- [ ] **Step 3: implement ส่วนผลลัพธ์ใน `app.py` + `templates/index.html`**

ส่ง `result=result` จาก route; ตาราง + region + warnings ใน template ตาม Interfaces (แปลงหน่วยใน template เท่านั้น — ห้ามแก้ solve())

- [ ] **Step 4: รัน test ทั้งชุดให้ PASS**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: ทุก test PASS (18 เดิม + 3 ใหม่ = 21), 0 failures

- [ ] **Step 5: Commit**

```bash
git add app.py templates/index.html tests/test_web.py
git commit -m "feat: display DC bias results with units and region warnings"
```

---

### Task 6: UI Styling, Docs, Validation Evidence, Final Verification

**Files:**
- Create: `static/style.css`, `README.md`, `AGENTS.md`, `docs/validation.md`
- Modify: `templates/index.html` (ลิงก์ stylesheet)

**Interfaces:**
- Consumes: ทุกอย่างจาก Task 1–5
- Produces: CSS ตอบสนองต่อหน้าจอเล็ก (ฟอร์ม+ผลอ่านง่ายบนมือถือ), README ที่คน clone ใหม่ทำตามได้ (A7), validation.md มีหลักฐานเทียบผลอิสระ, AGENTS.md บอกกติกาโค้ดให้ AI รุ่นถัดไป

- [ ] **Step 1: เขียน `static/style.css` + ลิงก์ใน template**

จัด layout คอลัมน์เดียวบนจอเล็ก / สองคอลัมน์บนจอใหญ่, ปุ่ม Calculate เด่น, error = กรอบแดง, warning = กรอบเหลือง, ตารางผลอ่านง่าย — ตรวจด้วยการเปิดเว็บจริง (Step 5)

- [ ] **Step 2: สร้าง `docs/validation.md` — หลักฐานเทียบผลอิสระ**

คำนวณค่าอ้างอิงด้วยคำสั่ง python แยกต่างหาก (**ห้าม import dc_bias**) แล้วรันแอปจริงเทียบ:

```bash
python -c "VCC=12;R1=100e3;R2=22e3;RC=2.2e3;RE=1e3;b=100;VBE=0.7;VTH=VCC*R2/(R1+R2);RTH=R1*R2/(R1+R2);IB=(VTH-VBE)/(RTH+(b+1)*RE);print('VCE=%.6f IC=%.6f mA'%(VCC-b*IB*RC-(b+1)*IB*RE, b*IB*1e3))"
```

Expected output: `VCE=8.052155 IC=1.229858 mA` — บันทึกลง validation.md พร้อมตารางเทียบกับผลจากเว็บ (รันผ่าน test client หรือ browser) ระบุว่าตรงกันทุกตำแหน่งทศนิยม, ปิดท้ายด้วยหมายเหตุข้อจำกัดแบบจำลอง (cutoff/saturation warning ทำงาน)

- [ ] **Step 3: เขียน `README.md` ตามเกณฑ์ A7**

เนื้อหา: คำอธิบายโปรเจกต์, ความต้องการระบบ (Python 3.x), ขั้นตอนติดตั้ง/รัน/test:

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1   |   Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m flask --app app run --debug
# เปิด http://127.0.0.1:5000/
python -m unittest discover -s tests -v
```

- [ ] **Step 4: เขียน `AGENTS.md`**

กติกาสั้น ๆ: คำสั่งรัน test, `dc_bias.py` ห้ามรู้จัก HTTP, ห้ามฮาร์ดโค้ดผลลัพธ์, ข้อความ error ตรงตาม test, commit style

- [ ] **Step 5: Verification ครบวงจร**

```bash
.venv\Scripts\python.exe -m unittest discover -s tests -v      # Expected: 21 tests, 0 failures
.venv\Scripts\python.exe -m flask --app app run --debug        # เปิด http://127.0.0.1:5000/
```

เปิดเบราว์เซอร์จริง: กรอกค่าอ้างอิง → เห็นตารางผล + Forward Active; กรอก r1=0 → เห็น error ไม่ล้ม; กรอก rc=10 → เห็น Saturation warning — ถ่าย screenshot เก็บเป็นหลักฐานส่งมอบ

- [ ] **Step 6: Commit**

```bash
git add static/style.css templates/index.html README.md AGENTS.md docs/validation.md
git commit -m "feat: add styling, README, and validation evidence"
```

---

## หลังจบแผน (อยู่นอกขอบเขต execution)

- ผู้เรียนตรวจ diff + กด **Push ผ่าน GitHub Desktop** แล้วส่ง Repository URL + Commit SHA
- เขียน `docs/reflection.md` ด้วยตนเอง (คำถามรายบุคคลในเอกสาร Lab)
- บันทึก Test Log + Screenshot หน้าจอคำนวณสำเร็จตามข้อส่งมอบ
