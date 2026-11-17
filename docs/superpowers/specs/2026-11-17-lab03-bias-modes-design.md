# Design — Lab 03: เพิ่ม Fixed Bias และ Emitter Bias ให้เว็บจาก Lab 02

- วันที่: 2026-11-17 · ENG29 2121 · Lab 03
- สถานะ: **รออนุมัติ** (Brainstorm 2026-11-17 — เลือกทาง A: reload ฟอร์มฝั่ง server)
- อ้างอิง: ใบงาน `ENG29_2121_Lab03_BJT_Bias_Web_App.html`, `docs/design-note.md` (Lab 02)

## 1. Intent

ต่อยอดเว็บ Flask เดิม (Voltage Divider) ให้เลือกได้สามวงจรไบอัส โดยใช้ Python คำนวณจริงทุกโหมด คงผลของ Lab 02 ไว้ครบ และเพิ่มการตรวจรับผ่านเบราว์เซอร์จริง (A1–A5) ตามใบงาน

## 2. Goals

- G1: `GET /` เลือกโหมดได้ (`?mode=divider|fixed|emitter`) และฟอร์มแสดงเฉพาะช่องที่โหมดต้องใช้
- G2: `POST /calculate` เลือกฟังก์ชันตามโหมด ตรวจเฉพาะช่องที่จำเป็น แปลง kΩ→Ω จุดเดียว และคืน HTTP 200 เสมอ
- G3: Fixed และ Emitter คำนวณตามสมการในใบงานและคืน `dict` คีย์เดียวกับ Divider (`vb, ve, vc, vce, ic, ie, ib, region, warnings`)
- G4: โหมดที่ไม่รู้จัก → ข้อความผิดพลาด ไม่เดาเป็น Divider
- G5: ผล Lab 02 ไม่เปลี่ยน (A1) — ฟอร์มเดิมที่ไม่มี `mode` ยังคำนวณ Divider ได้
- G6: เอกสารประกอบ: `docs/validation.md` (A1–A5 + ค่าอ้างอิงอิสระ), README (วิธีใช้สามโหมด + GitHub URL + Commit SHA + ส่วนที่ AI ช่วย) และการรันตรวจรับผ่านเบราว์เซอร์จริง

## 3. Non-goals

AC analysis, SPICE, DC Load Line, Transient, ตัวเก็บประจุ Bypass, JavaScript toggle, unittest แบบ Playwright, การคำนวณค่าใน Cutoff/Saturation

## 4. Anti-goals

- สมการหรือตัวเลขผลลัพธ์ใน HTML/route
- หน้าเว็บล้ม (500) เมื่ออินพุตผิดหรือโหมดไม่รู้จัก
- แสดงผลรอบก่อนเป็นผลของรอบใหม่
- เปลี่ยนค่าหรือข้อความของ Divider จนผล/เทสต์ Lab 02 เสีย
- เปิดทดสอบด้วย `file://`

## 5. Constraints

- ต้องไม่แตะ signature/messages ที่ tests เดิม assert: `validate_inputs(vcc, r1, r2, rc, re, beta, vbe)`, `solve(vcc, r1, r2, rc, re, beta, vbe)` และคีย์ `vth, rth, ...`
- `dc_bias.py` ห้าม import Flask; `app.py` ห้ามมีสมการ
- ข้อความไทยที่ pin ไว้ใน AGENTS.md ต้องคงเดิมทุกตัวอักษร
- งบเวลาคาบ 180 นาที

## 6. Approaches (ตัดสินใจแล้ว)

| ทาง | ผล |
|---|---|
| **A. reload ฝั่ง server** — dropdown ส่ง `GET /?mode=…` แล้ว render ฟอร์มใหม่เฉพาะช่อง | **เลือก** — ตรงใบงาน (ไม่ต้อง JS), MCP snapshot ใหม่ชัดเจน, ตรวจฝั่ง server ได้ตรงไปตรงมา |
| B. ฟอร์มเดียวแสดงทุกช่อง + dropdown ตอน submit | ตก — ผู้ใช้กรอกช่องเกินความจำเป็น ขัดข้อ "เห็นช่องที่ใช้เท่านั้น" และปล่อยให้ค่าที่ไม่ใช้หลุดเข้า validation |
| C. JS ซ่อน/แสดงช่อง | ตก — ใบงานไม่ต้องการ JS และ snapshot ของ MCP อาจอ่านช่องที่ซ่อนสับสน |

## 7. Design

### 7.1 `dc_bias.py`

