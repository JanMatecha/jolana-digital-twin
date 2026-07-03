from pathlib import Path
import unittest

from jolana_digital_twin.libre import load_libre_csv, summarize


SAMPLE_CSV = Path("data/examples/free_style_libre_sample.csv")


class LibreLoaderTest(unittest.TestCase):
    def test_loads_sample_libre_export(self) -> None:
        frame = load_libre_csv(SAMPLE_CSV)
        summary = summarize(frame)

        self.assertEqual(summary.rows, 309)
        self.assertEqual(summary.glucose_points, 288)
        self.assertEqual(summary.min_glucose, 5.0)
        self.assertEqual(summary.max_glucose, 11.4)
        self.assertEqual(frame.loc[0, "timestamp"].strftime("%Y-%m-%d %H:%M"), "2026-07-01 00:00")
        self.assertEqual(frame.loc[len(frame) - 1, "timestamp"].strftime("%Y-%m-%d %H:%M"), "2026-07-03 23:45")


if __name__ == "__main__":
    unittest.main()
