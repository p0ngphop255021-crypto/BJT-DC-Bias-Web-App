# Design Note — Lab 02: BJT DC Bias Web App

- วันที่: 2026-11-10 · คาบ Lab 02 · ENG29 2121 · 2/2569
- ผู้พัฒนา: p0ngphop255021-crypto (ToxicGentleman <p0ngphop255021@gmail.com>)
- สถานะ: **อนุมัติแล้ว** (Brainstorm ผ่าน 2026-11-10) — เอกสารนี้เขียนตามที่อนุมัติในบทสนทนา

## 1. Intent — ทำไมต้องสร้าง

สร้าง Flask Web Application จริงตัวแรกของรายวิชา เพื่อให้เห็นกระบวนการพัฒนา Software ครบวงจร: Frontend (ฟอร์ม/ผลลัพธ์), Backend (Python คำนวณจริง ไม่ใช่ตัวเลขฮาร์ดโค้ด), Template/Static, HTTP Request/Response, Automated Tests และ GitHub — โดยชิ้นงานคือเครื่องมือคำนวณ DC Operating Point ของวงจร BJT Common Emitter แบบ Voltage-Divider Bias

## 2. Goals (เทียบเกณฑ์รับ A1–A7)

- A1: `GET /` เปิดผ่าน `http://127.0.0.1:5000/` แล้วเห็นฟอร์ม (HTTP 200)
- A2: `POST` ให้ Python Backend คำนวณจริง แสดงผลใน HTML
- A3: `VB, VE, VC, VCE, IC` (+ `IB, IE`) สอดคล้องการคำนวณอิสระภายใต้สมการเดียวกัน มีหน่วยกำกับ
- A4: ค่าผิด/ไม่ครบ → ข้อความ error ชัดเจน หน้าไม่ล้ม (R≤0, β≤0, VCC≤0, non-numeric)
- A5: นอก Active Region (cutoff/saturation) → มี Warning ไม่อ้างว่าแม่นยำ
- A6: ≥3 unit tests (engineering math) + ≥1 Flask HTTP test
- A7: clone แล้วติดตั้ง/รัน/ทดสอบตาม README ได้

## 3. Non-goals / Anti-goals

**Non-goals:** AC analysis, Bode Plot, Transient, Signal Generator, SPICE/ngspice, FET, Circuit Editor, Knob, แผงวงจร SVG (ถ้ามีเวลาว่างค่อยเพิ่ม ไม่กระทบเกณฑ์รับ)

**Anti-goals (ห้ามเกิด):** ตัวเลขผลลัพธ์ฮาร์ดโค้ดใน HTML; หน้าเว็บล้ม (500) เมื่อ input ผิด; แสดงผลนอก Forward-Active โดยไม่มี Warning; เปิดด้วย `file://` แทน Local Web Server

## 4. Constraints

- เวลาคาบ 180 นาที (ช่วง Build 75 นาที + Verify 25 นาที) — ออกแบบให้จบในขอบเขตนี้
- Python 3.15.2 + Flask, ทดสอบด้วย `python -m unittest discover -s tests -v`
- โครงไฟล์ multi-file ตามที่กำหนด; `dc_bias.py` ห้ามรู้จัก HTML/HTTP
- Commit/Push ผ่าน GitHub Desktop (repo: `p0ngphop255021-crypto/BJT-DC-Bias-Web-App`)

## 5. Approaches ที่พิจารณา

| ทางเลือก | ผล |
|---|---|
| HTML ไฟล์เดียว คำนวณใน JavaScript | **ตก** — ขัดข้อกำหนด A2 (ต้องเป็น Python Backend) และไม่เห็นโครง Web App จริง |
| FastAPI / Django | **ตก** — เอกสาร Lab กำหนด Flask โดยตรง และเพิ่มความซับซ้อนเกินเวลาคาบ |
| **Flask multi-file ตามโครง Lab** | **เลือก** — ตรงเกณฑ์รับครบทุกข้อ แยกความรับผิดชอบชัด ทดสอบได้ง่ายสุดในเวลาที่เหลือ |

