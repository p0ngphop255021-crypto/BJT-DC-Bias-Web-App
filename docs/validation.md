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
.venv\Scripts\python.exe -m unittest discover -s tests -v   # 47 tests, 0 failures (หลัง Lab 03)
```

## Lab 03 — สามโหมดไบอัส (2026-11-17)

เพิ่ม Fixed Bias และ Emitter Bias แบบแหล่งจ่ายเดียว โดยผลของ Voltage Divider ต้องไม่เปลี่ยน

### 1. สมการต่อโหมด

| โหมด | กระแสฐาน |
|---|---|
| Fixed | I<sub>B</sub> = (V<sub>CC</sub> − V<sub>BE</sub>)/R<sub>B</sub> |
| Emitter | I<sub>B</sub> = (V<sub>CC</sub> − V<sub>BE</sub>)/[R<sub>B</sub> + (β+1)R<sub>E</sub>] |
| Divider | I<sub>B</sub> = (V<sub>TH</sub> − V<sub>BE</sub>)/[R<sub>TH</sub> + (β+1)R<sub>E</sub>] |

ทุกโหมด: I<sub>C</sub> = βI<sub>B</sub>, I<sub>E</sub> = (β+1)I<sub>B</sub>, V<sub>E</sub> = I<sub>E</sub>R<sub>E</sub> (Fixed: V<sub>E</sub> = 0), V<sub>B</sub> = V<sub>E</sub> + V<sub>BE</sub>, V<sub>C</sub> = V<sub>CC</sub> − I<sub>C</sub>R<sub>C</sub>, V<sub>CE</sub> = V<sub>C</sub> − V<sub>E</sub>

### 2. ค่าอ้างอิงอิสระ (คำนวณมือก่อนรัน — ไม่ import `dc_bias`)

ค่าคงที่: `VCC = 12 V`, `RC = 2.2 kΩ`, `β = 100`, `VBE = 0.70 V`

| กรณี | โหมด/อินพุต | I<sub>B</sub> | I<sub>C</sub> (mA) | V<sub>CE</sub> (V) |
|---|---|---|---|---|
| A1 | Divider R1=100k, R2=22k, RE=1k | 12.298581 µA | 1.229858 | 8.052155 |
| A2 | Fixed RB=1 MΩ | 11.300000 µA | 1.130000 | 9.514000 |
| A3 | Emitter RB=1 MΩ, RE=1k | 10.263397 µA | 1.026340 | 8.705450 |
| A4 | Emitter RB=1 MΩ, RE=2k | 9.40100 µA | 0.940100 | 8.032779 |

ทำนาย A4: RE ใหญ่ขึ้น → I<sub>B</sub> และ I<sub>C</sub> ลดลง (ตัวส่วนมี (β+1)RE) — ผลจริงเป็นไปตามทำนาย

### 3. ผลจริงจากเบราว์เซอร์

- วิธีจริง: **OpenCode Browser** (เปิดหน้า, กรอกฟอร์ม, กด Calculate, อ่านผลหลัง submit ทุกครั้ง)
- Playwright MCP: **NOT RUN** — เซสชันนี้ไม่มี MCP server `playwright` ติดตั้ง จึงใช้ OpenCode Browser ตามวิธีสำรองที่ใบงานอนุญาต
- เกณฑ์: I<sub>C</sub> คลาด ≤ 0.01 mA, V<sub>CE</sub> คลาด ≤ 0.02 V เทียบค่าอ้างอิงที่ยังไม่ปัดเศษ

| ID | วิธี | อินพุตบนฟอร์ม | ค่าคาดหมาย | ผลที่เห็น | สถานะ |
|---|---|---|---|---|---|
| A1 | OpenCode Browser | Divider · VCC=12, R1=100, R2=22, RC=2.2, RE=1, β=100, VBE=0.7 | IC 1.230 mA · VCE 8.052 V (เท่า Lab 02) | IC 1.230 mA · VCE 8.052 V · VB 1.942 · VE 1.242 · VC 9.294 · IB 12.299 µA | PASS |
| A2 | OpenCode Browser | Fixed · RB=1000 (kΩ), RC=2.2 | IC 1.130 mA · VCE 9.514 V (ไม่ต้องกรอก RE) | IC 1.130 mA · VCE 9.514 V · VB 0.700 · VE 0.000 · VC 9.514 · IB 11.300 µA | PASS |
| A3 | OpenCode Browser | Emitter · RB=1000, RE=1 | IC 1.026 mA · VCE 8.705 V | IC 1.026 mA · VCE 8.705 V · VB 1.737 · VE 1.037 · VC 9.742 · IB 10.263 µA | PASS |
| A4 | OpenCode Browser | Emitter เดิม เปลี่ยนเฉพาะ RE=2 | IC ลดจาก A3 → 0.940 mA · VCE 8.033 V | IC 0.940 mA · VCE 8.033 V · VE 1.899 · ยังเป็นโหมด Emitter | PASS |
| A5 | OpenCode Browser | Fixed · RB=0 | ข้อความให้แก้ RB, HTTP 200, ไม่มีผลค้าง | `Fixed Bias: RB, RC ต้องมากกว่า 0` · ไม่มีตารางผล · ค่า RB=0 ยังอยู่ในช่อง | PASS |

หลักฐานภาพ (A4): `docs/evidence/lab03-a4-emitter.jpg`

### 4. หมายเหตุการตรวจ

- A4 ตรวจว่าโหมดยังเป็น Emitter และ VCC/RB/RC/β/VBE เท่าเดิม ก่อนเปลี่ยนเฉพาะ RE
- A5 ตรวจว่า route คืน HTTP 200 และไม่ render ผลของรอบก่อน (ไม่มี `<section class="results">`)
- เทสต์อัตโนมัติครอบคลุมเส้นทางเดียวกัน: `TestModeRouting`, `TestModeForm`, `TestFixedBias`, `TestEmitterBias`

