"""
graphari._data
==============
Helpers for loading bundled weekly municipality geostatistical tables.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import pandas as pd

# The data/ directory lives next to this file inside the package.
_PKG_DIR = Path(__file__).parent
DATA_DIR: Path = _PKG_DIR / "data"
EPIDEMIOLOGICAL_WEEKS_CSV: Path = DATA_DIR / "Epidemiological_Weeks.csv"
DEFAULT_EDGES_CSV: Path = DATA_DIR / "edges.csv"
DEFAULT_ADJACENCY_MATRIX_CSV: Path = DATA_DIR / "adjacency_matrix.csv"

# Explicit order keeps feature vectors deterministic across runs.
DEFAULT_FEATURE_FILES: tuple[str, ...] = (
    "2m_mean_dewpoint_temperature.csv",
    "2m_mean_temperature.csv",
    "2m_relative_humidity.csv",
    "total_precipitation.csv",
    "10m_wind_speed.csv",
)

DEFAULT_START_WEEK = "2003/01"
DEFAULT_END_WEEK = "2024/52"

_NON_FEATURE_TABLES = {
    EPIDEMIOLOGICAL_WEEKS_CSV.name,
    DEFAULT_EDGES_CSV.name,
    DEFAULT_ADJACENCY_MATRIX_CSV.name,
    "adjacency_centroid_distance_matrix.csv",
}


def normalize_epiweek(week: str | int) -> str:
    """Return an epidemiological week label in ``YYYY/WW`` format."""
    text = str(week).strip().replace("-", "/")
    parts = text.split("/")
    if len(parts) != 2:
        raise ValueError(f"Expected an epidemiological week as 'YYYY/WW', got {week!r}.")

    year_text, week_text = parts
    try:
        year = int(year_text)
        week_number = int(week_text)
    except ValueError as exc:
        raise ValueError(f"Expected numeric year/week values, got {week!r}.") from exc

    if week_number < 1 or week_number > 53:
        raise ValueError(f"Epidemiological week must be between 1 and 53, got {week!r}.")
    return f"{year:04d}/{week_number:02d}"


def normalize_cvegeo(value: object) -> str:
    """Return a municipality ``CVEGEO`` code as a zero-padded 5-character string."""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    if not text:
        raise ValueError("CVEGEO values cannot be empty.")
    return text.zfill(5)


def _normalize_index(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.index = pd.Index(
        [normalize_epiweek(week) for week in df.index],
        name=df.index.name or "Date",
    )
    return df


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [normalize_cvegeo(column) for column in df.columns]
    return df


def _select_weeks(
    df: pd.DataFrame,
    *,
    start_week: str | int | None = None,
    end_week: str | int | None = None,
    weeks: Iterable[str | int] | None = None,
) -> pd.DataFrame:
    if weeks is not None and (start_week is not None or end_week is not None):
        raise ValueError("Specify either weeks or a start/end period, not both.")

    if weeks is not None:
        requested = [normalize_epiweek(week) for week in weeks]
        missing = [week for week in requested if week not in df.index]
        if missing:
            raise ValueError(
                "Requested epidemiological weeks are not available: "
                + ", ".join(missing)
            )
        return df.loc[requested]

    start = normalize_epiweek(start_week or DEFAULT_START_WEEK)
    end = normalize_epiweek(end_week or DEFAULT_END_WEEK)
    if start > end:
        raise ValueError(f"start_week must be <= end_week, got {start!r} > {end!r}.")
    if start not in df.index:
        raise ValueError(f"start_week {start!r} is not available in the data.")
    if end not in df.index:
        raise ValueError(f"end_week {end!r} is not available in the data.")

    selected = df.loc[(df.index >= start) & (df.index <= end)]
    if selected.empty:
        raise ValueError(f"No data found between {start!r} and {end!r}.")
    return selected


def _load_weekly_municipality_table(
    path: str | Path,
    *,
    start_week: str | int | None = None,
    end_week: str | int | None = None,
    weeks: Iterable[str | int] | None = None,
) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Data file not found: {csv_path}")

    df = pd.read_csv(csv_path, index_col=0, dtype=str)
    df = _normalize_index(df)
    df = _normalize_columns(df)
    df = df.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return _select_weeks(
        df,
        start_week=start_week,
        end_week=end_week,
        weeks=weeks,
    )


def _canonical_feature_name(file_name: str) -> str:
    stem = Path(file_name).stem.strip().lower()
    stem = re.sub(r"[^a-z0-9]+", "_", stem)
    return stem.strip("_")


def _resolve_feature_paths(
    *,
    feature_files: Iterable[str | Path] | None = None,
) -> list[Path]:
    base_dir = Path(DATA_DIR)
    if feature_files is None:
        paths = [base_dir / name for name in DEFAULT_FEATURE_FILES]
    else:
        paths = []
        for entry in feature_files:
            candidate = Path(f"{entry}.csv") if not str(entry).lower().endswith(".csv") else Path(entry)
            if not candidate.is_absolute():
                candidate = base_dir / candidate
            paths.append(candidate)

    if not paths:
        raise ValueError("feature_files cannot be empty.")

    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Feature table(s) not found: " + ", ".join(missing))
    return paths


def available_feature_tables() -> list[str]:
    """Return weekly municipality CSV files available in the data folder."""
    base_dir = Path(DATA_DIR)
    return sorted(
        path.name
        for path in base_dir.glob("*.csv")
        if path.name not in _NON_FEATURE_TABLES
    )


def load_feature_table(
    path: str | Path,
    *,
    start_week: str | int | None = None,
    end_week: str | int | None = None,
    weeks: Iterable[str | int] | None = None,
) -> pd.DataFrame:
    """Load one weekly municipality table indexed by epidemiological week."""
    return _load_weekly_municipality_table(
        path,
        start_week=start_week,
        end_week=end_week,
        weeks=weeks,
    )


def load_feature_tables(
    *,
    feature_files: Iterable[str | Path] | None = None,
    start_week: str | int | None = None,
    end_week: str | int | None = None,
    weeks: Iterable[str | int] | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Load and align weekly municipality feature tables.

    Returns a dictionary mapping canonical feature names to aligned DataFrames.
    """
    feature_paths = _resolve_feature_paths(feature_files=feature_files)
    tables: dict[str, pd.DataFrame] = {}
    reference_index: pd.Index | None = None
    reference_columns: pd.Index | None = None

    for path in feature_paths:
        feature_name = _canonical_feature_name(path.name)
        if feature_name in tables:
            raise ValueError(f"Duplicate canonical feature name detected: {feature_name!r}")

        df = load_feature_table(
            path,
            start_week=start_week,
            end_week=end_week,
            weeks=weeks,
        )
        if reference_index is None:
            reference_index = df.index
            reference_columns = df.columns
        else:
            if not df.index.equals(reference_index):
                raise ValueError(f"Feature table weeks are not aligned: {path}")
            if not df.columns.equals(reference_columns):
                df = df.reindex(columns=reference_columns, fill_value=0.0)

        tables[feature_name] = df

    return tables


def available_epiweeks() -> list[str]:
    """Return epidemiological weeks available in the default bundled feature span."""
    first_default = Path(DATA_DIR) / DEFAULT_FEATURE_FILES[0]
    df = pd.read_csv(first_default, index_col=0, usecols=[0])
    return [normalize_epiweek(week) for week in df.index]
