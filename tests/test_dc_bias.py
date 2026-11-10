import unittest

from dc_bias import solve, validate_inputs


class TestValidateInputs(unittest.TestCase):
    def test_valid_values_pass(self):
        validate_inputs(12.0, 100_000.0, 22_000.0, 2_200.0, 1_000.0, 100.0, 0.7)

    def test_zero_resistor_rejected(self):
        with self.assertRaisesRegex(ValueError, "R1, R2, RC, RE ต้องมากกว่า 0"):
            validate_inputs(12.0, 0.0, 22_000.0, 2_200.0, 1_000.0, 100.0, 0.7)

    def test_negative_resistor_rejected(self):
        with self.assertRaisesRegex(ValueError, "R1, R2, RC, RE ต้องมากกว่า 0"):
            validate_inputs(12.0, 100_000.0, 22_000.0, -2_200.0, 1_000.0, 100.0, 0.7)

    def test_zero_vcc_rejected(self):
        with self.assertRaisesRegex(ValueError, "VCC ต้องมากกว่า 0"):
            validate_inputs(0.0, 100_000.0, 22_000.0, 2_200.0, 1_000.0, 100.0, 0.7)

    def test_zero_beta_rejected(self):
        with self.assertRaisesRegex(ValueError, "beta ต้องมากกว่า 0"):
            validate_inputs(12.0, 100_000.0, 22_000.0, 2_200.0, 1_000.0, 0.0, 0.7)

    def test_zero_vbe_rejected(self):
        with self.assertRaisesRegex(ValueError, "VBE ต้องมากกว่า 0"):
            validate_inputs(12.0, 100_000.0, 22_000.0, 2_200.0, 1_000.0, 100.0, 0.0)

    def test_validate_rejects_non_finite(self):
        with self.assertRaisesRegex(ValueError, "จำกัด"):
            validate_inputs(float("inf"), 100_000.0, 22_000.0, 2_200.0, 1_000.0, 100.0, 0.7)


class TestSolveReferenceCase(unittest.TestCase):
    """VCC=12V, R1=100k, R2=22k, RC=2.2k, RE=1k, beta=100, VBE=0.7"""

    def setUp(self):
        self.r = solve(12.0, 100_000.0, 22_000.0, 2_200.0, 1_000.0, 100.0, 0.7)

    def test_solve_reference_case(self):
        self.assertAlmostEqual(self.r["vth"], 2.163934, places=6)
        self.assertAlmostEqual(self.r["ib"], 1.229858146e-05, places=9)
        self.assertAlmostEqual(self.r["ic"], 1.229858146e-03, places=9)
        self.assertAlmostEqual(self.r["ie"], 1.242156728e-03, places=9)
        self.assertAlmostEqual(self.r["vb"], 1.942157, places=6)
        self.assertAlmostEqual(self.r["ve"], 1.242157, places=6)
        self.assertAlmostEqual(self.r["vc"], 9.294312, places=6)
        self.assertAlmostEqual(self.r["vce"], 8.052155, places=6)

    def test_reference_region_is_forward_active(self):
        self.assertEqual(self.r["region"], "Forward Active")
        self.assertEqual(self.r["warnings"], [])

    def test_solve_rejects_invalid_values(self):
        with self.assertRaisesRegex(ValueError, "VCC ต้องมากกว่า 0"):
            solve(0.0, 100_000.0, 22_000.0, 2_200.0, 1_000.0, 100.0, 0.7)

    def test_solve_rejects_overflow_to_non_finite(self):
        # Huge-but-finite inputs pass validate_inputs but overflow mid-solve
        # (r1*r2 = 1e610) -> results must be rejected, not rendered as nan.
        with self.assertRaisesRegex(ValueError, "จำกัด"):
            solve(12.0, 1e305, 1e305, 2_200.0, 1_000.0, 100.0, 0.7)


class TestSolveRegions(unittest.TestCase):
    def test_solve_cutoff(self):
        # VCC=5V, R2=10k -> VTH=0.454545 <= VBE
        r = solve(5.0, 100_000.0, 10_000.0, 2_200.0, 1_000.0, 100.0, 0.7)
        self.assertLess(r["ib"], 0.0)
        self.assertEqual(r["region"], "Cutoff")
        self.assertEqual(len(r["warnings"]), 1)
        self.assertIn("เชื่อถือไม่ได้", r["warnings"][0])

    def test_solve_saturation(self):
        # reference case with RC=10k -> VCE=-1.540738 < 0.2
        r = solve(12.0, 100_000.0, 22_000.0, 10_000.0, 1_000.0, 100.0, 0.7)
        self.assertLess(r["vce"], 0.2)
        self.assertEqual(r["region"], "Saturation")
        self.assertEqual(len(r["warnings"]), 1)
        self.assertIn("เชื่อถือไม่ได้", r["warnings"][0])


if __name__ == "__main__":
    unittest.main()
