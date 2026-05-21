#!/usr/bin/env python3
"""Build a centroid-distance adjacency matrix from municipal polygons.

For each municipality pair:
- If polygons are adjacent (geometry intersects), matrix[i, j] is the
    Haversine great-circle distance between centroids (in meters).
- If not adjacent, matrix[i, j] is NaN.
- Diagonal values are 0.0.

The resulting matrix is saved as a CSV file in the package data folder.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import shape
from shapely.strtree import STRtree

from mexari._data import DEFAULT_GEOJSON, DATA_DIR, normalize_cvegeo


EARTH_RADIUS_M = 6_371_008.8


def haversine_distance_meters(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
) -> float:
    """Return the great-circle distance between two WGS84 points in meters."""
    lon1_rad = math.radians(lon1)
    lat1_rad = math.radians(lat1)
    lon2_rad = math.radians(lon2)
    lat2_rad = math.radians(lat2)

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_M * c


def load_features(geojson_path: Path) -> list[dict]:
    with geojson_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    if data.get("type") != "FeatureCollection" or "features" not in data:
        raise ValueError("GeoJSON must be a FeatureCollection with a features list.")
    return data["features"]


def build_distance_matrix(geojson_path: Path) -> pd.DataFrame:
    features = load_features(geojson_path)

    geometries = [shape(feature["geometry"]) for feature in features]
    centroids = [geom.centroid for geom in geometries]
    cvegeos = [
        normalize_cvegeo(feature.get("properties", {}).get("CVEGEO"))
        for feature in features
    ]

    n = len(cvegeos)
    matrix = np.full((n, n), np.nan, dtype=float)
    np.fill_diagonal(matrix, 0.0)

    tree = STRtree(geometries)
    for i, geom in enumerate(geometries):
        for j in tree.query(geom):
            j = int(j)
            if i >= j:
                continue
            if geom.intersects(geometries[j]):
                distance = haversine_distance_meters(
                    centroids[i].x,
                    centroids[i].y,
                    centroids[j].x,
                    centroids[j].y,
                )
                matrix[i, j] = distance
                matrix[j, i] = distance

    return pd.DataFrame(matrix, index=cvegeos, columns=cvegeos)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build municipality adjacency matrix weighted by centroid distances; "
            "non-adjacent pairs are NaN. Distances use Haversine (meters)."
        )
    )
    parser.add_argument(
        "--geojson",
        type=Path,
        default=DEFAULT_GEOJSON,
        help="Path to the input GeoJSON (default: bundled mexari/data/mexico.geojson).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DATA_DIR / "adjacency_centroid_distance_matrix.csv",
        help="Output CSV path (default: mexari/data/adjacency_centroid_distance_matrix.csv).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    geojson_path = args.geojson.expanduser().resolve()
    output_path = args.output.expanduser().resolve()

    if not geojson_path.exists():
        raise FileNotFoundError(f"GeoJSON not found: {geojson_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    matrix_df = build_distance_matrix(geojson_path)
    matrix_df.to_csv(output_path, index=True, index_label="CVEGEO")

    print(f"Saved matrix with shape {matrix_df.shape} to: {output_path}")


if __name__ == "__main__":
    main()
