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
.venv\Scripts\python.exe -m unittest discover -s tests -v   # 49 tests, 0 failures (หลัง Lab 03)
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

### 5. เส้นทางของ RE ใน A4 (จากฟอร์มถึงสมการ)

```
<input name="re" value="2">            templates/index.html  (kΩ บนฟอร์ม)
        ↓ POST /calculate
app.py::_parse_form → float("2") * 1000 = 2000.0 Ω
        ↓ mode == "emitter"
app.py::_solve_for_mode → dc_bias.solve_emitter(vcc, rb, rc, re=2000.0, beta, vbe)
        ↓
dc_bias.py::solve_emitter
  ib  = (12 − 0.70) / (1e6 + 101 × 2000) = 9.400998e-06 A
  ic  = 100 × ib  = 0.940100 mA      (A3 ที่ RE=1k ได้ 1.026340 mA → ลดลง)
  ie  = 101 × ib
  ve  = ie × 2000 = 1.899002 V
  vce = (12 − ic × 2200) − ve = 8.032779 V
        ↓
templates/index.html แสดง IC เป็น mA (×1000) และ VCE เป็น V
```

ถ้าลืมคูณ 1000 ที่ `_parse_form` หรือฟังก์ชันไม่ได้รับ `re` ค่า IC/VCE ของ A4 จะไม่เท่า A3/ค่าอ้างอิง และเทสต์ `TestEmitterBias.test_larger_re_lowers_ic` + `TestModeRouting.test_emitter_re_change_moves_ic_down` จะจับไว้

---

# Lab 04 — CE Amplifier Simulator (2026-11-24)

## 1. Engine และแหล่งที่มาของข้อมูล

- Binary จริง: `C:\Tools\ngspice\Spice64\bin\ngspice_con.exe` · `ngspice-47` (Build 2026-08-11)
- เรียกแบบ batch: `ngspice_con -b -o run.log -r run.raw ce.cir` (args list, ไม่ใช้ `shell=True`, timeout 20 s, temp dir แยกต่อครั้ง)
- ผลลัพธ์อ่านจาก **ASCII rawfile** ที่ ngspice เขียนเอง (`.option filetype=ascii`) — ไม่มีตัวเลขฮาร์ดโค้ด
- โมเดลทรานซิสเตอร์: **2N3904** คัดลอกจาก ON Semiconductor datasheet `2N3904/D` หัวข้อ “Spice Model” (เก็บใน `spice_engine.BJT_MODEL_CARD`)
- Netlist อ้างอิง: `VCC=12 V, R1=100 kΩ, R2=22 kΩ, RC=2.2 kΩ, RE=1 kΩ, RL=10 kΩ, CIN=COUT=10 µF, Vin=10 mV peak, 1 kHz`
- ไฟล์ fixture จริงใน unit test: `tests/fixtures/ce_reference.raw/.log/.cir` บันทึกจาก netlist เดียวกันโดยมี `.op`, `.ac dec 20 10 1e+07`, `.tran 5e-06 5e-03` พร้อมกัน (OP 1 จุด, AC 121 จุด, TRAN 1008 จุด) ผลตรงกับ log ที่แนบมา
- หมายเหตุ: `build_netlist()` ของแอป emit เฉพาะ directive ของ analysis ที่เลือก — fixture ที่มีครบ 3 plot สร้างขึ้นเพื่อทดสอบ parser โดยเฉพาะ

## 2. ทำไมค่าของ ngspice จึงไม่เท่า `dc_bias.py`

`dc_bias.py` ใช้โมเดล Forward-Active แบบ β/VBE คงที่ (β=100, VBE=0.7 V) → IC = **1.229858 mA**, VCE = **8.052155 V** (คำนวณอิสระแล้วในข้อ 2 ของ Lab 03) ฝั่ง SPICE ใช้โมเดล Gummel–Poon ของ 2N3904 (BF=416.4, IS=6.734 fA, VAF=74.03 V …) → IC = **1.324 mA**, VCE = **7.7543 V** ที่ bias เดียวกัน ความต่างนี้คาดหมาย และแอปแสดงสองตารางแยกกันพร้อมคำอธิบาย

## 3. ผลที่สังเกตจากเบราว์เซอร์ (B1–B8)

วิธี: **OpenCode Browser** (กรอกฟอร์ม กดปุ่ม อ่านผลหลัง submit จริง) สำหรับ B1–B7 และ **Playwright CLI (Chrome, viewport 1280×900 และ 390×844)** สำหรับ B8 — ไม่ได้ใช้ Playwright MCP (ไม่มี MCP server ในเซสชันนี้)

