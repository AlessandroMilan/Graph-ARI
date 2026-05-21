# Graph-ARI

Graph-ARI provides `graphari`, a lightweight Python package for building weekly municipal adjacency graphs for geostatistical analysis in Mexico.

The package reads all bundled weekly municipality feature tables from `graphari/data`:

- `2m_mean_dewpoint_temperature`
- `2m_mean_temperature`
- `2m_relative_humidity`
- `total_precipitation`

It also bundles topology and static municipality metadata files:

- `edges` (municipality node metadata and centroids)
- `adjacency_matrix` (distance-weighted municipal adjacency)
- `municipalities` (municipality creation week and population)
- `Epidemiological_Weeks` (helper file)

## Data

The bundled weekly feature tables cover epidemiological weeks `2003/01` through `2024/52` and have one column per municipality `CVEGEO` code. The default period contains 1,148 weekly observations across 2,478 municipalities.

`graphari` builds graph topology from `edges` and `adjacency_matrix`. Edge weights are centroid distances for adjacent municipalities. Each node includes the exogenous weekly variables plus `population`, `latitude`, `longitude`, and `exists`; `exists` is computed per graph from the municipality creation week in `municipalities`.

## Usage

```python
import graphari as ga

graphs = ga.build_graphs()
len(graphs)  # 1148 by default

G = graphs["2020/01"]
G.number_of_nodes()  # 2478 with the full municipal topology files
G.graph["feature_names"]
# ["2m_mean_dewpoint_temperature", "2m_mean_temperature", "2m_relative_humidity", "total_precipitation"]
G.graph["static_attribute_names"]
# ["population", "latitude", "longitude", "exists"]
G.nodes["23009"]["exists"]  # True for Tulum in 2020/01
G.nodes["23009"]["population"]  # 46721

X, node_order = ga.get_node_feature_matrix(G)
edge_index = ga.get_edge_index(G, node_order)
```

Build an inclusive period instead of the full default span:

```python
graphs = ga.build_graphs(
    start_week="2018/01",
    end_week="2020/52",
)
```

Or build one graph:

```python
G = ga.build_graph(week="2024/52")
```

Load all tables directly:

```python
tables = ga.load_feature_tables()
tables.keys()
```

Use a custom feature subset:

```python
graphs = ga.build_graphs(
    feature_files=["2m_mean_temperature", "total_precipitation"],
    start_week="2020/01",
    end_week="2020/52",
)
```
