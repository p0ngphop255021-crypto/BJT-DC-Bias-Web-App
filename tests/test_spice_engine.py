import math
import pathlib
import subprocess
import unittest
from unittest import mock

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


class TestDiscoveryAndRunner(unittest.TestCase):
    def test_missing_binary_raises_thai_error(self):
        with mock.patch.object(spice_engine.shutil, "which", return_value=None), \
             mock.patch.object(spice_engine, "KNOWN_WINDOWS_BINARY", "no-such-binary"):
            with self.assertRaisesRegex(spice_engine.SpiceError, "ไม่พบ ngspice"):
                spice_engine.find_ngspice({})

    def test_env_binary_is_used_when_present(self):
        with mock.patch.object(spice_engine.shutil, "which", return_value=None), \
             mock.patch.object(spice_engine.os.path, "isfile", return_value=True):
            found = spice_engine.find_ngspice({spice_engine.NGSPICE_BIN_ENV: "my-ngspice"})
            self.assertEqual(found, "my-ngspice")

    def test_timeout_becomes_spice_error(self):
        def boom(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="ngspice", timeout=1)

        with mock.patch.object(spice_engine.subprocess, "run", boom):
            with self.assertRaisesRegex(spice_engine.SpiceError, "timeout"):
                spice_engine.run_netlist("net", "ngspice_con", timeout=1)

    def test_nonzero_exit_becomes_spice_error(self):
        result = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="bad")
        with mock.patch.object(spice_engine.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(spice_engine.SpiceError, "exit code 1"):
                spice_engine.run_netlist("net", "ngspice_con")


class TestSimulate(unittest.TestCase):
    def setUp(self):
        self.raw = RAW.read_text(encoding="utf-8")
        self.patchers = [
            mock.patch.object(spice_engine, "find_ngspice", return_value="ngspice_con"),
            mock.patch.object(spice_engine, "ngspice_version", return_value="ngspice-47"),
            mock.patch.object(spice_engine, "run_netlist", return_value=("log", self.raw)),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_simulate_dc_reads_reference_fixture(self):
        result = spice_engine.simulate(PARAMS, "dc")
        self.assertEqual(result["analysis"], "dc")
        self.assertEqual(result["model"], spice_engine.BJT_MODEL_NAME)
        self.assertIn("2N3904", result["netlist"])
        values = result["values"]
        self.assertAlmostEqual(values["vce"], values["vc"] - values["ve"])
        self.assertGreater(values["ic"], 0.5e-3)
        self.assertLess(values["ic"], 5e-3)

    def test_simulate_ac_and_tran_shapes(self):
        ac = spice_engine.simulate(PARAMS, "ac")
        self.assertEqual(len(ac["freq"]), 121)
        self.assertEqual(len(ac["freq"]), len(ac["gain_db"]))
        self.assertEqual(len(ac["freq"]), len(ac["phase_deg"]))
        self.assertTrue(all(math.isfinite(g) for g in ac["gain_db"]))
        self.assertGreater(ac["gain_1k_db"], 0.0)
        self.assertLess(ac["gain_1k_db"], 20.0)
        tr = spice_engine.simulate(PARAMS, "tran")
        self.assertEqual(len(tr["time"]), len(tr["vin"]))
        self.assertEqual(len(tr["time"]), len(tr["vout"]))
        # COUT blocks DC, so the output node's DC offset is ~0, not VC.
        self.assertLess(abs(tr["vout_dc"]), 0.1)
        self.assertTrue(any(v > 0 for v in tr["vout"]))
        self.assertTrue(any(v < 0 for v in tr["vout"]))

    def test_simulate_rejects_unknown_analysis(self):
        with self.assertRaises(ValueError):
            spice_engine.simulate(PARAMS, "noise")


def _real_binary_available():
    try:
        return bool(spice_engine.find_ngspice())
    except spice_engine.SpiceError:
        return False


@unittest.skipUnless(_real_binary_available(), "ngspice not installed")
class TestRealNgspice(unittest.TestCase):
    def test_real_dc_run_returns_finite_values(self):
        result = spice_engine.simulate(PARAMS, "dc")
        self.assertTrue(all(isinstance(v, float) for v in result["values"].values()))
        self.assertGreater(result["values"]["ic"], 0)
        self.assertIn("ngspice", result["version"])


if __name__ == "__main__":
    unittest.main()