| ID | สิ่งที่ตรวจ | อินพุต/วิธี | ค่าคาดหมาย | ค่าที่เห็นจริง | สถานะ |
|---|---|---|---|---|---|
| B1 | Lab 03 regression | เปิด `/` แล้วกด Calculate (Divider default) + ชุดเทสต์ 90 ตัว | IC 1.230 mA, VCE 8.052 V เหมือน Lab 03 | IC **1.230 mA**, VCE **8.052 V**, VB 1.942, VE 1.242, VC 9.294, IB 12.299 µA; 90 tests OK | PASS |
| B2 | DC จาก ngspice จริง | เลือก DC แล้วกด Run | มีค่าจาก `.op` + ชื่อโมเดล/binary/version + netlist | VB **2.0037 V**, VE **1.3329 V**, VC **9.0872 V**, VCE **7.7543 V**, IC **1.324 mA**, IB **8.887 µA**; `ngspice-47`, `2N3904`, `op: 1 points` | PASS |
| B3 | เปลี่ยน RE | RE 1 → **2 kΩ**, รัน DC ใหม่ | IC ลดลง | IC **1.324 → 0.705 mA**, IB **8.887 → 5.065 µA**, VCE **7.7543 → 9.0315 V**, VB **2.0037 → 2.0727 V** | PASS |
| B4 | Bode/AC | เลือก AC, RE กลับ 1 kΩ | แกน Hz, gain dB, phase deg, 121 จุด | `ac: 121 points` · gain **4.89 dB @ 1000 Hz** · phase **−179.87°** · label แกน `Frequency (Hz)`, `Gain (dB)`, `Phase (deg)` · tick `1e1…1e7` | PASS |
| B5 | Transient 10 mV/1 kHz | เลือก Transient (Vin=10 mV, 1 kHz ค่าเดิม) | กราฟ Vin/Vout, เห็นเฟสกลับ | `tran: 1008 points` · 2 series (`vin`, `vout`) · DC offset เฉลี่ย **3.615e−05 V** (COUT ตัด DC) · peak Vout **0.01756 V** เทียบ Vin **0.010 V** → \|Aᵥ\| ≈ **1.756** = 4.89 dB ตรงกับ AC | PASS |
| B6 | เปลี่ยน amplitude/frequency | tran: Vin 10 mV/1 kHz → **20 mV/2 kHz** | กราฟเปลี่ยนตามข้อมูลจริง | label แกน Y ตัวแรก `−0.02 → −0.04`, ขนาด SVG 34101 → 65457 อักขระ, gain ยัง ≈4.89 dB ตามคาด (ความถี่อยู่ในแบนด์) | PASS |
| B7 | Invalid input + engine unavailable | ใส่ `RE=0` แล้วรัน / ทดสอบจำลองไม่มี binary | ข้อความไทย, HTTP 200, ไม่มีกราฟหรือค่าค้าง | `ngspice: R1, R2, RC, RE, RL ต้องมากกว่า 0` · ไม่มี `.spice-results` · ไม่มี `<svg>` · ค่า `0` ยังอยู่ในช่อง · engine-unavailable ตรวจด้วย `test_missing_binary_raises_thai_error` + `test_simulate_engine_error_has_no_results` (browser sub-case: NOT RUN) | PASS (browser) / NOT RUN (engine-unavailable ใน browser) |
| B8 | Responsive desktop/mobile | Playwright `--viewport-size 1280,900` และ `390,844` แบบ full-page | อ่านได้ ไม่ตัดกราฟ | `docs/captures/lab04-desktop-viewport.png`, `docs/captures/lab04-mobile-viewport.png` · ฟอร์มเป็นคอลัมน์เดียวบน 390 px, กราฟอยู่ใน `.chart { overflow-x:auto }` | PASS |

หลักฐานภาพเพิ่มเติมจาก OpenCode Browser: `docs/captures/lab04-desktop-dc.png` (ผล DC สำเร็จ), `docs/captures/lab04-narrow-dc.png` (ภาพแคบจาก screenshot tool — **ไม่ใช่** viewport จริง ใช้ `lab04-mobile-viewport.png` เป็นหลักฐาน mobile ที่แท้จริง)

## 4. ความสอดคล้องข้าม analysis (ตรวจย้อนกลับได้)

| ปริมาณ | จาก `.ac` | จาก `.tran` | ตรงกัน |
|---|---|---|---|
| Gain ที่ 1 kHz | 4.89 dB → 10^(4.89/20) = **1.756** | peak Vout / peak Vin = 0.01756 / 0.010 = **1.756** | ✓ |
| เฟส | −179.87° | Vout มีค่าเป็นลบเมื่อ Vin เป็นบวก (กลับเฟส) | ✓ |
| DC ที่ output | — | ค่าเฉลี่ย **3.615e−05 V** ≈ 0 เพราะ COUT ตัด DC (ไม่ใช่ VC ≈ 9 V) | ✓ |

## 5. วิธีทำซ้ำ

```bash
.venv\Scripts\python.exe -m unittest discover -s tests -v   # 90 tests, OK
.venv\Scripts\python.exe -m flask --app app run --debug     # http://127.0.0.1:5000/
```

ถ้าไม่มี ngspice ให้ตั้ง `NGSPICE_BIN` ชี้ถึง `ngspice_con.exe` — หน้าเว็บจะแสดงข้อความ `ไม่พบ ngspice: ...` แทนกราฟ (HTTP 200)

## 6. สรุปข้อจำกัดที่ตรวจแล้ว

- `.save all @q1[ic] @q1[ib]` จำเป็นเพื่อให้ OP plot มี `i(@q1[ic])` — ไม่มีบรรทัดนี้ parser จะไม่พบ IC
- `ngspice.exe` บน Windows detach ทันที → ต้องใช้ `ngspice_con.exe` (หรือ env `NGSPICE_BIN`)
- rawfile ที่ถูกตัด/ว่าง → `SpiceError` พร้อมข้อความไทย ไม่มี IndexError ใน chart helper (มี unit test ครอบ)
- ทุก route คืน HTTP 200 แม้อินพุตผิดหรือ engine หาย (มี unit test ครอบ)


