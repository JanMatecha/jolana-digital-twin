from __future__ import annotations

import argparse
from pathlib import Path

from .libre import load_libre_csv, summarize
from .plotting import plot_glucose


def main() -> None:
    parser = argparse.ArgumentParser(description="Load and plot FreeStyle Libre data.")
    parser.add_argument("csv_path", type=Path, help="Path to Libre CSV export.")
    parser.add_argument("--plot", type=Path, help="Optional PNG output path.")
    args = parser.parse_args()

    frame = load_libre_csv(args.csv_path)
    summary = summarize(frame)

    print(f"Rows: {summary.rows}")
    print(f"Glucose points: {summary.glucose_points}")
    print(f"Start: {_format_timestamp(summary.start)}")
    print(f"End: {_format_timestamp(summary.end)}")
    print(f"Mean glucose: {_format_number(summary.mean_glucose)} mmol/L")
    print(f"Min glucose: {_format_number(summary.min_glucose)} mmol/L")
    print(f"Max glucose: {_format_number(summary.max_glucose)} mmol/L")

    if args.plot:
        output_path = plot_glucose(frame, args.plot)
        print(f"Plot: {output_path}")


def _format_timestamp(value) -> str:
    if value is None:
        return "n/a"
    return value.strftime("%Y-%m-%d %H:%M")


def _format_number(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


if __name__ == "__main__":
    main()
