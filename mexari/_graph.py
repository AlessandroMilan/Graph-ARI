"""
mexari._graph
=============
Core graph construction for the mexari package.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional, Union

import networkx as nx
import numpy as np
import pandas as pd
from shapely.geometry import shape
from shapely.strtree import STRtree

from mexari._data import DEFAULT_CSV


def _load_geojson(path: Union[str, Path]) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["features"]


def _load_mortality(
    path: Union[str, Path],
    dates: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, dtype=str)
    df = df.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    if dates is not None:
        dates = list(dates)
        df = df.loc[df.index.isin(dates)]
    return df


def _build_adjacency(features: list[dict]) -> list[tuple[str, str]]:
    geometries = [shape(f["geometry"]) for f in features]
    cvegeos = [f["properties"]["CVEGEO"] for f in features]
    tree = STRtree(geometries)
    edges: set[frozenset] = set()
    for i, geom in enumerate(geometries):
        for j in tree.query(geom):
            if i == j:
                continue
            if geom.touches(geometries[j]) or (
                geom.intersects(geometries[j]) and not geom.touches(geometries[j])
            ):
                edges.add(frozenset({i, j}))
    return [(cvegeos[min(pair)], cvegeos[max(pair)]) for pair in edges]


def _centroid(feature: dict) -> tuple[float, float]:
    pt = shape(feature["geometry"]).centroid
    return pt.x, pt.y


def build_graph(
    geojson_path: Union[str, Path],
    csv_path: Union[str, Path] = DEFAULT_CSV,
    date: Optional[str] = None,
    dates: Optional[Iterable[str]] = None,
) -> nx.Graph:
    """
    Build and return a NetworkX spatio-temporal graph of Mexican municipalities.

    Nodes
    -----
    Key: CVEGEO string (e.g. "01001").
    Attributes: cvegeo, mun_name, state_name, cve_ent, cve_mun,
                lon, lat, mortality (dict), features (np.ndarray).

    Edges
    -----
    Undirected spatial adjacency edges. weight=1.0 on every edge.

    Parameters
    ----------
    geojson_path : path-like, required – municipality geometries supplied by caller.
    csv_path     : path-like, optional – defaults to bundled mortality rates.
    date  : str, optional – single snapshot "YYYY/MM".
    dates : iterable of str, optional – subset of dates.

    Examples
    --------
    >>> from pathlib import Path
    >>> import mexari
    >>> geojson_path = Path("/path/to/mexico.geojson")
    >>> G = mexari.build_graph(geojson_path)
    >>> G = mexari.build_graph(geojson_path, date="2020/01")
    """
    if date is not None and dates is not None:
        raise ValueError("Specify either date or dates, not both.")
    if date is not None:
        dates = [date]

    geojson_path, csv_path = Path(geojson_path), Path(csv_path)
    if not geojson_path.exists():
        raise FileNotFoundError(f"GeoJSON not found: {geojson_path}")
    if not csv_path.exists():
        raise FileNotFoundError(f"Mortality CSV not found: {csv_path}")

    features = _load_geojson(geojson_path)
    mortality_df = _load_mortality(csv_path, dates=dates)
    available_dates: list[str] = list(mortality_df.index)

    G = nx.Graph()
    G.graph["dates"] = available_dates
    G.graph["source_geojson"] = str(geojson_path)
    G.graph["source_csv"] = str(csv_path)

    for feat in features:
        props = feat["properties"]
        cvegeo: str = props["CVEGEO"]
        lon, lat = _centroid(feat)
        if cvegeo in mortality_df.columns:
            mort_series: dict[str, float] = mortality_df[cvegeo].to_dict()
            feat_vector = mortality_df[cvegeo].to_numpy(dtype=np.float32)
        else:
            mort_series = {d: 0.0 for d in available_dates}
            feat_vector = np.zeros(len(available_dates), dtype=np.float32)
        G.add_node(
            cvegeo,
            cvegeo=cvegeo,
            mun_name=props.get("NOMGEO", ""),
            state_name=props.get("NOM_ENT", ""),
            cve_ent=props.get("CVE_ENT", ""),
            cve_mun=props.get("CVE_MUN", ""),
            lon=lon,
            lat=lat,
            mortality=mort_series,
            features=feat_vector,
        )

    for u, v in _build_adjacency(features):
        G.add_edge(u, v, weight=1.0)

    return G


def get_node_feature_matrix(G: nx.Graph) -> tuple[np.ndarray, list[str]]:
    """Return (X, node_order) where X has shape (n_nodes, n_features)."""
    node_order = list(G.nodes())
    X = np.stack([G.nodes[n]["features"] for n in node_order], axis=0)
    return X, node_order


def get_edge_index(
    G: nx.Graph,
    node_order: Optional[list[str]] = None,
) -> np.ndarray:
    """
    Return COO edge index compatible with PyTorch Geometric / DGL.
    Shape: (2, num_edges * 2) – both directions included.
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
