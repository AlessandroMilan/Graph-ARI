"""
graphari
========
Weekly municipal NetworkX graphs for geostatistical analysis of ARI mortality
and climate covariates in Mexico.

Quick start
-----------
>>> import graphari
>>> graphs = graphari.build_graphs()
>>> G = graphs["2020/01"]
>>> X, order = graphari.get_node_feature_matrix(G)
>>> edge_index = graphari.get_edge_index(G, order)
"""

from graphari._data import (
    available_feature_tables,
    available_epiweeks,
    load_feature_tables,
)
from graphari._graph import (
    build_graph,
    build_graphs,
    get_edge_index,
    get_node_feature_matrix,
)

__version__ = "1.0"
__author__ = "Hector Alessandro Milan"
__all__ = [
    "build_graph",
    "build_graphs",
    "get_node_feature_matrix",
    "get_edge_index",
    "load_feature_tables",
    "available_feature_tables",
    "available_epiweeks",
]
