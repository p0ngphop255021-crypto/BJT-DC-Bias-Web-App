# AGENTS.md — กติกาสำหรับ AI ที่จะมาพัฒนาโปรเจกต์นี้ต่อ

## คำสั่งสำคัญ

- Test: `python -m unittest discover -s tests -v` (รันจาก root ของ repo; หลังสร้าง venv ใช้ `.venv\Scripts\python.exe`)
- เว็บ: `python -m flask --app app run --debug` → `http://127.0.0.1:5000/`
- ห้ามเปิด/ทดสอบด้วย `file://`

## สถาปัตยกรรม

- `dc_bias.py` = pure engineering module — **ห้าม import flask หรือรู้จัก request/response/HTML** รับ float คืน float/dict (หน่วย SI)
- `app.py` = HTTP layer เบา ๆ — parse ฟอร์ม, แปลง kΩ→Ω (`* 1000`), เรียก `solve()`, render — **ห้ามมีสมการฝังอยู่**
- Template แสดงผลเท่านั้น — แปลงหน่วย display (mA/µA) ใน template ได้ แต่ห้ามคำนวณใหม่
- **ห้ามฮาร์ดโค้ดผลลัพธ์** ใน HTML — ทุกค่าต้องมาจาก `solve()`

## ข้อความ error/warning

ข้อความไทยใน `dc_bias.py` ถูก assert ด้วยข้อความเต็มใน tests — ห้ามแก้สำนวนโดยไม่แก้ test พร้อมกัน:

- `ค่าทุกช่องต้องเป็นจำนวนจริงที่จำกัด (finite)`
- `R1, R2, RC, RE ต้องมากกว่า 0`
- `VCC ต้องมากกว่า 0`, `beta ต้องมากกว่า 0`, `VBE ต้องมากกว่า 0`
- ข้อความ warning cutoff/saturation ลงท้าย `ค่าที่แสดงเชื่อถือไม่ได้`

## Rules

- TDD: เขียน test ให้ fail ก่อนเสมอ แล้วค่อยเขียนโค้ดให้ pass
- Route ต้องคืน HTTP 200 เสมอเมื่อ input ผิด (ห้ามปล่อย exception กลายเป็น 500)
- Region rules (ลำดับนี้): `vth <= vbe` → Cutoff; `vce < 0.2` → Saturation; อื่น ๆ → Forward Active
- Commit style: `feat:`/`fix:` prefix, สั้น อิงพฤติกรรม (เช่น `feat: add input validation for DC bias parameters`)
- ห้าม commit: `.venv/`, `__pycache__/`, `.env`, API keys (มีใน `.gitignore` แล้ว)
- ค่า expected ใน tests มาจากการคำนวณอิสระ (บันทึกใน `docs/validation.md`) — อย่าก๊อปจากโค้ดที่ทดสอบ
