from __future__ import annotations

from datetime import datetime, time, timedelta
from fnmatch import fnmatch
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as components

from jolana_digital_twin.application import import_libre_csv, import_manual_meals_csv
from jolana_digital_twin.application.database import initialize_configured_database
from jolana_digital_twin.application.persistent_import import import_libre_csv_to_configured_database
from jolana_digital_twin.config import Settings, ensure_data_directories, get_settings
from jolana_digital_twin.libre import summarize
from jolana_digital_twin.simulation import (
    SimulationParameters,
    build_event_simulation,
    build_modelica_event_simulation,
)
from jolana_digital_twin.storage import SQLiteStore


SAMPLE_DATA = Path("data/examples/free_style_libre_sample.csv")
DEFAULT_DEBUG_DATE = datetime(2026, 6, 22).date()
TEXT_COLOR = "#111827"
GRID_COLOR = "#d7dee8"
AXIS_LINE_COLOR = "#64748b"
MODEL_WORKFLOW_MERMAID = """
flowchart LR
    A["Libre CSV"] --> B["LibreCsvReader"]
    M["manual meals.csv"] --> C["ManualMealsCsvReader"]

    B --> D["ImportedData"]
    C --> D

    D --> E["Temporary SQLite"]
    E --> F["glucose_frame"]
    E --> G["insulin_frame"]
    E --> H["meals_frame"]

    F --> P["Python Gaussian response model"]
    G --> P
    H --> P

    F --> O["OpenModelica wrapper"]
    G --> O
    H --> O

    O --> MO["GaussianResponseGlucose.mo"]
    MO --> CSV["OpenModelica CSV result"]

    P --> V["Plotly comparison chart"]
    CSV --> V
    F --> V
"""


def main() -> None:
    settings = get_settings()
    ensure_data_directories(settings)
    initialize_configured_database(settings)
    st.set_page_config(page_title="Jolana Digital Twin", layout="wide")
    _apply_light_theme()
    st.title("Jolana Digital Twin")
    st.caption("Prvni webovy nahled dat z FreeStyle Libre.")

    local_files = _local_data_files(settings)
    input_options = ["Anonymni ukazkova data", "Nahrat CSV"]
    if local_files:
        input_options.insert(0, "Lokalni realna data")

    input_mode = st.sidebar.radio("Zdroj dat", input_options)
    selected_local_file = None
    uploaded_file = None

    if input_mode == "Lokalni realna data":
        selected_local_file = st.sidebar.selectbox(
            "Lokalni CSV",
            local_files,
            format_func=lambda path: str(path),
        )
    elif input_mode == "Nahrat CSV":
        uploaded_file = st.sidebar.file_uploader("Libre CSV", type=["csv"])

    simulation_parameters = _show_simulation_parameters()

    try:
        csv_path = _resolve_input(input_mode, uploaded_file, selected_local_file)
        _show_data_source_info(input_mode, csv_path, settings, uploaded_file)
        _show_persistent_import_action(input_mode, csv_path, settings, uploaded_file)
        frame, insulin_frame, meals_frame = _load_universal_frames(csv_path, _manual_meals_path(settings))
    except Exception as exc:
        st.error(f"Data se nepodarilo nacist: {exc}")
        return

    _, selected_start, selected_end = _show_period_controls(frame)
    filtered_frame, filtered_insulin, filtered_meals = _filter_timeline_frames(
        frame,
        insulin_frame,
        meals_frame,
        selected_start,
        selected_end,
    )
    if filtered_frame.empty:
        st.warning("Ve vybranem obdobi nejsou zadna mereni glukozy. Zkontroluj zacatek a konec zobrazeni.")
    summary = summarize(filtered_frame)
    simulation_frame = build_event_simulation(
        filtered_frame,
        filtered_insulin,
        filtered_meals,
        simulation_parameters,
    )
    modelica_frame, modelica_error = _build_modelica_simulation_frame(
        filtered_frame,
        filtered_insulin,
        filtered_meals,
        simulation_parameters,
    )
    if modelica_error:
        st.warning(modelica_error)
    _show_summary(summary)
    _show_timeline_chart(filtered_frame, filtered_insulin, filtered_meals, simulation_frame, modelica_frame)

    with st.expander("Nahled dat"):
        st.subheader("Glukoza")
        st.dataframe(filtered_frame, use_container_width=True)
        st.subheader("Inzulin")
        st.dataframe(filtered_insulin, use_container_width=True)
        st.subheader("Jidlo")
        st.dataframe(filtered_meals, use_container_width=True)


