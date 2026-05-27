"""
graphari._graph
===============
Weekly NetworkX graph construction for geostatistical analysis.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import networkx as nx
import numpy as np
import pandas as pd

from graphari._data import (
    DATA_DIR,
    DEFAULT_ADJACENCY_MATRIX_CSV,
    DEFAULT_EDGES_CSV,
    load_feature_table,
    load_feature_tables,
    normalize_cvegeo,
    normalize_epiweek,
)

EXPECTED_NODE_COUNT = 2478
EXISTS_ATTRIBUTE_NAME = "exists"
MORTALITY_ATTRIBUTE_NAME = "mortality_rate"
STATIC_ATTRIBUTE_NAMES = ("population", "latitude", "longitude")
MORTALITY_RATES_CSV = DATA_DIR / "mortality_rates.csv"


def _load_nodes(edge_list_path: str | Path) -> tuple[list[tuple[str, dict]], list[str]]:
    csv_path = Path(edge_list_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Edge list file not found: {csv_path}")

    df = pd.read_csv(csv_path, dtype={"CVEGEO": str, "CVE_ENT": str, "CVE_MUN": str})
    lower_to_column = {column.casefold(): column for column in df.columns}

    required_columns = {
        "CVEGEO",
        "CVE_ENT",
        "CVE_MUN",
        "NOMGEO",
        "NOMMUN",
        "centroid_lon",
        "centroid_lat",
        "creation_week",
    }
    missing = sorted(
        required
        for required in required_columns
        if required.casefold() not in lower_to_column
    )
    if missing:
        raise ValueError(
            f"Edge list CSV is missing required columns: {', '.join(missing)}"
        )

    cvegeo_col = lower_to_column["cvegeo"]
    cve_ent_col = lower_to_column["cve_ent"]
    cve_mun_col = lower_to_column["cve_mun"]
    state_col = lower_to_column["nomgeo"]
    municipality_col = lower_to_column["nommun"]
    lon_col = lower_to_column["centroid_lon"]
    lat_col = lower_to_column["centroid_lat"]
    creation_week_col = lower_to_column["creation_week"]

    population_col = lower_to_column.get("population")
    if population_col is None:
        population_col = lower_to_column.get("pop")
    if population_col is None:
        raise ValueError("Edge list CSV is missing required columns: Population")

    nodes: list[tuple[str, dict]] = []
    order: list[str] = []
    seen: set[str] = set()
    for row in df.to_dict(orient="records"):
        cvegeo = normalize_cvegeo(row[cvegeo_col])
        if cvegeo in seen:
            raise ValueError(f"Duplicate CVEGEO in edge list CSV: {cvegeo}")
        seen.add(cvegeo)
        order.append(cvegeo)

        creation_week = normalize_epiweek(row[creation_week_col])
        population = _parse_population(row[population_col])

        nodes.append(
            (
                cvegeo,
                {
                    "cvegeo": cvegeo,
                    "municipality": str(row.get(municipality_col, "") or ""),
                    "state": str(row.get(state_col, "") or ""),
                    "cve_ent": str(row.get(cve_ent_col, cvegeo[:2]) or cvegeo[:2]).zfill(2),
                    "cve_mun": str(row.get(cve_mun_col, cvegeo[2:]) or cvegeo[2:]).zfill(3),
                    "longitude": float(row[lon_col]),
                    "latitude": float(row[lat_col]),
                    "population": population,
                    "creation_week": creation_week,
                },
            )
        )
    return nodes, order


def _parse_population(value: object) -> int:
    population = pd.to_numeric(pd.Series([value]), errors="raise")[0]
    if pd.isna(population):
        raise ValueError("Population values cannot be empty.")
    population = int(population)
    if population < 0:
        raise ValueError("Population values cannot be negative.")
    return population


def _load_weighted_edges(
    adjacency_matrix_path: str | Path,
    node_order: list[str],
) -> list[tuple[str, str, float]]:
    csv_path = Path(adjacency_matrix_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Adjacency matrix file not found: {csv_path}")

    matrix = pd.read_csv(csv_path, index_col=0)
    matrix.index = pd.Index([normalize_cvegeo(v) for v in matrix.index], name="CVEGEO")
    matrix.columns = [normalize_cvegeo(v) for v in matrix.columns]
    matrix = matrix.apply(pd.to_numeric, errors="coerce")

    expected = set(node_order)
    row_set = set(matrix.index)
    col_set = set(matrix.columns)
    if row_set != expected or col_set != expected:
        raise ValueError(
            "Adjacency matrix nodes do not match edge list nodes. "
            f"rows={len(row_set)} cols={len(col_set)} expected={len(expected)}"
        )

    matrix = matrix.loc[node_order, node_order]
    matrix_values = matrix.to_numpy(dtype=float)

    edges: list[tuple[str, str, float]] = []
    n = len(node_order)
    for i in range(n):
        u = node_order[i]
        for j in range(i + 1, n):
            value = float(matrix_values[i, j])
            if not np.isnan(value) and value > 0.0:
                v = node_order[j]
                edges.append((u, v, value))
    return edges


def _series_value(values, cvegeo: str) -> float:
    return float(values[cvegeo]) if cvegeo in values.index else 0.0


def _build_week_graph(
    week: str,
    feature_rows: dict[str, object],
    mortality_values: object,
    nodes: list[tuple[str, dict]],
    edges: list[tuple[str, str, float]],
    feature_names: list[str],
) -> nx.Graph:
    G = nx.Graph()
    exogenous_feature_names = [*feature_names, EXISTS_ATTRIBUTE_NAME]
    endogenous_feature_names = [MORTALITY_ATTRIBUTE_NAME]
    existing_nodes: set[str] = set()

    G.graph.update(
        {
            "feature_names": feature_names,
            "epidemiological_week": week,
            "exogenous_variables": exogenous_feature_names,
            "endogenous_variables": endogenous_feature_names,
            "static_attributes": list(STATIC_ATTRIBUTE_NAMES),
            "node_attributes": [
                *exogenous_feature_names,
                *endogenous_feature_names,
                *STATIC_ATTRIBUTE_NAMES,
            ],
        }
    )

    for cvegeo, base_attrs in nodes:
        attrs = dict(base_attrs)
        creation_week = attrs.pop("creation_week")
        if week < creation_week:
            continue
        for feature_name in feature_names:
            feature_value = _series_value(feature_rows[feature_name], cvegeo)
            attrs[feature_name] = feature_value
        attrs[EXISTS_ATTRIBUTE_NAME] = True
        attrs[MORTALITY_ATTRIBUTE_NAME] = _series_value(mortality_values, cvegeo)
        G.add_node(cvegeo, **attrs)
        existing_nodes.add(cvegeo)

    G.add_edges_from(
        (u, v, {"weight": w})
        for u, v, w in edges
        if u in existing_nodes and v in existing_nodes
    )
    return G


def build_graphs(
    feature_files: Iterable[str | Path] | None = None,
    start_week: str | int | None = None,
    end_week: str | int | None = None,
    weeks: Iterable[str | int] | None = None,
) -> dict[str, nx.Graph]:
    """
    Build one municipal weighted graph per epidemiological week.

    By default this builds all bundled weeks from ``2003/01`` through
    ``2024/52`` using all bundled weekly municipality feature tables in
    ``graphari/data`` plus topology from ``edges.csv`` and
    ``adjacency_matrix.csv``.
    """
    edge_list_path = Path(DEFAULT_EDGES_CSV)
    adjacency_matrix_path = Path(DEFAULT_ADJACENCY_MATRIX_CSV)

    nodes, node_order = _load_nodes(edge_list_path)
    if EXPECTED_NODE_COUNT is not None and len(nodes) != EXPECTED_NODE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_NODE_COUNT} municipality nodes, got {len(nodes)} from {edge_list_path}."
        )

    feature_files_list = list(feature_files) if feature_files is not None else None
    feature_tables = load_feature_tables(
        feature_files=feature_files_list,
        start_week=start_week,
        end_week=end_week,
        weeks=weeks,
    )
    mortality_table = load_feature_table(
        MORTALITY_RATES_CSV,
        start_week=start_week,
        end_week=end_week,
        weeks=weeks,
    )

    feature_names = list(feature_tables.keys())
    week_index = feature_tables[feature_names[0]].index
    if not mortality_table.index.equals(week_index):
        raise ValueError("mortality_rates.csv weeks are not aligned with feature tables.")

    reference_columns = feature_tables[feature_names[0]].columns
    if not mortality_table.columns.equals(reference_columns):
        mortality_table = mortality_table.reindex(columns=reference_columns, fill_value=0.0)

    edges = _load_weighted_edges(adjacency_matrix_path, node_order)

    graphs: dict[str, nx.Graph] = {}
    for week in week_index:
        feature_rows = {name: df.loc[week] for name, df in feature_tables.items()}
        mortality_values = mortality_table.loc[week]
        graphs[week] = _build_week_graph(
            week=week,
            feature_rows=feature_rows,
            mortality_values=mortality_values,
            nodes=nodes,
            edges=edges,
            feature_names=feature_names,
        )
    return graphs


def build_graph(
    feature_files: Iterable[str | Path] | None = None,
    week: str | int | None = None,
) -> nx.Graph | dict[str, nx.Graph]:
    """
    Build weekly graphs, or a single graph when ``week`` is provided.
    """

    if week is not None:
        normalized_week = normalize_epiweek(week)
        return build_graphs(
            feature_files=feature_files,
            weeks=[normalized_week],
        )[normalized_week]
    
    raise ValueError("week must be provided to build a single graph.")


def get_node_feature_matrix(G: nx.Graph) -> tuple[np.ndarray, list[str]]:
    """Return ``(X, node_order)`` where ``X`` has shape ``(n_nodes, n_features)``."""
    node_order = list(G.nodes())
    feature_names = G.graph.get("feature_names", [])
    X = np.stack(
        [[G.nodes[n].get(feature, 0.0) for feature in feature_names] for n in node_order],
        axis=0,
    )
    return X, node_order


def get_edge_index(
    G: nx.Graph,
    node_order: list[str] | None = None,
) -> np.ndarray:
    """
    Return a COO edge index with both edge directions included.

    Shape is ``(2, num_edges * 2)``.
    """
    if node_order is None:
        node_order = list(G.nodes())
    node_to_idx = {n: i for i, n in enumerate(node_order)}
    src, dst = [], []
    for u, v in G.edges():
        i, j = node_to_idx[u], node_to_idx[v]
        src += [i, j]
        dst += [j, i]
    return np.array([src, dst], dtype=np.int64)
