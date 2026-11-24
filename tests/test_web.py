import unittest
from contextlib import contextmanager
from unittest import mock

from flask import template_rendered

import app as app_module
from app import app


SIM_FORM = {
    "analysis": "dc",
    "vcc": "12", "r1": "100", "r2": "22", "rc": "2.2",
    "re": "1", "rl": "10", "cin": "10", "cout": "10",
    "amp": "10", "freq": "1000", "beta": "100", "vbe": "0.7",
}


@contextmanager
def captured_templates():
    recorded = []

    def record(sender, template, context, **extra):
        recorded.append((template, context))

    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)


class TestIndex(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_get_index_returns_200_with_form(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('<form action="/calculate" method="post">', html)
        self.assertIn("Calculate DC Bias", html)
        for field in ("vcc", "r1", "r2", "rc", "re", "beta", "vbe"):
            self.assertIn(f'name="{field}"', html)


class TestPostValidation(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.valid = {
            "vcc": "12", "r1": "100", "r2": "22", "rc": "2.2",
            "re": "1", "beta": "100", "vbe": "0.7",
        }

    def post(self, overrides=None):
        data = dict(self.valid)
        if overrides:
            data.update(overrides)
        return self.client.post("/calculate", data=data)

    def test_post_non_numeric_shows_error(self):
        resp = self.post({"r1": "abc"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("กรอกข้อมูลให้ครบและเป็นตัวเลข", resp.get_data(as_text=True))

    def test_post_zero_resistor_shows_error(self):
        resp = self.post({"r1": "0"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("R1, R2, RC, RE ต้องมากกว่า 0", resp.get_data(as_text=True))

    def test_post_missing_field_shows_error(self):
        resp = self.client.post("/calculate", data={"vcc": "12"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("กรอกข้อมูลให้ครบและเป็นตัวเลข", resp.get_data(as_text=True))

    def test_post_nan_shows_error(self):
        resp = self.post({"vcc": "nan"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("จำกัด", resp.get_data(as_text=True))

    def test_post_overflow_shows_error(self):
        # Finite input that overflows mid-solve must error, never render nan.
        resp = self.post({"r1": "1e305", "r2": "1e305"})
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("จำกัด", html)
        self.assertNotIn("nan V", html)


class TestPostResults(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.valid = {
            "vcc": "12", "r1": "100", "r2": "22", "rc": "2.2",
            "re": "1", "beta": "100", "vbe": "0.7",
        }

    def test_post_reference_shows_values(self):
        resp = self.client.post("/calculate", data=self.valid)
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("8.052", html)    # VCE [V]
        self.assertIn("12.299", html)   # IB [uA]
        self.assertIn("1.230", html)    # IC [mA]
        self.assertIn("Forward Active", html)

    def test_post_saturation_shows_warning(self):
        data = dict(self.valid, rc="10")
        resp = self.client.post("/calculate", data=data)
        html = resp.get_data(as_text=True)
        self.assertIn("Saturation", html)
        self.assertIn("เชื่อถือไม่ได้", html)
        self.assertNotIn("Forward Active", html)

    def test_post_cutoff_shows_warning(self):
        data = dict(self.valid, vcc="5", r2="10")
        resp = self.client.post("/calculate", data=data)
        html = resp.get_data(as_text=True)
        self.assertIn("Cutoff", html)
        self.assertIn("เชื่อถือไม่ได้", html)
        self.assertNotIn("Forward Active", html)


class TestModeRouting(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_missing_mode_defaults_to_divider(self):
        resp = self.client.post("/calculate", data={
            "vcc": "12", "r1": "100", "r2": "22", "rc": "2.2",
            "re": "1", "beta": "100", "vbe": "0.7"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("8.052", resp.get_data(as_text=True))

    def test_unknown_mode_shows_error_not_divider_fallback(self):
        resp = self.client.post("/calculate", data={
            "mode": "bogus", "vcc": "12", "r1": "100", "r2": "22", "rc": "2.2",
            "re": "1", "beta": "100", "vbe": "0.7"})
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("โหมดวงจรไม่ถูกต้อง", html)
        self.assertNotIn("8.052", html)

    def test_fixed_post_reference(self):
        resp = self.client.post("/calculate", data={
            "mode": "fixed", "vcc": "12", "rb": "1000", "rc": "2.2",
            "beta": "100", "vbe": "0.7"})
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("9.514", html)   # VCE [V]
        self.assertIn("1.130", html)   # IC [mA]
        self.assertIn("Forward Active", html)

    def test_fixed_ignores_unrelated_fields(self):
        resp = self.client.post("/calculate", data={
            "mode": "fixed", "vcc": "12", "rb": "1000", "rc": "2.2",
            "beta": "100", "vbe": "0.7", "r1": "abc", "r2": "", "re": "-5"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("9.514", resp.get_data(as_text=True))

    def test_emitter_post_reference(self):
        resp = self.client.post("/calculate", data={
            "mode": "emitter", "vcc": "12", "rb": "1000", "rc": "2.2",
            "re": "1", "beta": "100", "vbe": "0.7"})
        html = resp.get_data(as_text=True)
        self.assertIn("8.705", html)   # VCE [V]
        self.assertIn("1.026", html)   # IC [mA]

    def test_emitter_re_change_moves_ic_down(self):
        resp = self.client.post("/calculate", data={
            "mode": "emitter", "vcc": "12", "rb": "1000", "rc": "2.2",
            "re": "2", "beta": "100", "vbe": "0.7"})
        html = resp.get_data(as_text=True)
        self.assertIn("8.033", html)
        self.assertIn("0.940", html)

    def test_fixed_zero_rb_shows_error_without_stale_result(self):
        resp = self.client.post("/calculate", data={
            "mode": "fixed", "vcc": "12", "rb": "0", "rc": "2.2",
            "beta": "100", "vbe": "0.7"})
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("RB, RC ต้องมากกว่า 0", html)
        self.assertNotIn("9.514", html)


class TestModeForm(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_default_get_shows_divider_fields(self):
        html = self.client.get("/").get_data(as_text=True)
        for field in ("vcc", "r1", "r2", "rc", "re", "beta", "vbe"):
            self.assertIn(f'name="{field}"', html)
        self.assertIn('<select name="mode"', html)

    def test_fixed_get_shows_only_fixed_fields(self):
        html = self.client.get("/?mode=fixed").get_data(as_text=True)
        self.assertIn('name="rb"', html)
        self.assertNotIn('name="r1"', html)
        self.assertNotIn('name="re"', html)

    def test_emitter_get_shows_rb_and_re(self):
        html = self.client.get("/?mode=emitter").get_data(as_text=True)
        self.assertIn('name="rb"', html)
        self.assertIn('name="re"', html)
        self.assertNotIn('name="r1"', html)

    def test_unknown_mode_get_shows_error(self):
        resp = self.client.get("/?mode=bogus")
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("โหมดวงจรไม่ถูกต้อง", html)

    def test_result_header_names_mode(self):
        html = self.client.post("/calculate", data={
            "mode": "emitter", "vcc": "12", "rb": "1000", "rc": "2.2",
            "re": "1", "beta": "100", "vbe": "0.7"}).get_data(as_text=True)
        self.assertIn("Emitter Bias", html)

    def test_unknown_mode_error_not_labelled_with_fallback_mode(self):
        html = self.client.get("/?mode=bogus").get_data(as_text=True)
        self.assertIn("โหมดวงจรไม่ถูกต้อง", html)
        self.assertNotIn("Voltage Divider Bias: โหมดวงจรไม่ถูกต้อง", html)
        self.assertNotIn("Voltage Divider Bias (Common Emitter)", html)

    def test_unknown_mode_post_error_not_labelled_with_fallback_mode(self):
        html = self.client.post(
            "/calculate", data={"mode": "bogus", "vcc": "12"}
        ).get_data(as_text=True)
        self.assertIn("โหมดวงจรไม่ถูกต้อง", html)
        self.assertNotIn("Voltage Divider Bias: โหมดวงจรไม่ถูกต้อง", html)

    def test_error_keeps_entered_value(self):
        html = self.client.post("/calculate", data={
            "mode": "fixed", "vcc": "12", "rb": "0", "rc": "2.2",
            "beta": "100", "vbe": "0.7"}).get_data(as_text=True)
        self.assertIn('value="0"', html)


class TestSimulateRoute(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def post(self, overrides=None):
        data = dict(SIM_FORM)
        if overrides:
            data.update(overrides)
        return self.client.post("/simulate", data=data)

    def test_simulate_rejects_zero_re_with_200(self):
        with captured_templates() as templates:
            resp = self.post({"re": "0"})
        context = templates[-1][1]
        self.assertEqual(resp.status_code, 200)
        self.assertIn("มากกว่า 0", context["sim_error"])
        self.assertIsNone(context["simulation"])

    def test_simulate_rejects_missing_or_text_field(self):
        data = {k: v for k, v in SIM_FORM.items() if k != "rl"}
        with captured_templates() as templates:
            resp = self.client.post("/simulate", data=data)
        context = templates[-1][1]
        self.assertEqual(resp.status_code, 200)
        self.assertIn("กรอกข้อมูลให้ครบ", context["sim_error"])
        self.assertIsNone(context["simulation"])

    def test_simulate_rejects_non_finite_input(self):
        with captured_templates() as templates:
            resp = self.post({"vcc": "1e309"})
        context = templates[-1][1]
        self.assertEqual(resp.status_code, 200)
        self.assertIn("finite", context["sim_error"])

    def test_simulate_engine_error_has_no_results(self):
        def boom(*args, **kwargs):
            raise app_module.spice_engine.SpiceError("ไม่พบ ngspice: test")

        with mock.patch.object(app_module.spice_engine, "simulate", boom), \
             captured_templates() as templates:
            resp = self.post()
        context = templates[-1][1]
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(context["sim_error"], "ไม่พบ ngspice: test")
        self.assertIsNone(context["simulation"])
        self.assertIsNone(context["analytical"])

    def test_simulate_success_passes_si_params_and_analytical(self):
        fake = {
            "analysis": "dc", "model": "2N3904", "binary": "ngspice_con",
            "version": "ngspice-47", "netlist": "* net", "raw_summary": "op: 1 points",
            "values": {"vb": 2.0, "ve": 1.33, "vc": 9.09, "vce": 7.76,
                       "ic": 0.00133, "ib": 0.00001},
        }
        with mock.patch.object(app_module.spice_engine, "simulate", return_value=fake) as sim, \
             captured_templates() as templates:
            resp = self.post()
        context = templates[-1][1]
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(context["sim_error"])
        self.assertEqual(context["simulation"], fake)
        params = sim.call_args.args[0]
        self.assertEqual(params["r1"], 100000.0)
        self.assertEqual(params["cin"], 10e-6)
        self.assertEqual(params["amp"], 0.01)
        self.assertIn("ic", context["analytical"])

    def test_simulate_analysis_is_forwarded(self):
        with mock.patch.object(app_module.spice_engine, "simulate", return_value={"analysis": "ac"}) as sim:
            self.post({"analysis": "ac"})
        self.assertEqual(sim.call_args.args[1], "ac")

    def test_simulate_rejects_unknown_analysis(self):
        with captured_templates() as templates:
            resp = self.post({"analysis": "noise"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("analysis", templates[-1][1]["sim_error"])


if __name__ == "__main__":
    unittest.main()
