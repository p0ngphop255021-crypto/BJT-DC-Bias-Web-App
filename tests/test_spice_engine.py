import unittest

import spice_engine

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


if __name__ == "__main__":
    unittest.main()
