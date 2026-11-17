# BJT DC Bias Web App

เครื่องมือคำนวณ DC Operating Point ของวงจร BJT Common Emitter (วิชา ENG29 2121) — **Lab 03** รองรับสามวงจรไบอัส

| โหมด | ช่องอินพุตเพิ่ม | สูตรกระแสฐาน |
|---|---|---|
| Voltage Divider Bias (Lab 02) | R1, R2, RE | `(VTH − VBE) / [RTH + (β+1)RE]` |
| Fixed Bias | RB | `(VCC − VBE) / RB` |
| Emitter Bias (แหล่งจ่ายเดียว) | RB, RE | `(VCC − VBE) / [RB + (β+1)RE]` |

ทุกโหมดได้ `VB, VE, VC, VCE, IC, IB, IE` พร้อมหน่วย, Operating Region และคำเตือนเมื่อแบบจำลอง Forward-Active ใช้ไม่ได้ — คำนวณจริงด้วย Python/Flask ไม่ใช่ตัวเลขฮาร์ดโค้ด

## ความต้องการระบบ

- Python 3.x (พัฒนาบน Python 3.15.2)
- Flask 3.1.3 (ติดตั้งผ่าน `requirements.txt`)

## ติดตั้งและรัน

```bash
# 1. clone แล้วเข้าโฟลเดอร์โปรเจกต์
python -m venv .venv

# เปิด virtual environment:
#   Windows:        .venv\Scripts\Activate.ps1
#   Linux/macOS:    source .venv/bin/activate

python -m pip install -r requirements.txt

# 2. รันเว็บเซิร์ฟเวอร์
python -m flask --app app run --debug
```

เปิดเบราว์เซอร์ที่ `http://127.0.0.1:5000/`

- `http://127.0.0.1:5000/` — Voltage Divider Bias (ค่าเริ่มต้น)
- `http://127.0.0.1:5000/?mode=fixed` — Fixed Bias
- `http://127.0.0.1:5000/?mode=emitter` — Emitter Bias

สลับโหมดได้จาก dropdown บนหน้าเว็บ (โหลดฟอร์มใหม่เฉพาะช่องที่โหมดนั้นใช้ ไม่ต้องใช้ JavaScript)

> ต้องรันผ่าน Local Web Server เท่านั้น — ห้ามเปิดไฟล์ HTML ด้วย `file://`

## รัน automated tests

```bash
python -m unittest discover -s tests -v
```

- `tests/test_dc_bias.py` — สมการและ validation ของทั้งสามโหมด
- `tests/test_web.py` — Flask HTTP tests (`GET /`, `POST /calculate` ทุกโหมด รวมโหมดผิดและอินพุตผิด)

## โครงสร้างโปรเจกต์

```
app.py                 # Flask routes (HTTP layer เท่านั้น) + เลือกฟังก์ชันตามโหมด
dc_bias.py             # สมการ + validation ล้วน ๆ ไม่รู้จัก Flask/HTTP
templates/index.html   # ตัวเลือกโหมด + ฟอร์ม/ตารางผล (Jinja)
static/style.css       # styles responsive
tests/                 # unittest suite
docs/                  # design note, validation evidence (A1–A5), plan, spec
requirements.txt       # Flask==3.1.3 (pin)
```

## หน่วย

- ตัวต้านทานกรอกเป็น **kΩ** (เช่น 100, 2.2, 1000 = 1 MΩ) — แปลงเป็น Ω ใน backend จุดเดียว
- แรงดันกรอกเป็น **V**; ผลลัพธ์: แรงดัน V, IC/IE เป็น mA, IB เป็น µA

## ข้อจำกัด

แบบจำลองคำนวณเป็น Forward-Active — เมื่อ `IB ≤ 0` (Cutoff) หรือ `VCE < 0.2 V` (Saturation) หน้าเว็บจะแสดงคำเตือนว่าค่าที่แสดงเชื่อถือไม่ได้

## การตรวจรับ Lab 03

ตาราง A1–A5 พร้อมค่าอ้างอิงอิสระ ผลจริงจากเบราว์เซอร์ และหลักฐานภาพ: [`docs/validation.md`](docs/validation.md)

- A1 (Divider ด้วยค่าเดิม) ให้ผลเท่า Lab 02: IC = 1.230 mA, VCE = 8.052 V
- A2 (Fixed RB = 1 MΩ): IC = 1.130 mA, VCE = 9.514 V
- A3 (Emitter RB = 1 MΩ, RE = 1 kΩ): IC = 1.026 mA, VCE = 8.705 V
- A4 (Emitter RE = 2 kΩ): IC = 0.940 mA (ลดลง), VCE = 8.033 V
- A5 (Fixed RB = 0): แสดง `RB, RC ต้องมากกว่า 0` ไม่มีผลค้าง และ HTTP 200

## GitHub และ Commit

- Repository: <https://github.com/p0ngphop255021-crypto/BJT-DC-Bias-Web-App>
- Commit SHA ของงาน Lab 03 (โค้ด + การตรวจรับ): `35e2199`

## ส่วนที่ AI ช่วย และส่วนที่นักศึกษาตรวจ

- AI ช่วย: ร่างฟังก์ชัน `solve_fixed` / `solve_emitter`, การเลือกฟังก์ชันตามโหมดใน `app.py`, ฟอร์ม/สไตล์, ชุดเทสต์ และเอกสาร
- นักศึกษาตรวจ: สมการและหน่วยของทั้งสามโหมด, การแปลง kΩ→Ω, การเลือกฟังก์ชันตามโหมด, เงื่อนไข validation และการแสดง warning, และทวนผล A1–A5 บนเบราว์เซอร์ด้วยค่าอ้างอิงที่คำนวณเอง
