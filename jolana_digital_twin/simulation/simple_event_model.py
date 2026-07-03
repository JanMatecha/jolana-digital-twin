from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd


@dataclass(frozen=True)
class SimulationParameters:
    carb_effect_mmol_l_per_g: float = 0.05
    rapid_insulin_effect_mmol_l_per_unit: float = -1.2
    long_insulin_effect_mmol_l_per_unit: float = -0.15
    carb_peak_minutes: float = 60.0
    carb_duration_minutes: float = 180.0
    insulin_peak_minutes: float = 90.0
    insulin_duration_minutes: float = 240.0


def build_event_simulation(
    glucose_frame: pd.DataFrame,
    insulin_frame: pd.DataFrame,
    meals_frame: pd.DataFrame,
    parameters: SimulationParameters | None = None,
) -> pd.DataFrame:
    parameters = parameters or SimulationParameters()
    glucose = glucose_frame.dropna(subset=["timestamp", "glucose_mmol_l"]).copy()
    if glucose.empty:
        return pd.DataFrame(columns=["timestamp", "simulated_glucose_mmol_l"])

    start = glucose["timestamp"].min()
    end = glucose["timestamp"].max()
    initial_glucose = float(glucose.sort_values("timestamp").iloc[0]["glucose_mmol_l"])

    timeline = _simulation_timeline(start, end)
    meal_events = _meal_events(meals_frame, start, end, parameters)
    insulin_events = _insulin_events(insulin_frame, start, end, parameters)

    rows = []
    for timestamp in timeline:
        carb_effect = _combined_effect(
            timestamp,
            meal_events,
            parameters.carb_peak_minutes,
            parameters.carb_duration_minutes,
            normalize_area=True,
        )
        insulin_effect = _combined_effect(
            timestamp,
            insulin_events,
            parameters.insulin_peak_minutes,
            parameters.insulin_duration_minutes,
            normalize_area=True,
        )
        rows.append(
            {
                "timestamp": timestamp,
                "carb_effect_mmol_l": carb_effect,
                "insulin_effect_mmol_l": insulin_effect,
                "simulated_glucose_mmol_l": max(0.0, initial_glucose + carb_effect + insulin_effect),
            }
        )

    return pd.DataFrame(rows)


def _simulation_timeline(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    timeline = pd.date_range(start=start, end=end, freq="5min")
    if timeline.empty or timeline[-1] != end:
        timeline = timeline.append(pd.DatetimeIndex([end]))
    return timeline


def _combined_effect(
    timestamp: pd.Timestamp,
    events: list[tuple[pd.Timestamp, float]],
    peak_minutes: float,
    duration_minutes: float,
    normalize_area: bool = False,
) -> float:
    area = _gaussian_response_area_hours(peak_minutes, duration_minutes) if normalize_area else 1.0
    return sum(
        effect * _gaussian_response(
            elapsed_minutes=(timestamp - event_timestamp).total_seconds() / 60.0,
            peak_minutes=peak_minutes,
            duration_minutes=duration_minutes,
        )
        / area
        for event_timestamp, effect in events
    )


def _gaussian_response(elapsed_minutes: float, peak_minutes: float, duration_minutes: float) -> float:
    if elapsed_minutes < 0 or elapsed_minutes > duration_minutes:
        return 0.0
    sigma = max(duration_minutes / 6.0, 1.0)
    return math.exp(-0.5 * ((elapsed_minutes - peak_minutes) / sigma) ** 2)


def _gaussian_response_area_hours(peak_minutes: float, duration_minutes: float) -> float:
    sigma = max(duration_minutes / 6.0, 1.0)
    lower = (0.0 - peak_minutes) / (math.sqrt(2.0) * sigma)
    upper = (duration_minutes - peak_minutes) / (math.sqrt(2.0) * sigma)
    area = sigma * math.sqrt(math.pi / 2.0) * (math.erf(upper) - math.erf(lower)) / 60.0
    return max(area, 1e-9)


def _meal_events(
    meals_frame: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    parameters: SimulationParameters,
) -> list[tuple[pd.Timestamp, float]]:
    if meals_frame.empty:
        return []

    events: list[tuple[pd.Timestamp, float]] = []
    for _, meal in meals_frame.dropna(subset=["timestamp"]).iterrows():
        timestamp = meal["timestamp"]
        if timestamp < start or timestamp > end:
            continue
        carbs_g = float(meal["carbs_g"]) if pd.notna(meal.get("carbs_g")) else 0.0
        events.append((timestamp, carbs_g * parameters.carb_effect_mmol_l_per_g))
    return events


def _insulin_events(
    insulin_frame: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    parameters: SimulationParameters,
) -> list[tuple[pd.Timestamp, float]]:
    if insulin_frame.empty:
        return []

    events: list[tuple[pd.Timestamp, float]] = []
    for _, dose in insulin_frame.dropna(subset=["timestamp"]).iterrows():
        timestamp = dose["timestamp"]
        if timestamp < start or timestamp > end:
            continue
        units = float(dose["units"]) if pd.notna(dose.get("units")) else 0.0
        insulin_type = str(dose.get("insulin_type", "rapid"))
        if insulin_type == "long":
            effect = units * parameters.long_insulin_effect_mmol_l_per_unit
        else:
            effect = units * parameters.rapid_insulin_effect_mmol_l_per_unit
        events.append((timestamp, effect))
    return events
