"""
mexari
======
Spatio-temporal NetworkX graph of ARI mortality rates
across Mexican municipalities.

Quick start
-----------
>>> import mexari
>>> geojson_path = "/path/to/mexico.geojson"
>>> G = mexari.build_graph(geojson_path)
>>> G = mexari.build_graph(geojson_path, date="2020/01")
>>> X, order = mexari.get_node_feature_matrix(G)
>>> edge_index = mexari.get_edge_index(G, order)
"""

from mexari._graph import (
    build_graph,
    get_node_feature_matrix,
    get_edge_index,
)
from mexari._data import DEFAULT_CSV

__version__ = "0.1.0"
__author__ = "Alessandro Milan Ortega"
__all__ = [
    "build_graph",
    "get_node_feature_matrix",
    "get_edge_index",
    "DEFAULT_CSV",
]