def _apply_light_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: #ffffff;
            color: #111827;
        }
        .stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp label,
        .stApp [data-testid="stMarkdownContainer"],
        .stApp [data-testid="stMetricLabel"],
        .stApp [data-testid="stMetricValue"] {
            color: #111827;
        }
        [data-testid="stSidebar"] {
            background: #f8fafc;
            color: #111827;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _manual_meals_path(settings: Settings) -> Path:
    return settings.data_dir / "manual" / "meals.csv"


def _local_data_patterns(settings: Settings) -> list[tuple[Path, str]]:
    return [
        (settings.data_dir / "raw", "*.csv"),
        (Path("."), "*_glucose_*.csv"),
    ]


def _local_data_files(settings: Settings) -> list[Path]:
    files: list[Path] = []
    for directory, pattern in _local_data_patterns(settings):
        files.extend(path for path in directory.glob(pattern) if path.is_file())
    return sorted(set(files), key=lambda path: str(path).lower())


def _local_file_origin(path: Path, settings: Settings) -> str:
    resolved_path = _safe_resolve(path)
    raw_dir = _safe_resolve(settings.data_dir / "raw")
    project_root = _safe_resolve(Path("."))

    if _is_relative_to(resolved_path, raw_dir):
        return "configured_raw"

    if fnmatch(path.name, "*_glucose_*.csv") and resolved_path.parent == project_root:
        return "legacy_project_root"

    return "unknown"


def _file_metadata(path: Path) -> dict[str, str]:
    try:
        stat = path.stat()
    except OSError:
        return {"exists": "false", "size": "n/a", "modified": "n/a"}

    return {
        "exists": "true",
        "size": _format_file_size(stat.st_size),
        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
    }


def _format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def _safe_resolve(path: Path) -> Path:
    try:
        return path.resolve(strict=False)
    except OSError:
        return path.absolute()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _show_data_source_info(input_mode: str, csv_path: Path, settings: Settings, uploaded_file) -> None:
    if input_mode == "Lokalni realna data":
        metadata = _file_metadata(csv_path)
        st.sidebar.info(
            "\n\n".join(
                [
                    "**Aktualni zdroj dat:** Lokalni CSV",
                    f"**Soubor:** `{csv_path}`",
                    f"**Umisteni:** {_local_file_origin_label(_local_file_origin(csv_path, settings))}",
                    f"**Velikost:** {metadata['size']}",
                    f"**Zmeneno:** {metadata['modified']}",
                ]
            )
        )
    elif input_mode == "Anonymni ukazkova data":
        st.sidebar.info(
            "\n\n".join(
                [
                    "**Aktualni zdroj dat:** Anonymni ukazkova data",
                    f"**Soubor:** `{SAMPLE_DATA}`",
                    "**Poznamka:** Tato data jsou anonymizovana testovaci data z repozitare.",
                ]
            )
        )
    elif input_mode == "Nahrat CSV" and uploaded_file is not None:
        st.sidebar.info(
            "\n\n".join(
                [
                    "**Aktualni zdroj dat:** Nahrany CSV soubor",
                    f"**Puvodni nazev:** `{uploaded_file.name}`",
                    (
                        "**Poznamka:** Soubor je pouzit jen docasne pro aktualni zobrazeni. "
                        "Zatim se neuklada do data/raw ani do persistentni databaze."
                    ),
                ]
            )
        )


def _show_persistent_import_action(input_mode: str, csv_path: Path, settings: Settings, uploaded_file) -> None:
    if input_mode == "Anonymni ukazkova data":
        st.sidebar.caption("Anonymni ukazkova data se bezne neimportuji do persistentni databaze.")
        return

    if input_mode == "Nahrat CSV" and uploaded_file is None:
        return

    if input_mode not in ("Lokalni realna data", "Nahrat CSV"):
        return

    st.sidebar.subheader("Persistentni import")
    if st.sidebar.button("Importovat tento CSV soubor do databaze"):
        try:
            result = import_libre_csv_to_configured_database(
                csv_path,
                settings=settings,
                original_file_name=uploaded_file.name if uploaded_file is not None else None,
            )
        except Exception as exc:
            st.sidebar.error(f"Import se nepodaril: {exc}")
            return

        if result.status == "duplicate":
            st.sidebar.warning("Tento CSV soubor uz byl importovan. Data nebyla vlozena podruhe.")
            st.sidebar.caption(f"Import ID: {result.import_id}, checksum: {result.checksum[:12]}")
            return

        st.sidebar.success("CSV soubor byl importovan do persistentni databaze.")
        st.sidebar.caption(f"Import ID: {result.import_id}")
        st.sidebar.caption(f"Checksum: {result.checksum[:12]}")
        st.sidebar.caption(f"Raw kopie: {result.raw_path}")
        st.sidebar.caption(
            f"Ulozeno: glukoza {result.glucose_readings}, inzulin {result.insulin_doses}, jidlo {result.meals}"
        )


def _local_file_origin_label(origin: str) -> str:
    labels = {
        "configured_raw": "<JOLANA_DATA_DIR>/raw",
        "legacy_project_root": "legacy fallback v koreni projektu",
        "unknown": "nezname umisteni",
    }
    return labels.get(origin, labels["unknown"])


def _resolve_input(input_mode: str, uploaded_file, selected_local_file: Path | None) -> Path:
    if input_mode == "Lokalni realna data":
        if selected_local_file is None:
            raise ValueError("Nenasel jsem zadne lokalni realne CSV.")
        return selected_local_file

    if uploaded_file is not None:
        suffix = Path(uploaded_file.name).suffix or ".csv"
        with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(uploaded_file.getbuffer())
            return Path(temp_file.name)

    if input_mode == "Anonymni ukazkova data":
        return SAMPLE_DATA

    raise ValueError("Nahraj Libre CSV nebo vyber dostupny zdroj dat.")


def _show_simulation_parameters() -> SimulationParameters:
    st.sidebar.subheader("Parametry modelu")
    carb_effect = st.sidebar.number_input(
        "Citlivost na sacharidy - plocha odezvy (mmol/L*h na 1 g)",
        min_value=0.0,
        max_value=0.5,
        value=0.05,
        step=0.01,
        format="%.2f",
        help="Celkova plocha vzestupu pod odezvovou krivkou po 1 g sacharidu. Integruje se v hodinach.",
    )
    carb_peak_minutes = st.sidebar.number_input(
        "Sacharidy: cas vrcholu (min)",
        min_value=0,
        max_value=360,
        value=60,
        step=15,
        help="Za jak dlouho ma byt vliv sacharidu nejsilnejsi.",
    )
    carb_duration_minutes = st.sidebar.number_input(
        "Sacharidy: delka odezvy (min)",
        min_value=15,
        max_value=720,
        value=180,
        step=15,
        help="Jak dlouho ma vliv sacharidu trvat.",
    )
    insulin_sensitivity = st.sidebar.number_input(
        "Inzulinova citlivost - plocha odezvy (mmol/L*h na 1 jednotku)",
        min_value=0.0,
        max_value=10.0,
        value=1.20,
        step=0.10,
        format="%.2f",
        help="Celkova plocha poklesu pod odezvovou krivkou po 1 jednotce inzulinu. Integruje se v hodinach.",
    )
    insulin_peak_minutes = st.sidebar.number_input(
        "Inzulin: cas vrcholu (min)",
        min_value=0,
        max_value=720,
        value=90,
        step=15,
        help="Za jak dlouho ma byt vliv inzulinu nejsilnejsi.",
    )
    insulin_duration_minutes = st.sidebar.number_input(
        "Inzulin: delka odezvy (min)",
        min_value=15,
        max_value=1440,
        value=240,
        step=15,
        help="Jak dlouho ma vliv inzulinu trvat.",
    )
    return SimulationParameters(
        carb_effect_mmol_l_per_g=carb_effect,
        rapid_insulin_effect_mmol_l_per_unit=-insulin_sensitivity,
        long_insulin_effect_mmol_l_per_unit=-insulin_sensitivity,
        carb_peak_minutes=float(carb_peak_minutes),
        carb_duration_minutes=float(carb_duration_minutes),
        insulin_peak_minutes=float(insulin_peak_minutes),
        insulin_duration_minutes=float(insulin_duration_minutes),
    )


def _load_universal_frames(
    csv_path: Path,
    manual_meals_path: Path | None = None,
    include_manual_meals: bool = True,
):
    manual_meals_path = manual_meals_path or _manual_meals_path(get_settings())
    with NamedTemporaryFile(delete=False, suffix=".sqlite") as temp_file:
        db_path = Path(temp_file.name)

    import_libre_csv(csv_path, db_path)
    if include_manual_meals and manual_meals_path.exists():
        import_manual_meals_csv(manual_meals_path, db_path)

    store = SQLiteStore(db_path)
    glucose_frame = store.glucose_readings_frame()
    insulin_frame = store.insulin_doses_frame()
    meals_frame = store.meals_frame()
    db_path.unlink(missing_ok=True)

    glucose_frame["glucose_source"] = glucose_frame["source"]
    return glucose_frame, insulin_frame, meals_frame


def _build_modelica_simulation_frame(
    glucose_frame: pd.DataFrame,
    insulin_frame: pd.DataFrame,
    meals_frame: pd.DataFrame,
    simulation_parameters: SimulationParameters,
) -> tuple[pd.DataFrame, str | None]:
    try:
        return (
            build_modelica_event_simulation(
                glucose_frame,
                insulin_frame,
                meals_frame,
                simulation_parameters,
            ),
            None,
        )
    except Exception as exc:
        return pd.DataFrame(columns=["timestamp", "modelica_glucose_mmol_l"]), f"Modelica simulace se nepodarila: {exc}"


def _show_period_controls(frame) -> tuple[pd.DataFrame, datetime, datetime]:
    timestamps = frame["timestamp"].dropna()
    if timestamps.empty:
        st.warning("Data neobsahuji platne casove znacky.")
        return frame, datetime.min, datetime.max

    start = timestamps.min().to_pydatetime()
    end = timestamps.max().to_pydatetime()
    day_start = datetime.combine(start.date(), time.min)
    day_end = datetime.combine(end.date() + timedelta(days=1), time.min)

    if start == end:
        st.info(f"Data obsahuji jen jeden cas: {start:%d.%m.%Y %H:%M}.")
        return frame, start, end

    default_start_date = start.date()
    default_end_date = end.date()
    if start.date() <= DEFAULT_DEBUG_DATE <= end.date():
        default_start_date = DEFAULT_DEBUG_DATE
        default_end_date = DEFAULT_DEBUG_DATE

    st.subheader("Zobrazovane obdobi")
    start_cols = st.columns(2)
    end_cols = st.columns(2)

    start_date = start_cols[0].date_input(
        "Zacatek den",
        value=default_start_date,
        min_value=start.date(),
        max_value=end.date(),
    )
    start_hour = start_cols[1].number_input(
        "Zacatek hodina",
        min_value=0,
        max_value=23,
        value=0,
        step=1,
    )
    end_date = end_cols[0].date_input(
        "Konec den",
        value=default_end_date,
        min_value=start.date(),
        max_value=end.date(),
    )
    end_hour = end_cols[1].number_input(
        "Konec hodina",
        min_value=0,
        max_value=24,
        value=24,
        step=1,
    )

    manual_start = _combine_date_hour(start_date, int(start_hour))
    manual_end = _combine_date_hour(end_date, int(end_hour))
    manual_start = max(day_start, min(manual_start, day_end))
    manual_end = max(day_start, min(manual_end, day_end))

    if manual_start >= manual_end:
        st.error("Zacatek obdobi musi byt pred koncem obdobi.")
        return frame.iloc[0:0].copy(), manual_start, manual_end

    selected_start, selected_end = st.slider(
        "Jemne doladeni obdobi",
        min_value=day_start,
        max_value=day_end,
        value=(manual_start, manual_end),
        step=timedelta(minutes=15),
        format="DD.MM.YYYY HH:mm",
        key=f"period_slider_{manual_start.isoformat()}_{manual_end.isoformat()}",
    )

    return filter_by_period(frame, selected_start, selected_end), selected_start, selected_end


def _combine_date_hour(selected_date, hour: int) -> datetime:
    if hour == 24:
        return datetime.combine(selected_date + timedelta(days=1), time.min)
    return datetime.combine(selected_date, time(hour=hour))


def filter_by_period(frame, start: datetime, end: datetime):
    if frame.empty or "timestamp" not in frame.columns:
        return frame.copy()

    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    return frame.loc[
        frame["timestamp"].notna()
        & (frame["timestamp"] >= start_ts)
        & (frame["timestamp"] <= end_ts)
    ].copy()


def _filter_timeline_frames(
    glucose_frame,
    insulin_frame,
    meals_frame,
    start: datetime,
    end: datetime,
):
    return (
        filter_by_period(glucose_frame, start, end),
        filter_by_period(insulin_frame, start, end),
        filter_by_period(meals_frame, start, end),
    )


def _show_summary(summary) -> None:
    cols = st.columns(6)
    cols[0].metric("Radku", summary.rows)
    cols[1].metric("Hodnot glukozy", summary.glucose_points)
    cols[2].metric("Prumer", _format_mmol(summary.mean_glucose))
    cols[3].metric("Minimum", _format_mmol(summary.min_glucose))
    cols[4].metric("Maximum", _format_mmol(summary.max_glucose))
    cols[5].metric("Obdobi", _format_period(summary.start, summary.end))


def _show_timeline_chart(frame, insulin_frame, meals_frame, simulation_frame, modelica_frame=None) -> None:
    glucose = frame.dropna(subset=["timestamp", "glucose_mmol_l"])

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.68, 0.32],
        vertical_spacing=0.08,
        specs=[[{"secondary_y": False}], [{"secondary_y": True}]],
    )

    fig.add_trace(
        go.Scatter(
            x=glucose["timestamp"],
            y=glucose["glucose_mmol_l"],
            mode="lines",
            name="mereni",
            line={"color": "#1f77b4", "width": 1.6},
            hovertemplate="%{x|%d.%m.%Y %H:%M}<br>mereni: %{y:.1f} mmol/L<extra></extra>",
        ),
        row=1,
        col=1,
    )
    if not simulation_frame.empty:
        fig.add_trace(
            go.Scatter(
                x=simulation_frame["timestamp"],
                y=simulation_frame["simulated_glucose_mmol_l"],
                mode="lines",
                name="model Python",
                line={"color": "#d62728", "width": 1.4},
                hovertemplate="%{x|%d.%m.%Y %H:%M}<br>model Python: %{y:.1f} mmol/L<extra></extra>",
            ),
            row=1,
            col=1,
        )
        if simulation_frame["carb_effect_mmol_l"].abs().max() > 0:
            fig.add_trace(
                go.Scatter(
                    x=simulation_frame["timestamp"],
                    y=simulation_frame["carb_effect_mmol_l"],
                    mode="lines",
                    name="vliv sacharidu",
                    line={"color": "#2ca02c", "width": 1.1, "dash": "dot"},
                    hovertemplate="%{x|%d.%m.%Y %H:%M}<br>vliv sacharidu: %{y:.1f} mmol/L<extra></extra>",
                ),
                row=1,
                col=1,
            )

    if modelica_frame is not None and not modelica_frame.empty:
        fig.add_trace(
            go.Scatter(
                x=modelica_frame["timestamp"],
                y=modelica_frame["modelica_glucose_mmol_l"],
                mode="lines",
                name="model Modelica",
                line={"color": "#111827", "width": 1.2, "dash": "dash"},
                hovertemplate="%{x|%d.%m.%Y %H:%M}<br>model Modelica: %{y:.1f} mmol/L<extra></extra>",
            ),
            row=1,
            col=1,
        )
        if simulation_frame["insulin_effect_mmol_l"].abs().max() > 0:
            fig.add_trace(
                go.Scatter(
                    x=simulation_frame["timestamp"],
                    y=simulation_frame["insulin_effect_mmol_l"],
                    mode="lines",
                    name="vliv inzulinu",
                    line={"color": "#9467bd", "width": 1.1, "dash": "dot"},
                    hovertemplate="%{x|%d.%m.%Y %H:%M}<br>vliv inzulinu: %{y:.1f} mmol/L<extra></extra>",
                ),
                row=1,
                col=1,
            )

    _add_meal_panel(fig, meals_frame, insulin_frame)

    fig.add_hrect(
        y0=3.9,
        y1=10.0,
        fillcolor="green",
        opacity=0.12,
        line_width=0,
        row=1,
        col=1,
    )
    fig.add_hline(y=3.9, line_dash="dash", line_color="red", line_width=1, row=1, col=1)
    fig.add_hline(y=10.0, line_dash="dash", line_color="orange", line_width=1, row=1, col=1)
    meal_axis_range, insulin_axis_range = _lower_panel_axis_ranges(meals_frame, insulin_frame)
    axis_style = {
        "color": TEXT_COLOR,
        "gridcolor": GRID_COLOR,
        "linecolor": AXIS_LINE_COLOR,
        "tickfont": {"color": TEXT_COLOR},
        "title_font": {"color": TEXT_COLOR},
        "zerolinecolor": AXIS_LINE_COLOR,
    }
    fig.update_xaxes(**axis_style)
    fig.update_xaxes(
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikedash="dot",
        spikecolor="#334155",
        spikethickness=1,
    )
    fig.update_yaxes(**axis_style)
    fig.update_yaxes(title_text="Glukoza a vliv modelu (mmol/L)", row=1, col=1)
    fig.update_yaxes(
        title_text="Jidlo (g)",
        range=meal_axis_range,
        zeroline=True,
        zerolinecolor=AXIS_LINE_COLOR,
        zerolinewidth=1,
        row=2,
        col=1,
        secondary_y=False,
    )
    fig.update_yaxes(
        title_text="Inzulin (jednotky)",
        range=insulin_axis_range,
        zeroline=True,
        zerolinecolor=AXIS_LINE_COLOR,
        zerolinewidth=1,
        row=2,
        col=1,
        secondary_y=True,
    )
    fig.update_xaxes(title_text="Cas", row=2, col=1)
    fig.update_layout(
        template="plotly_white",
        height=720,
        hovermode="x unified",
        hoversubplots="axis",
        paper_bgcolor="white",
        plot_bgcolor="white",
        font={"color": TEXT_COLOR},
        hoverlabel={"bgcolor": "white", "font_color": TEXT_COLOR, "bordercolor": "#cbd5e1"},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "font": {"color": TEXT_COLOR},
            "bgcolor": "rgba(255,255,255,0.92)",
        },
        margin={"l": 20, "r": 20, "t": 45, "b": 20},
    )
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Jak funguje Modelica workflow", expanded=False):
        st.caption(
            "Diagram ukazuje tok dat od Libre CSV pres SQLite, Python model a OpenModelica az do spolecneho Plotly grafu."
        )
        _show_mermaid_diagram(MODEL_WORKFLOW_MERMAID)