- คง `validate_inputs(...)` และ `solve(...)` ของ Divider ไว้ทั้ง signature และพฤติกรรม (ผล A1 ต้องไม่ขยับ)
- เพิ่มตัวช่วยภายใน: ตรวจ finite → ตรวจค่าบวกของตัวต้านทานโดยสร้างข้อความจากรายชื่อ เช่น `"RB, RC ต้องมากกว่า 0"` (เรียงตามลำดับรายการ จึงได้ `"R1, R2, RC, RE ต้องมากกว่า 0"` ตรงกับข้อความเดิม)
- เพิ่มฟังก์ชันใหม่:
  - `solve_fixed(vcc, rb, rc, beta, vbe) → dict`
    `IB = (VCC − VBE)/RB`, `IC = βIB`, `IE = (β+1)IB`, `VE = 0`, `VB = VBE`, `VC = VCC − IC·RC`, `VCE = VC`
  - `solve_emitter(vcc, rb, rc, re, beta, vbe) → dict`
    `IB = (VCC − VBE)/[RB + (β+1)RE]` แล้วสูตรเดียวกับ Divider
- คืน `dict` คีย์เดียวกันทุกโหมด: `vb, ve, vc, vce, ic, ie, ib, region, warnings, mode` (Divider คง `vth, rth` เพิ่มไว้)
- Region (ลำดับเดิม): `IB ≤ 0` → Cutoff; `VCE < 0.2` → Saturation; อื่น ๆ → Forward Active
  - Divider ใช้เงื่อนไข `VTH ≤ VBE` ตามเดิม (สมมูลกับ `IB ≤ 0` เมื่อตัวส่วนเป็นบวก) และคงข้อความ warning เดิม
  - Fixed/Emitter ใช้ข้อความ `"IB <= 0: ทรานซิสเตอร์ตัด (Cutoff) — แบบจำลอง Forward-Active ใช้ไม่ได้ ค่าที่แสดงเชื่อถือไม่ได้"`
  - ทุก warning ลงท้าย `ค่าที่แสดงเชื่อถือไม่ได้`
- ตรวจ `math.isfinite` ของผลลัพธ์ทุกตัวก่อนคืน (กัน overflow) เช่นเดียวกับปัจจุบัน

### 7.2 `app.py`

- `MODES = {"divider": "Voltage Divider Bias", "fixed": "Fixed Bias", "emitter": "Emitter Bias"}`; `DEFAULT_MODE = "divider"`
- `GET /`: อ่าน `?mode=`; ค่าไม่รู้จัก → render ฟอร์ม Divider พร้อม `error` (ไม่คำนวณ); ไม่ระบุ → Divider
- `POST /calculate`:
  - `mode = request.form.get("mode", "divider")` — **ไม่มีช่อง mode = Divider** (รองรับฟอร์ม/เทสต์ Lab 02); ค่าที่ส่งมาแต่ไม่รู้จัก → error
  - ฟิลด์ตามโหมด: divider `vcc,r1,r2,rc,re,beta,vbe` · fixed `vcc,rb,rc,beta,vbe` · emitter `vcc,rb,rc,re,beta,vbe`
  - แปลง kΩ→Ω (`* 1000`) ในขั้น parse ครั้งเดียว ตามด้วยเรียกฟังก์ชันของโหมด
  - ส่งเข้า template: `mode`, `mode_label`, `error`, `result`, `form` (ค่าดิบเพื่อเติมกลับ), `FIELD_LABELS`
  - error ทุกกรณี HTTP 200 และ `result=None` (ไม่มีผลรอบเก่าค้าง)
- ข้อความ error ใหม่: โหมดไม่รู้จัก และฟิลด์ขาด/ไม่ใช่ตัวเลข (ใช้ `FORM_ERROR` เดิมได้)

### 7.3 `templates/index.html` + `static/style.css`

- บล็อกเลือกโหมด: `<form method="get" action="/">` + `<select name="mode">` + ปุ่ม "เลือกโหมด" (มี `label for="mode"`)
- ฟอร์มคำนวณมี `<input type="hidden" name="mode">` และเฉพาะช่องของโหมดนั้น ทุกช่องมี `id` และ `label for=` ตรงกัน
- เติมค่าที่กรอกกลับมาทั้งหลัง error และหลังคำนวณสำเร็จ (`form` dict) เพื่อให้ลำดับ A3→A4 แก้เฉพาะ RE ได้; ค่าเริ่มต้นเมื่อ `GET`
- หัวผลลัพธ์ระบุโหมด: `DC Operating Point — {{ mode_label }}`; error ระบุโหมดที่เลือกด้วย
- ตารางผลเหมือนเดิม (`VB, VE, VC, VCE, IC, IB, IE`, warning block)
- CSS: จัดสไตล์ `select` ให้เข้าชุดกับ `input`, บล็อกโหมดแยกจากการ์ดฟอร์ม

