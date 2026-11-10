"""Engineering validation for BJT Common-Emitter DC bias (Voltage-Divider).

Pure module: no Flask, no HTTP, no template knowledge.
All values are SI floats (ohms, volts) — kΩ→Ω conversion happens in the route.
"""
import math


def validate_inputs(
    vcc: float,
    r1: float,
    r2: float,
    rc: float,
    re: float,
    beta: float,
    vbe: float,
) -> None:
    """Raise ValueError with a Thai message when any value is unusable."""
    values = (vcc, r1, r2, rc, re, beta, vbe)
    if not all(math.isfinite(v) for v in values):
        raise ValueError("ค่าทุกช่องต้องเป็นจำนวนจริงที่จำกัด (finite)")
    if not (r1 > 0 and r2 > 0 and rc > 0 and re > 0):
        raise ValueError("R1, R2, RC, RE ต้องมากกว่า 0")
    if not vcc > 0:
        raise ValueError("VCC ต้องมากกว่า 0")
    if not beta > 0:
        raise ValueError("beta ต้องมากกว่า 0")
    if not vbe > 0:
        raise ValueError("VBE ต้องมากกว่า 0")


# Assumed collector-emitter saturation voltage used for the region check.
VCE_SAT = 0.2

_CUTOFF_WARNING = (
    "VTH <= VBE: ทรานซิสเตอร์ตัด (Cutoff) — แบบจำลอง Forward-Active ใช้ไม่ได้ "
    "ค่าที่แสดงเชื่อถือไม่ได้"
)
_SATURATION_WARNING = (
    "VCE ต่ำกว่า 0.2 V: ทรานซิสเตอร์อิ่มตัว (Saturation) — แบบจำลอง Forward-Active "
    "ใช้ไม่ได้ ค่าที่แสดงเชื่อถือไม่ได้"
)


def solve(
    vcc: float,
    r1: float,
    r2: float,
    rc: float,
    re: float,
    beta: float,
    vbe: float,
) -> dict:
    """Solve the DC operating point (SI units in and out).

    Uses the two-supply-less Thevenin approximation assuming forward-active
    operation, then reports whether that assumption actually holds.
    """
    validate_inputs(vcc, r1, r2, rc, re, beta, vbe)

    vth = vcc * r2 / (r1 + r2)
    rth = r1 * r2 / (r1 + r2)
    ib = (vth - vbe) / (rth + (beta + 1.0) * re)
    ic = beta * ib
    ie = (beta + 1.0) * ib
    ve = ie * re
    vb = ve + vbe
    vc = vcc - ic * rc
    vce = vc - ve

    # Huge-but-finite inputs can overflow mid-solve (e.g. r1*r2) — reject the
    # non-finite results instead of classifying/rendering them.
    results = (vth, rth, ib, ic, ie, vb, ve, vc, vce)
    if not all(math.isfinite(v) for v in results):
        raise ValueError("ค่าทุกช่องต้องเป็นจำนวนจริงที่จำกัด (finite)")

    if vth <= vbe:
        region = "Cutoff"
        warnings = [_CUTOFF_WARNING]
    elif vce < VCE_SAT:
        region = "Saturation"
        warnings = [_SATURATION_WARNING]
    else:
        region = "Forward Active"
        warnings = []

    return {
        "vth": vth,
        "rth": rth,
        "ib": ib,
        "ic": ic,
        "ie": ie,
        "vb": vb,
        "ve": ve,
        "vc": vc,
        "vce": vce,
        "region": region,
        "warnings": warnings,
    }
