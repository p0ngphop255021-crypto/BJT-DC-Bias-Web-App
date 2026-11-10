# Validation — BJT DC Bias Web App

- วันที่: 2026-11-10 · Lab 02 · ENG29 2121
- วัตถุประสงค์: พิสูจน์ว่าค่าที่เว็บแสดงมาจากการคำนวณจริงของ Python ตรงกับการคำนวณอิสระ (เกณฑ์รับ A3)

## 1. ค่าอินพุตอ้างอิง

`VCC=12 V, R1=100 kΩ, R2=22 kΩ, RC=2.2 kΩ, RE=1 kΩ, β=100, VBE=0.70 V`

## 2. การคำนวณอิสระ (ไม่ import `dc_bias`)

คำนวณด้วยสูตร Thevenin + Forward-Active ตรง ๆ ใน Python แยกต่างหาก:

```bash
python -c "VCC=12;R1=100e3;R2=22e3;RC=2.2e3;RE=1e3;b=100;VBE=0.7;VTH=VCC*R2/(R1+R2);RTH=R1*R2/(R1+R2);IB=(VTH-VBE)/(RTH+(b+1)*RE);print('VCE=%.6f IC=%.6f mA'%(VCC-b*IB*RC-(b+1)*IB*RE, b*IB*1e3))"
```

Output:

```
VCE=8.052155 IC=1.229858 mA
```

ค่าอิสระเต็ม (คำนวณทีละขั้นจากสมการเดียวกัน):

| ปริมาณ | ค่าอิสระ | ค่าจากเว็บ (ทศนิยม 3 ตำแหน่ง) | ตรงกัน |
|---|---|---|---|
| VTH | 2.163934 V | — (ค่าภายใน) | — |
| IB | 12.298581 µA | 12.299 µA | ✓ |
| IC | 1.229858 mA | 1.230 mA | ✓ |
| IE | 1.242157 mA | 1.242 mA | ✓ |
| VB | 1.942157 V | 1.942 V | ✓ |
| VE | 1.242157 V | 1.242 V | ✓ |
| VC | 9.294312 V | 9.294 V | ✓ |
| VCE | 8.052155 V | 8.052 V | ✓ |
| Region | Forward Active | Forward Active | ✓ |

## 3. ผลจากแอปจริง (ผ่าน Flask test client `POST /calculate`)

HTTP status: **200**

```
Forward Active
1.942 V
1.242 V
9.294 V
8.052 V
1.230 mA
12.299 µA
1.242 mA
```

**สรุป:** ค่าทุกช่องตรงกับการคำนวณอิสระทุกตำแหน่งทศนิยมที่แสดง (ค่า display ปัดจากค่า SI ที่คำนวณได้ตรงตามสมการใน design-note §7 ไม่มีตัวเลขฮาร์ดโค้ด)

## 4. ข้อจำกัดแบบจำลอง (ตรวจผ่าน automated tests)

แบบจำลอง Forward-Active ใช้ได้เฉพาะในขอบเขต — แอปเตือนเมื่ออยู่นอกขอบเขต:

- **Cutoff** (`VTH ≤ VBE`, ทดสอบ: VCC=5, R2=10k → VTH=0.455 V): แสดง warning `...ค่าที่แสดงเชื่อถือไม่ได้` — ยืนยันโดย `test_solve_cutoff` + `test_post_cutoff_shows_warning`
- **Saturation** (`VCE < 0.2 V`, ทดสอบ: RC=10k → VCE=−1.541 V): แสดง warning `...ค่าที่แสดงเชื่อถือไม่ได้` — ยืนยันโดย `test_solve_saturation` + `test_post_saturation_shows_warning`

## 5. หน่วย kΩ/Ω

อินพุตบนเว็บเป็น kΩ (r1=100 → 100 kΩ) แปลงเป็น Ω ใน route ก่อนเรียก `solve()` — ถ้าแปลงผิด (ลืม ×1000) VCE จะเพี้ยนไกลจาก 8.052 ทันที ซึ่ง `test_post_reference_shows_values` (ค่า 8.052 ต้องปรากฏ) จะจับไว้

## 6. วิธีทำซ้ำ

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v   # 20 tests, 0 failures
```
