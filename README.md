# BJT DC Bias Web App

เครื่องมือคำนวณ DC Operating Point ของวงจร BJT Common Emitter แบบ Voltage-Divider Bias (วิชา ENG29 2121 — Lab 02)

กรอก `VCC, R1, R2, RC, RE, β, VBE` แล้วได้ `VB, VE, VC, VCE, IC, IB, IE` พร้อมหน่วย, Operating Region และคำเตือนเมื่ออยู่นอก Forward-Active — คำนวณจริงด้วย Python/Flask ไม่ใช่ตัวเลขฮาร์ดโค้ด

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

> ต้องรันผ่าน Local Web Server เท่านั้น — ห้ามเปิดไฟล์ HTML ด้วย `file://`

## รัน automated tests

```bash
python -m unittest discover -s tests -v
```

- `tests/test_dc_bias.py` — unit tests ของสมการ/ validation (engineering math)
- `tests/test_web.py` — Flask HTTP tests (`GET /`, `POST /calculate` ทั้งเคสถูกและเคสผิด)

## โครงสร้างโปรเจกต์

```
app.py                 # Flask routes (HTTP layer เท่านั้น)
dc_bias.py             # สมการ + validation ล้วน ๆ ไม่รู้จัก Flask/HTTP
templates/index.html   # ฟอร์ม + ตารางผล (Jinja)
static/style.css       # styles responsive
tests/                 # unittest suite
docs/                  # design note, validation evidence, plan
requirements.txt       # Flask==3.1.3 (pin)
```

## หน่วย

- ตัวต้านทานกรอกเป็น **kΩ** (เช่น 100, 2.2) — แปลงเป็น Ω ใน backend
- แรงดันกรอกเป็น **V**; ผลลัพธ์: แรงดัน V, IC/IE เป็น mA, IB เป็น µA

## ข้อจำกัด

แบบจำลองคำนวณเป็น Forward-Active — เมื่อ `VTH ≤ VBE` (Cutoff) หรือ `VCE < 0.2 V` (Saturation) หน้าเว็บจะแสดงคำเตือนว่าค่าที่แสดงเชื่อถือไม่ได้
