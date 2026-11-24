import unittest

import spice_plots


class TestPolylinePoints(unittest.TestCase):
    def test_polyline_maps_ranges_and_flips_y(self):
        pts = spice_plots.polyline_points(
            [0, 1], [0, 1], 100, 50, 5, (0, 1), (0, 1)
        )
        self.assertEqual(pts, "5,45 95,5")

    def test_polyline_handles_equal_x_range(self):
        pts = spice_plots.polyline_points(
            [1, 1], [0, 1], 100, 50, 5, (1, 1), (0, 1)
        )
        self.assertEqual(len(pts.split()), 2)


class TestNiceRange(unittest.TestCase):
    def test_nice_range_pads_and_handles_equal_values(self):
        lo, hi = spice_plots.nice_range([2.0, 2.0])
        self.assertLess(lo, 2.0)
        self.assertGreater(hi, 2.0)

    def test_nice_range_uses_min_max_with_padding(self):
        lo, hi = spice_plots.nice_range([0.0, 10.0], pad_fraction=0.1)
        self.assertAlmostEqual(lo, -1.0)
        self.assertAlmostEqual(hi, 11.0)


class TestBodeSvg(unittest.TestCase):
    def test_bode_svg_contains_gain_phase_and_units(self):
        svg = spice_plots.bode_svg(
            [10, 100, 1000], [0.0, 10.0, 20.0], [180.0, 175.0, 170.0]
        )
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("Gain (dB)", svg)
        self.assertIn("Phase (deg)", svg)
        self.assertIn("Hz", svg)
        self.assertGreaterEqual(svg.count("<polyline"), 2)


class TestWaveSvg(unittest.TestCase):
    def test_wave_svg_has_both_series_and_time_axis(self):
        svg = spice_plots.wave_svg(
            [0.0, 0.001, 0.002], [0.0, 0.01, 0.0], [0.0, -0.5, 0.0]
        )
        self.assertIn('data-series="vin"', svg)
        self.assertIn('data-series="vout"', svg)
        self.assertIn("Time (ms)", svg)
        self.assertIn("Voltage (V)", svg)


class TestEmptySeries(unittest.TestCase):
    def test_bode_rejects_empty(self):
        with self.assertRaises(ValueError):
            spice_plots.bode_svg([], [], [])

    def test_wave_rejects_empty(self):
        with self.assertRaises(ValueError):
            spice_plots.wave_svg([], [], [])


if __name__ == "__main__":
    unittest.main()
