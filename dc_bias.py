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
