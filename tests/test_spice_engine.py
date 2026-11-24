import pathlib
import unittest

import spice_engine

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
RAW = FIXTURES / "ce_reference.raw"

PARAMS = dict(
    vcc=12.0,
    r1=100e3,
    r2=22e3,
    rc=2.2e3,
    re=1e3,
    rl=10e3,
    cin=10e-6,
    cout=10e-6,
    amp=0.01,
    freq=1e3,
)


class TestBuildNetlist(unittest.TestCase):
    def test_netlist_has_circuit_elements_in_si_units(self):
        n = spice_engine.build_netlist(PARAMS, "dc")
        self.assertIn("R1 vcc b 100000", n)
        self.assertIn("RC vcc c 2200", n)
        self.assertIn("CIN in b 1e-05", n)
        self.assertIn("Q1 c b e 2N3904", n)
        self.assertIn("VIN in 0 DC 0 AC 1 SIN(0 0.01 1000)", n)

    def test_netlist_directive_per_analysis(self):
        self.assertIn(".op", spice_engine.build_netlist(PARAMS, "dc"))
        self.assertIn(".ac dec 20 10 1e+07", spice_engine.build_netlist(PARAMS, "ac"))
        self.assertIn(".tran", spice_engine.build_netlist(PARAMS, "tran"))

    def test_netlist_saves_transistor_currents_and_ascii_raw(self):
        n = spice_engine.build_netlist(PARAMS, "dc")
        self.assertIn(".save all @q1[ic] @q1[ib]", n)
        self.assertIn(".option filetype=ascii", n)
        self.assertIn(spice_engine.BJT_MODEL_CARD, n)

    def test_unknown_analysis_rejected(self):
        with self.assertRaises(ValueError):
            spice_engine.build_netlist(PARAMS, "noise")


class TestValidateParams(unittest.TestCase):
    def test_accepts_reference_params(self):
        spice_engine.validate_params(PARAMS)

    def test_rejects_non_positive_and_non_finite(self):
        for bad in ({"vcc": 0}, {"re": -1}, {"freq": 0}, {"r1": float("inf")}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                spice_engine.validate_params({**PARAMS, **bad})

    def test_finite_message_is_shared_wording(self):
        with self.assertRaisesRegex(ValueError, "ค่าทุกช่องต้องเป็นจำนวนจริงที่จำกัด"):
            spice_engine.validate_params({**PARAMS, "vcc": float("nan")})

    def test_rejects_negative_amplitude(self):
        with self.assertRaisesRegex(ValueError, "amplitude ต้องไม่ติดลบ"):
            spice_engine.validate_params({**PARAMS, "amp": -0.1})


class TestTranStop(unittest.TestCase):
    def test_tran_stop_scales_with_frequency_and_is_capped(self):
        step, stop = spice_engine.tran_stop(1e3)
        self.assertAlmostEqual(step, 5e-6)
        self.assertAlmostEqual(stop, 5e-3)
        self.assertLessEqual(spice_engine.tran_stop(1e6)[1], 50e-3)


class TestParseRawAscii(unittest.TestCase):
    def test_reference_fixture_parses_all_three_plots(self):
        plots = spice_engine.parse_raw_ascii(RAW.read_text(encoding="utf-8"))
        self.assertEqual(set(plots), {"op", "ac", "tran"})
        self.assertEqual(len(plots["ac"]["points"]), 121)
        self.assertIn("v(out)", plots["ac"]["variables"])

    def test_op_voltage_and_transistor_current_available(self):
        plots = spice_engine.parse_raw_ascii(RAW.read_text(encoding="utf-8"))
        vb = spice_engine.raw_value(plots["op"], "v(b)")
        ic = spice_engine.raw_value(plots["op"], "i(@q1[ic])")
        self.assertGreater(vb.real, 1.0)
        self.assertLess(vb.real, 3.0)
        self.assertGreater(ic.real, 0.5e-3)
        self.assertLess(ic.real, 5e-3)

    def test_ac_values_are_complex_with_frequency(self):
        plots = spice_engine.parse_raw_ascii(RAW.read_text(encoding="utf-8"))
        f = spice_engine.raw_value(plots["ac"], "frequency", 0)
        vout = spice_engine.raw_value(plots["ac"], "v(out)", 0)
        self.assertAlmostEqual(f.real, 10.0)
        self.assertTrue(hasattr(vout, "real") and hasattr(vout, "imag"))

    def test_truncated_or_empty_raw_raises(self):
        for text in ("", "Title: x\nPlotname: AC Analysis\n"):
            with self.subTest(text=text[:20]), self.assertRaises(spice_engine.SpiceError):
                spice_engine.parse_raw_ascii(text)


if __name__ == "__main__":
    unittest.main()
