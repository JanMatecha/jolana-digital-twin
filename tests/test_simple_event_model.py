from pathlib import Path
import unittest

import pandas as pd

from jolana_digital_twin.presentation.streamlit_app import _load_universal_frames
from jolana_digital_twin.simulation import SimulationParameters, build_event_simulation


SAMPLE_CSV = Path("data/examples/free_style_libre_sample.csv")


class SimpleEventModelTest(unittest.TestCase):
    def test_simulation_starts_from_first_measured_glucose(self) -> None:
        glucose_frame, insulin_frame, meals_frame = _load_universal_frames(SAMPLE_CSV, include_manual_meals=False)

        simulation = build_event_simulation(glucose_frame, insulin_frame, meals_frame)

        self.assertEqual(simulation.iloc[0]["timestamp"], glucose_frame.iloc[0]["timestamp"])
        self.assertEqual(
            simulation.iloc[0]["simulated_glucose_mmol_l"],
            glucose_frame.iloc[0]["glucose_mmol_l"],
        )

    def test_meals_raise_and_insulin_lowers_glucose_smoothly(self) -> None:
        glucose_frame, insulin_frame, meals_frame = _load_universal_frames(SAMPLE_CSV, include_manual_meals=False)

        simulation = build_event_simulation(glucose_frame, insulin_frame, meals_frame)

        first_meal = meals_frame.iloc[0]
        after_meal_peak = simulation.loc[
            simulation["timestamp"] == first_meal["timestamp"] + pd.Timedelta(minutes=60)
        ].iloc[-1]

        self.assertGreater(after_meal_peak["carb_effect_mmol_l"], 0)
        self.assertLess(simulation["insulin_effect_mmol_l"].min(), 0)

    def test_parameters_control_event_effects(self) -> None:
        glucose_frame, insulin_frame, meals_frame = _load_universal_frames(SAMPLE_CSV, include_manual_meals=False)

        stronger_carb_effect = build_event_simulation(
            glucose_frame,
            insulin_frame,
            meals_frame,
            SimulationParameters(
                carb_effect_mmol_l_per_g=0.10,
                rapid_insulin_effect_mmol_l_per_unit=-1.2,
                long_insulin_effect_mmol_l_per_unit=-1.2,
            ),
        )
        weaker_carb_effect = build_event_simulation(
            glucose_frame,
            insulin_frame,
            meals_frame,
            SimulationParameters(
                carb_effect_mmol_l_per_g=0.02,
                rapid_insulin_effect_mmol_l_per_unit=-1.2,
                long_insulin_effect_mmol_l_per_unit=-1.2,
            ),
        )

        self.assertGreater(
            stronger_carb_effect["simulated_glucose_mmol_l"].max(),
            weaker_carb_effect["simulated_glucose_mmol_l"].max(),
        )

    def test_carb_peak_parameter_controls_response_peak(self) -> None:
        glucose_frame, insulin_frame, meals_frame = _load_universal_frames(SAMPLE_CSV, include_manual_meals=False)
        parameters = SimulationParameters(
            carb_effect_mmol_l_per_g=0.05,
            rapid_insulin_effect_mmol_l_per_unit=0.0,
            long_insulin_effect_mmol_l_per_unit=0.0,
            carb_peak_minutes=30,
            carb_duration_minutes=120,
        )

        simulation = build_event_simulation(glucose_frame, insulin_frame, meals_frame, parameters)
        first_meal_time = meals_frame.iloc[0]["timestamp"]
        first_meal_window = simulation.loc[
            (simulation["timestamp"] >= first_meal_time)
            & (simulation["timestamp"] <= first_meal_time + pd.Timedelta(minutes=120))
        ]
        peak_row = first_meal_window.sort_values("carb_effect_mmol_l").iloc[-1]

        self.assertEqual(peak_row["timestamp"], first_meal_time + pd.Timedelta(minutes=30))

    def test_insulin_sensitivity_controls_area_under_response(self) -> None:
        start = pd.Timestamp("2026-06-22 00:00")
        end = start + pd.Timedelta(minutes=240)
        glucose_frame = pd.DataFrame(
            {
                "timestamp": [start, end],
                "glucose_mmol_l": [10.0, 10.0],
            }
        )
        insulin_frame = pd.DataFrame(
            {
                "timestamp": [start],
                "units": [2.0],
                "insulin_type": ["rapid"],
            }
        )
        meals_frame = pd.DataFrame(columns=["timestamp", "carbs_g"])
        parameters = SimulationParameters(
            rapid_insulin_effect_mmol_l_per_unit=-1.5,
            long_insulin_effect_mmol_l_per_unit=0.0,
            insulin_peak_minutes=90,
            insulin_duration_minutes=240,
        )

        simulation = build_event_simulation(glucose_frame, insulin_frame, meals_frame, parameters)
        sampled_area = simulation["insulin_effect_mmol_l"].sum() * 5.0

        self.assertAlmostEqual(sampled_area, -3.0, delta=0.05)

    def test_carb_sensitivity_controls_area_under_response(self) -> None:
        start = pd.Timestamp("2026-06-22 00:00")
        end = start + pd.Timedelta(minutes=180)
        glucose_frame = pd.DataFrame(
            {
                "timestamp": [start, end],
                "glucose_mmol_l": [10.0, 10.0],
            }
        )
        insulin_frame = pd.DataFrame(columns=["timestamp", "units", "insulin_type"])
        meals_frame = pd.DataFrame(
            {
                "timestamp": [start],
                "carbs_g": [40.0],
            }
        )
        parameters = SimulationParameters(
            carb_effect_mmol_l_per_g=0.05,
            carb_peak_minutes=60,
            carb_duration_minutes=180,
        )

        simulation = build_event_simulation(glucose_frame, insulin_frame, meals_frame, parameters)
        sampled_area = simulation["carb_effect_mmol_l"].sum() * 5.0

        self.assertAlmostEqual(sampled_area, 2.0, delta=0.05)


if __name__ == "__main__":
    unittest.main()
