"""
mexari
======
Weekly municipal NetworkX graphs for geostatistical analysis of ARI mortality
and climate covariates in Mexico.

Quick start
-----------
>>> import mexari
>>> graphs = mexari.build_graphs()
>>> G = graphs["2020/01"]
>>> X, order = mexari.get_node_feature_matrix(G)
>>> edge_index = mexari.get_edge_index(G, order)
"""

from mexari._data import (
    available_feature_tables,
    available_epiweeks,
    load_feature_table,
    load_feature_tables,
    normalize_cvegeo,
    normalize_epiweek,
)
from mexari._graph import (
    build_graph,
    build_graphs,
    get_edge_index,
    get_node_feature_matrix,
)

__version__ = "0.3.0"
__author__ = "Alessandro Milan Ortega"
__all__ = [
    "build_graph",
    "build_graphs",
    "get_node_feature_matrix",
    "get_edge_index",
    "load_feature_table",
    "load_feature_tables",
    "available_feature_tables",
    "available_epiweeks",
    "normalize_epiweek",
    "normalize_cvegeo",
]
