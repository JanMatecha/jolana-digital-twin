from __future__ import annotations

import csv
import math
from datetime import datetime, timedelta
from pathlib import Path


OUTPUT_PATH = Path("data/examples/free_style_libre_sample.csv")

HEADER_METADATA = [
    "Udaje o glukoze",
    "Vygenerovano dne",
    "02-07-2026 15:46 UTC",
    "Vygeneroval(a)",
    "Sample Patient",
]

HEADER = [
    "Zařízení",
    "Sériové číslo",
    "Časová značka zařízení",
    "Typ záznamu",
    "Historie údajů o glukóze mmol/L",
    "Skenovat glukózu mmol/L",
    "Inzulín s rychlým účinkem, bez číselného vyjádření",
    "Inzulín s rychlým účinkem (jednotky)",
    "Potravina, bez číselného vyjádření",
    "Karbohydráty (gramy)",
    "Karbohydráty (porce)",
    "Inzulín s dlouhým účinkem, bez číselného vyjádření",
    "Inzulín s dlouhým účinkem (jednotky)",
    "Poznámky",
    "Proužek na testování glukózy mmol/L",
    "Keton mmol/L",
    "Inzulín v jídle (jednotky)",
    "Nápravný inzulín (jednotky)",
    "Inzulín, uživatelská změna (jednotky)",
    "Tuky (gramy)",
]

MEALS = {
    "07:15": (42, 12),
    "12:30": (58, 18),
    "18:15": (48, 16),
}

RAPID_INSULIN = {
    "07:00": 2.5,
    "12:15": 3.5,
    "18:00": 3.0,
}

LONG_INSULIN = {
    "21:00": 7.0,
}


def main() -> None:
    rows = [HEADER_METADATA, HEADER]
    start = datetime(2026, 7, 1, 0, 0)

    for step in range(3 * 24 * 4):
        timestamp = start + timedelta(minutes=15 * step)
        rows.append(_glucose_row(timestamp))

        time_key = timestamp.strftime("%H:%M")
        if time_key in RAPID_INSULIN:
            rows.append(_rapid_insulin_row(timestamp, RAPID_INSULIN[time_key]))
        if time_key in MEALS:
            carbs_g, fat_g = MEALS[time_key]
            rows.append(_meal_row(timestamp, carbs_g, fat_g))
        if time_key in LONG_INSULIN:
            rows.append(_long_insulin_row(timestamp, LONG_INSULIN[time_key]))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(rows)


def _glucose_row(timestamp: datetime) -> list[str]:
    value = _glucose_value(timestamp)
    row = _blank_row(timestamp, record_type="0")
    row[4] = _format_decimal(value)
    return row


def _rapid_insulin_row(timestamp: datetime, units: float) -> list[str]:
    row = _blank_row(timestamp, record_type="4")
    row[7] = _format_decimal(units)
    return row


def _meal_row(timestamp: datetime, carbs_g: int, fat_g: int) -> list[str]:
    row = _blank_row(timestamp, record_type="5")
    row[9] = str(carbs_g)
    row[19] = str(fat_g)
    return row


def _long_insulin_row(timestamp: datetime, units: float) -> list[str]:
    row = _blank_row(timestamp, record_type="4")
    row[12] = _format_decimal(units)
    return row


def _blank_row(timestamp: datetime, record_type: str) -> list[str]:
    row = [""] * len(HEADER)
    row[1] = "SAMPLE"
    row[2] = timestamp.strftime("%d-%m-%Y %H:%M")
    row[3] = record_type
    return row


def _glucose_value(timestamp: datetime) -> float:
    minutes = timestamp.hour * 60 + timestamp.minute
    day_index = (timestamp.date() - datetime(2026, 7, 1).date()).days

    baseline = 6.4 + 0.35 * math.sin((minutes - 240) / 1440 * 2 * math.pi)
    overnight_dip = -0.8 * math.exp(-((minutes - 210) / 150) ** 2)
    breakfast = 3.7 * math.exp(-((minutes - 510) / 95) ** 2)
    lunch = 4.1 * math.exp(-((minutes - 830) / 115) ** 2)
    dinner = 3.3 * math.exp(-((minutes - 1190) / 125) ** 2)
    correction_drop = -1.2 * math.exp(-((minutes - 980) / 90) ** 2)
    deterministic_noise = 0.25 * math.sin(step_like(timestamp) * 1.7)
    day_shift = [0.0, 0.7, -0.3][day_index]

    value = baseline + overnight_dip + breakfast + lunch + dinner + correction_drop + deterministic_noise + day_shift
    return max(3.1, min(15.2, round(value, 1)))


def step_like(timestamp: datetime) -> int:
    delta = timestamp - datetime(2026, 7, 1)
    return int(delta.total_seconds() // 900)


def _format_decimal(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


if __name__ == "__main__":
    main()
