from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


def plot_glucose(frame: pd.DataFrame, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    glucose = frame.dropna(subset=["timestamp", "glucose_mmol_l"])

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(glucose["timestamp"], glucose["glucose_mmol_l"], linewidth=1.4, color="#1f77b4")
    ax.axhspan(3.9, 10.0, color="#2ca02c", alpha=0.12, label="cilove pasmo 3.9-10.0 mmol/L")
    ax.axhline(3.9, color="#d62728", linestyle="--", linewidth=0.9)
    ax.axhline(10.0, color="#ff7f0e", linestyle="--", linewidth=0.9)

    ax.set_title("Libre glucose")
    ax.set_xlabel("Cas")
    ax.set_ylabel("Glukoza (mmol/L)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m\n%H:%M"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    return output_path
