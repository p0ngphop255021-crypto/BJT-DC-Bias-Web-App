import unittest

from dc_bias import validate_inputs


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


if __name__ == "__main__":
    unittest.main()
