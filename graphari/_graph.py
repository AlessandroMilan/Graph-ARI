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
    load_feature_tables,
    normalize_cvegeo,
    normalize_epiweek,
)

EXPECTED_NODE_COUNT = 2478


def _load_nodes(edge_list_path: str | Path) -> tuple[list[tuple[str, dict]], list[str]]:
    csv_path = Path(edge_list_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Edge list file not found: {csv_path}")

    df = pd.read_csv(csv_path, dtype={"CVEGEO": str, "CVE_ENT": str, "CVE_MUN": str})
    required_columns = {
        "CVEGEO",
        "CVE_ENT",
        "CVE_MUN",
        "NOMGEO",
        "NOMMUN",
        "centroid_lon",
        "centroid_lat",
    }
    missing = sorted(required_columns - set(df.columns))
    if missing:
        raise ValueError(
            f"Edge list CSV is missing required columns: {', '.join(missing)}"
        )

    nodes: list[tuple[str, dict]] = []
    order: list[str] = []
    seen: set[str] = set()
    for row in df.itertuples(index=False):
        cvegeo = normalize_cvegeo(getattr(row, "CVEGEO"))
        if cvegeo in seen:
            raise ValueError(f"Duplicate CVEGEO in edge list CSV: {cvegeo}")
        seen.add(cvegeo)
        order.append(cvegeo)

        nodes.append(
            (
                cvegeo,
                {
                    "cvegeo": cvegeo,
                    "municipality": str(getattr(row, "NOMMUN", "") or ""),
                    "state": str(getattr(row, "NOMGEO", "") or ""),
                    "cve_ent": str(getattr(row, "CVE_ENT", cvegeo[:2]) or cvegeo[:2]).zfill(2),
                    "cve_mun": str(getattr(row, "CVE_MUN", cvegeo[2:]) or cvegeo[2:]).zfill(3),
                    "longitude": float(getattr(row, "centroid_lon")),
                    "latitude": float(getattr(row, "centroid_lat")),
                },
            )
        )
    return nodes, order


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
    *,
    week: str,
    feature_rows: dict[str, object],
    nodes: list[tuple[str, dict]],
    edges: list[tuple[str, str, float]],
    edge_list_path: Path,
    adjacency_matrix_path: Path,
    source_csvs: dict[str, str],
    feature_names: list[str],
) -> nx.Graph:
    G = nx.Graph()

    G.graph.update(
        {
            "epidemiological_week": week,
            "feature_names": feature_names,
        }
    )

    for cvegeo, base_attrs in nodes:
        attrs = dict(base_attrs)
        for feature_name in feature_names:
            feature_value = _series_value(feature_rows[feature_name], cvegeo)
            attrs[feature_name] = feature_value

        G.add_node(cvegeo, **attrs)

    G.add_edges_from((u, v, {"weight": w}) for u, v, w in edges)
    return G


def build_graphs(
    edge_list_path: str | Path = DEFAULT_EDGES_CSV,
    adjacency_matrix_path: str | Path = DEFAULT_ADJACENCY_MATRIX_CSV,
    *,
    data_dir: str | Path = DATA_DIR,
    feature_files: Iterable[str | Path] | None = None,
    start_week: str | int | None = None,
    end_week: str | int | None = None,
    weeks: Iterable[str | int] | None = None,
    expected_nodes: int | None = EXPECTED_NODE_COUNT,
) -> dict[str, nx.Graph]:
    """
    Build one municipal weighted graph per epidemiological week.

    By default this builds all bundled weeks from ``2003/01`` through
    ``2024/52`` using all bundled weekly municipality feature tables in
    ``mexari/data`` plus topology from ``edges.csv`` and
    ``adjacency_matrix.csv``. Pass ``start_week``/``end_week`` for an inclusive
    period, or ``weeks`` for an explicit list of epidemiological weeks.
    """
    edge_list_path = Path(edge_list_path)
    adjacency_matrix_path = Path(adjacency_matrix_path)

    nodes, node_order = _load_nodes(edge_list_path)
    if expected_nodes is not None and len(nodes) != expected_nodes:
        raise ValueError(
            f"Expected {expected_nodes} municipality nodes, got {len(nodes)} from {edge_list_path}."
        )

    feature_files_list = list(feature_files) if feature_files is not None else None
    feature_tables = load_feature_tables(
        data_dir=data_dir,
        feature_files=feature_files_list,
        start_week=start_week,
        end_week=end_week,
        weeks=weeks,
    )
    feature_names = list(feature_tables.keys())
    week_index = feature_tables[feature_names[0]].index
    source_csvs = {
        name: str(Path(data_dir) / f"{name}.csv") for name in feature_names
    }
    if feature_files_list is not None:
        source_csvs = {}
        for file_path, feature_name in zip(feature_files_list, feature_names):
            candidate = Path(file_path)
            if not candidate.is_absolute():
                candidate = Path(data_dir) / candidate
            source_csvs[feature_name] = str(candidate)

    edges = _load_weighted_edges(adjacency_matrix_path, node_order)

    graphs: dict[str, nx.Graph] = {}
    for week in week_index:
        feature_rows = {name: df.loc[week] for name, df in feature_tables.items()}
        graphs[week] = _build_week_graph(
            week=week,
            feature_rows=feature_rows,
            nodes=nodes,
            edges=edges,
            edge_list_path=edge_list_path,
            adjacency_matrix_path=adjacency_matrix_path,
            source_csvs=source_csvs,
            feature_names=feature_names,
        )
    return graphs


def build_graph(
    edge_list_path: str | Path = DEFAULT_EDGES_CSV,
    adjacency_matrix_path: str | Path = DEFAULT_ADJACENCY_MATRIX_CSV,
    *,
    data_dir: str | Path = DATA_DIR,
    feature_files: Iterable[str | Path] | None = None,
    week: str | int | None = None,
    date: str | int | None = None,
    start_week: str | int | None = None,
    end_week: str | int | None = None,
    weeks: Iterable[str | int] | None = None,
    expected_nodes: int | None = EXPECTED_NODE_COUNT,
) -> nx.Graph | dict[str, nx.Graph]:
    """
    Build weekly graphs, or a single graph when ``week`` is provided.

    ``date`` is accepted as a legacy alias for ``week``.
    """
    if date is not None:
        if week is not None:
            raise ValueError("Specify either week or date, not both.")
        week = date

    if week is not None:
        if weeks is not None or start_week is not None or end_week is not None:
            raise ValueError("Specify either a single week or a period, not both.")
        normalized_week = normalize_epiweek(week)
        return build_graphs(
            edge_list_path,
            adjacency_matrix_path,
            data_dir=data_dir,
            feature_files=feature_files,
            weeks=[normalized_week],
            expected_nodes=expected_nodes,
        )[normalized_week]

    return build_graphs(
        edge_list_path,
        adjacency_matrix_path,
        data_dir=data_dir,
        feature_files=feature_files,
        start_week=start_week,
        end_week=end_week,
        weeks=weeks,
        expected_nodes=expected_nodes,
    )


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
