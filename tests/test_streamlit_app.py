from datetime import date, datetime
from pathlib import Path
import unittest

import pandas as pd

from jolana_digital_twin.libre import load_libre_csv
from jolana_digital_twin.presentation.streamlit_app import (
    _combine_date_hour,
    _lower_panel_axis_ranges,
    _resolve_input,
    filter_by_period,
)


SAMPLE_CSV = Path("data/examples/free_style_libre_sample.csv")


class StreamlitAppTest(unittest.TestCase):
    def test_filters_rows_by_selected_period(self) -> None:
        frame = load_libre_csv(SAMPLE_CSV)

        filtered = filter_by_period(
            frame,
            datetime(2026, 7, 1, 7, 0),
            datetime(2026, 7, 1, 9, 0),
        )

        timestamps = filtered["timestamp"].dropna()
        self.assertEqual(len(filtered), 11)
        self.assertEqual(timestamps.min().strftime("%Y-%m-%d %H:%M"), "2026-07-01 07:00")
        self.assertEqual(timestamps.max().strftime("%Y-%m-%d %H:%M"), "2026-07-01 09:00")

    def test_resolves_selected_local_real_file(self) -> None:
        selected_path = Path("data/raw/libre_export.csv")

        resolved = _resolve_input("Lokalni realna data", uploaded_file=None, selected_local_file=selected_path)

        self.assertEqual(resolved, selected_path)

    def test_combines_end_hour_24_as_next_midnight(self) -> None:
        self.assertEqual(
            _combine_date_hour(date(2026, 7, 1), 24),
            datetime(2026, 7, 2, 0, 0),
        )

    def test_lower_panel_axis_ranges_share_zero_baseline(self) -> None:
        meals_frame = pd.DataFrame({"carbs_g": [11.5, 60.5], "fat_g": [0.0, 20.0]})
        insulin_frame = pd.DataFrame({"units": [1.0, 4.0]})

        meal_range, insulin_range = _lower_panel_axis_ranges(meals_frame, insulin_frame)

        self.assertEqual(meal_range[0], 0.0)
        self.assertEqual(insulin_range[0], 0.0)
        self.assertGreater(meal_range[1], 60.5)
        self.assertGreater(insulin_range[1], 4.0)


if __name__ == "__main__":
    unittest.main()