def _show_mermaid_diagram(diagram: str, height: int = 520) -> None:
    components.html(
        f"""
        <div class="mermaid">
        {diagram}
        </div>
        <script type="module">
          import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
          mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
        </script>
        """,
        height=height,
        scrolling=True,
    )


def _lower_panel_axis_ranges(meals_frame, insulin_frame) -> tuple[list[float], list[float]]:
    meal_max = 0.0
    if not meals_frame.empty:
        for column in ("carbs_g", "fat_g"):
            if column in meals_frame.columns and meals_frame[column].notna().any():
                meal_max = max(meal_max, float(meals_frame[column].fillna(0).max()))

    insulin_max = 0.0
    if not insulin_frame.empty and "units" in insulin_frame.columns and insulin_frame["units"].notna().any():
        insulin_max = float(insulin_frame["units"].fillna(0).max())

    return [0.0, _padded_axis_max(meal_max)], [0.0, _padded_axis_max(insulin_max)]


def _padded_axis_max(value: float) -> float:
    if value <= 0:
        return 1.0
    return value * 1.15


def _add_meal_panel(fig, meals_frame, insulin_frame) -> None:
    if meals_frame.empty and insulin_frame.empty:
        return

    meals = meals_frame.dropna(subset=["timestamp"]) if not meals_frame.empty else meals_frame

    if not meals.empty and "carbs_g" in meals.columns and meals["carbs_g"].notna().any():
        fig.add_trace(
            go.Bar(
                x=meals["timestamp"] - pd.Timedelta(minutes=6),
                y=meals["carbs_g"].fillna(0),
                width=10 * 60 * 1000,
                name="sacharidy",
                marker_color="#ff7f0e",
                opacity=0.75,
                hovertemplate="%{x|%d.%m.%Y %H:%M}<br>sacharidy: %{y:.1f} g<extra></extra>",
            ),
            row=2,
            col=1,
            secondary_y=False,
        )

    if not meals.empty and "fat_g" in meals.columns and meals["fat_g"].notna().any():
        fig.add_trace(
            go.Bar(
                x=meals["timestamp"] + pd.Timedelta(minutes=6),
                y=meals["fat_g"].fillna(0),
                width=10 * 60 * 1000,
                name="tuky",
                marker_color="#9467bd",
                opacity=0.75,
                hovertemplate="%{x|%d.%m.%Y %H:%M}<br>tuky: %{y:.1f} g<extra></extra>",
            ),
            row=2,
            col=1,
            secondary_y=False,
        )

    for insulin_type, color, marker in [("rapid", "black", "triangle-down"), ("long", "purple", "square")]:
        doses = insulin_frame.loc[insulin_frame["insulin_type"] == insulin_type] if not insulin_frame.empty else insulin_frame
        if not doses.empty:
            fig.add_trace(
                go.Scatter(
                    x=doses["timestamp"],
                    y=doses["units"],
                    mode="markers",
                    name=f"inzulin {insulin_type}",
                    marker={"color": color, "symbol": marker, "size": 10, "line": {"color": "white", "width": 1.5}},
                    hovertemplate="%{x|%d.%m.%Y %H:%M}<br>inzulin: %{y:.1f} U<extra></extra>",
                ),
                row=2,
                col=1,
                secondary_y=True,
            )


def _format_mmol(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f} mmol/L"


def _format_period(start, end) -> str:
    if start is None or end is None:
        return "n/a"
    return f"{start:%d.%m.} - {end:%d.%m.}"


if __name__ == "__main__":
    main()
