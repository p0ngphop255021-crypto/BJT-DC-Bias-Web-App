import unittest

from app import app


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


if __name__ == "__main__":
    unittest.main()