## 6. การตัดสินใจที่อนุมัติแล้ว

- **โครงไฟล์:** `app.py` (routes: `GET /`, `POST /calculate`), `dc_bias.py` (validate + solve, ไม่รู้จัก HTTP), `templates/index.html` (Jinja), `static/style.css`, `tests/test_dc_bias.py`, `tests/test_web.py`, `requirements.txt`, `README.md`, `AGENTS.md`, `docs/` (เอกสารชุดนี้ + `validation.md` + `reflection.md`)
- **Flow:** Browser ส่งฟอร์ม → route รับค่า → `dc_bias.solve()` คืน dict ผลลัพธ์ + errors/warnings → render หน้าผลพร้อมหน่วย
- **Validation:** ตรวจชนิดข้อมูล (parse float ไม่ได้/หายไป → error), แล้ว `R1,R2,RC,RE > 0`, `VCC > 0`, `β > 0`, `VBE > 0` — คืนข้อความ error อ่านง่าย ไม่ raise crash ออกหน้าเว็บ
- **Warning (Forward-Active ใช้ไม่ได้):** คำนวณ `VTH`; ถ้า `VTH ≤ VBE` → แจ้ง Cutoff; ถ้า `VCE < 0.2 V` (สมมติ VCE(sat)) → แจ้ง Saturation — แสดงเป็นคำเตือน ไม่ยกเลิกผล แต่ระบุว่าค่าเหล่านี้เชื่อถือไม่ได้ภายใต้แบบจำลอง
- **หน่วยอินพุต:** ตัวต้านทานกรอกเป็น **kΩ** (เช่น 100, 22, 2.2, 1) ตามภาพตัวอย่าง Lab → แปลงเป็น Ω ใน backend; ผลลัพธ์: แรงดัน V, `IC` เป็น mA, `IB/IE` แสดงหน่วยเหมาะสม (µA/mA)
- **UI:** ฟอร์มกรอกค่า + ปุ่ม Calculate DC Bias + ตารางผล (`VB, VE, VC, VCE, IC, IB, IE`) + ข้อความ Operating Region/Error/Warning — เรียบ responsive ใช้ได้บนมือถือ
- **Tests:** `unittest`; expected values มาจากการคำนวณอิสระด้วยมือ/สเปรดชีต (บันทึกหลักฐานใน `docs/validation.md`) — อย่าก๊อปค่าจากโค้ดที่ทดสอบ; ครอบคลุม: กรณีอ้างอิงปกติ, input ผิด (≥2 แบบ), cutoff warning, saturation warning, `GET /` = 200, `POST` valid = ผลปรากฏใน HTML, `POST` invalid = error ไม่ใช่ 500

## 7. สมการและค่าอ้างอิง

```
VTH = VCC × R2/(R1+R2)       RTH = R1·R2/(R1+R2)
IB  = (VTH−VBE)/(RTH+(β+1)·RE)
IC  = β·IB                   IE = (β+1)·IB
VE  = IE·RE                  VB = VE + VBE
VC  = VCC − IC·RC            VCE = VC − VE
```

ค่าทดสอบเริ่มต้น (สำหรับตรวจผลอิสระ): `VCC=12 V, R1=100 kΩ, R2=22 kΩ, RC=2.2 kΩ, RE=1 kΩ, β=100, VBE=0.70 V`

## 8. ส่งต่อให้ Implementation Plan

งานย่อย, ลำดับการทำ, และเกณฑ์ผ่านของแต่ละงาน — กำหนดในแผนการพัฒนา (implementation plan) ถัดไป เพื่อให้ผู้เรียนตรวจและเลือกวิธี execute ก่อนเริ่มเขียนโค้ด
