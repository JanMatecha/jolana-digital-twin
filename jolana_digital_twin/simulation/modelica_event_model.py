from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
from tempfile import TemporaryDirectory

import pandas as pd

from .simple_event_model import SimulationParameters, _insulin_events, _meal_events


MODEL_FILE = Path("modelica/GaussianResponseGlucose.mo")


def is_openmodelica_available() -> bool:
    return _omc_command() is not None


def build_modelica_event_simulation(
    glucose_frame: pd.DataFrame,
    insulin_frame: pd.DataFrame,
    meals_frame: pd.DataFrame,
    parameters: SimulationParameters | None = None,
    model_file: Path = MODEL_FILE,
) -> pd.DataFrame:
    parameters = parameters or SimulationParameters()
    glucose = glucose_frame.dropna(subset=["timestamp", "glucose_mmol_l"]).copy()
    if glucose.empty:
        return pd.DataFrame(columns=["timestamp", "modelica_glucose_mmol_l"])
    omc_command = _omc_command()
    if omc_command is None:
        raise RuntimeError("OpenModelica command 'omc' is not available in PATH.")

    start = glucose["timestamp"].min()
    end = glucose["timestamp"].max()
    stop_seconds = (end - start).total_seconds()
    if stop_seconds <= 0:
        return pd.DataFrame(
            {
                "timestamp": [start],
                "modelica_glucose_mmol_l": [float(glucose.sort_values("timestamp").iloc[0]["glucose_mmol_l"])],
            }
        )

    initial_glucose = float(glucose.sort_values("timestamp").iloc[0]["glucose_mmol_l"])
    events = _modelica_events(insulin_frame, meals_frame, start, end, parameters)

    with TemporaryDirectory(prefix="jolana_modelica_") as temp_dir:
        temp_path = Path(temp_dir)
        mos_path = temp_path / "run_modelica.mos"
        result_stem = "ModelicaGaussianRun"
        mos_path.write_text(
            _modelica_script(
                model_file=model_file.resolve(),
                result_stem=result_stem,
                initial_glucose=initial_glucose,
                events=events,
                stop_seconds=stop_seconds,
                number_of_intervals=max(1, int(round(stop_seconds / 300.0))),
            ),
            encoding="utf-8",
        )
        process = subprocess.run(
            [str(omc_command), str(mos_path)],
            cwd=temp_path,
            text=True,
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(_format_omc_error(process))

        result_path = _find_result_csv(temp_path, result_stem)
        if not result_path.exists():
            files = ", ".join(sorted(path.name for path in temp_path.iterdir()))
            raise RuntimeError(
                f"OpenModelica did not create expected result CSV for {result_stem}. "
                f"Files: {files}. Output: {process.stdout.strip()} {process.stderr.strip()}"
            )

        result = pd.read_csv(result_path)

    if "time" not in result.columns or "glucose" not in result.columns:
        raise RuntimeError("OpenModelica result is missing 'time' or 'glucose' columns.")

    output = pd.DataFrame(
        {
            "timestamp": start + pd.to_timedelta(result["time"], unit="s"),
            "modelica_glucose_mmol_l": result["glucose"],
        }
    )
    return output.loc[
        (output["timestamp"] >= start) & (output["timestamp"] <= end)
    ].drop_duplicates(subset=["timestamp"], keep="last").reset_index(drop=True)


def _modelica_events(
    insulin_frame: pd.DataFrame,
    meals_frame: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    parameters: SimulationParameters,
) -> list[tuple[float, float, float, float]]:
    events: list[tuple[float, float, float, float]] = []
    for timestamp, effect_hours in _meal_events(meals_frame, start, end, parameters):
        events.append(
            (
                (timestamp - start).total_seconds(),
                effect_hours * 3600.0,
                parameters.carb_peak_minutes * 60.0,
                parameters.carb_duration_minutes * 60.0,
            )
        )
    for timestamp, effect_hours in _insulin_events(insulin_frame, start, end, parameters):
        events.append(
            (
                (timestamp - start).total_seconds(),
                effect_hours * 3600.0,
                parameters.insulin_peak_minutes * 60.0,
                parameters.insulin_duration_minutes * 60.0,
            )
        )
    return sorted(events, key=lambda event: event[0])


def _find_result_csv(directory: Path, result_stem: str) -> Path:
    candidates = [
        directory / f"{result_stem}_res.csv",
        directory / f"{result_stem}.csv",
    ]
    candidates.extend(sorted(directory.glob("*_res.csv")))
    candidates.extend(sorted(directory.glob("*.csv")))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return directory / f"{result_stem}_res.csv"


def _omc_command() -> Path | None:
    path_command = shutil.which("omc")
    if path_command:
        return Path(path_command)

    openmodelica_home = os.environ.get("OPENMODELICAHOME")
    if openmodelica_home:
        candidate = Path(openmodelica_home) / "bin" / "omc.exe"
        if candidate.exists():
            return candidate

    program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
    candidates = sorted(program_files.glob("OpenModelica*/bin/omc.exe"), reverse=True)
    return candidates[0] if candidates else None


def _modelica_script(
    model_file: Path,
    result_stem: str,
    initial_glucose: float,
    events: list[tuple[float, float, float, float]],
    stop_seconds: float,
    number_of_intervals: int,
) -> str:
    event_times = _modelica_array([event[0] for event in events])
    event_areas = _modelica_array([event[1] for event in events])
    peak_times = _modelica_array([event[2] for event in events])
    durations = _modelica_array([event[3] for event in events])
    model_path = str(model_file).replace("\\", "/")
    return f"""loadFile("{model_path}");
loadString("model ModelicaGaussianRun
  extends GaussianResponseGlucose(
    initialGlucose = {_modelica_number(initial_glucose)},
    nEvents = {len(events)},
    eventTimes = {event_times},
    eventAreas = {event_areas},
    peakTimes = {peak_times},
    durations = {durations});
end ModelicaGaussianRun;");
simulate(
  ModelicaGaussianRun,
  startTime = 0,
  stopTime = {_modelica_number(stop_seconds)},
  numberOfIntervals = {number_of_intervals},
  outputFormat = "csv",
  fileNamePrefix = "{result_stem}");
getErrorString();
"""


def _modelica_array(values: list[float]) -> str:
    if not values:
        return "fill(0.0, 0)"
    return "{" + ", ".join(_modelica_number(value) for value in values) + "}"


def _modelica_number(value: float) -> str:
    return f"{float(value):.12g}"


def _format_omc_error(process: subprocess.CompletedProcess[str]) -> str:
    output = "\n".join(part for part in (process.stdout.strip(), process.stderr.strip()) if part)
    return f"OpenModelica simulation failed with exit code {process.returncode}.\n{output}"
