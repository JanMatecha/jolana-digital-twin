from pathlib import Path
import unittest

import pandas as pd

from jolana_digital_twin.presentation.streamlit_app import _load_universal_frames
from jolana_digital_twin.simulation import (
    SimulationParameters,
    build_event_simulation,
    build_modelica_event_simulation,
    is_openmodelica_available,
)


SAMPLE_CSV = Path("data/examples/free_style_libre_sample.csv")


class ModelicaEventModelTest(unittest.TestCase):
    def test_modelica_availability_check_returns_boolean(self) -> None:
        self.assertIsInstance(is_openmodelica_available(), bool)

    @unittest.skipUnless(is_openmodelica_available(), "OpenModelica is not available")
    def test_modelica_matches_python_reference_model(self) -> None:
        glucose_frame, insulin_frame, meals_frame = _load_universal_frames(SAMPLE_CSV, include_manual_meals=False)
        glucose_frame = glucose_frame.head(40)
        parameters = SimulationParameters()

        python_simulation = build_event_simulation(glucose_frame, insulin_frame, meals_frame, parameters)
        modelica_simulation = build_modelica_event_simulation(
            glucose_frame,
            insulin_frame,
            meals_frame,
            parameters,
        )
        comparison = pd.merge(python_simulation, modelica_simulation, on="timestamp", how="inner")
        event_times = set(insulin_frame["timestamp"].dropna()).union(set(meals_frame["timestamp"].dropna()))
        comparison = comparison.loc[~comparison["timestamp"].isin(event_times)]

        self.assertGreater(len(comparison), 0)
        max_difference = (
            comparison["simulated_glucose_mmol_l"] - comparison["modelica_glucose_mmol_l"]
        ).abs().max()
        self.assertLess(max_difference, 0.01)


if __name__ == "__main__":
    unittest.main()