### 7.4 Tests (คงของเดิมทั้งหมด + เพิ่ม)

- `tests/test_dc_bias.py`: ค่าอ้างอิง A2/A3/A4, validation `RB ≤ 0`, cutoff ของ Fixed (`VCC ≤ VBE`), ฟังก์ชันใหม่ไม่แตะ Divider
- `tests/test_web.py`: `GET /?mode=fixed` แสดง `rb` ไม่แสดง `r1`; POST fixed/emitter ได้ค่าตามตาราง; fixed ไม่ต้องมี `re`; โหมดไม่รู้จัก → 200 + error; `rb=0` → error ไม่มีผลค้าง
- ค่าคาดหมายในเทสต์มาจาก §8 (คำนวณอิสระ) ไม่ก๊อปจากโค้ด
- **นโยบายเทสต์:** ใบงานเขียนว่า "ไม่ต้องสร้าง unittest ใหม่" = ไม่บังคับ ไม่ใช่ห้าม; AGENTS.md บังคับ TDD จึงคงเทสต์เดิม 22 ตัวและเพิ่มเทสต์ของสองโหมดใหม่ การตรวจรับหลักยังเป็นเบราว์เซอร์ A1–A5 ตามใบงาน

## 8. ค่าอ้างอิงอิสระ (A1–A5, VCC=12 V, RC=2.2 kΩ, β=100, VBE=0.70 V)

| กรณี | โหมด/อินพุต | IB | IC (mA) | VCE (V) | หมายเหตุ |
|---|---|---|---|---|---|
| A1 | Divider R1=100k, R2=22k, RE=1k | 12.29858 µA | 1.229858 | 8.052155 | ต้องเท่าผล Lab 02 |
| A2 | Fixed RB=1 MΩ | 11.30000 µA | 1.130000 | 9.514000 | VE=0, VB=0.7 |
| A3 | Emitter RB=1 MΩ, RE=1k | 10.26340 µA | 1.026340 | 8.705450 | VE=1.036603 V |
| A4 | Emitter RB=1 MΩ, RE=2k | 9.40100 µA | 0.940100 | 8.032779 | IC ลดจาก A3 (RE ใหญ่ขึ้น) |
| A5 | Fixed RB=0 | — | — | — | ต้องได้ error ให้แก้ RB, HTTP 200 |

## 9. Verification

1. `.venv\Scripts\python.exe -m unittest discover -s tests -v` — เทสต์เดิม 22 + ใหม่ผ่านหมด
2. รัน Flask แล้วตรวจ A1–A5 ผ่านเบราว์เซอร์ในแอป (วิธีจริง: OpenCode Browser; ถ้ามี Playwright MCP ให้ใช้ก่อน) อ่าน snapshot หลัง submit ทุกครั้ง เก็บ screenshot อย่างน้อย 1 กรณี
3. บันทึกตาราง A1–A5 (อินพุต/คาดหมาย/เห็นจริง/วิธี/สถานะ) + tolerance IC ≤ 0.01 mA, VCE ≤ 0.02 V ลง `docs/validation.md`
4. อัปเดต README (สามโหมด + วิธีรัน + GitHub URL + ส่วนที่ AI ช่วย)
5. `git diff` / `git diff --staged` ก่อน commit (`feat: …`)
6. Commit SHA ต้องปรากฏใน README: commit งานหลักก่อน แล้ว commit เอกสารตามหลัง (`docs: …`) ที่ใส่ SHA ของ commit ก่อนหน้า — ไม่ amend เพราะ SHA จะเปลี่ยน

## 10. Left to the builder

- โครง HTML/CSS ที่แน่นอน (ชื่อคลาส, การจัดวาง)
- การแบ่งคลาสเทสต์/ชื่อเทสต์
- รูปแบบการบันทึก screenshot และจะเก็บไฟล์ภาพใน repo หรืออ้างถึงในเอกสาร

## 11. ความเสี่ยง

- ฟอร์มที่เติมค่าเดิมซ้ำหลัง error อาจทำให้ดูเหมือนผลค้าง → ต้อง render `result=None` เสมอเมื่อมี error
- โหมด Fixed/Emitter ไม่มี `vth` — template ห้ามอ้างคีย์นั้น
- kΩ→Ω แปลงเฉพาะตัวต้านทานของโหมดนั้น จึงต้องไม่ parse ช่องที่โหมดไม่ใช้ (เช่น `re` ใน Fixed)
