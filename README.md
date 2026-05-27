# Graph-ARI

Graph-ARI provides `graphari`, a lightweight Python package for building weekly municipal adjacency graphs for geostatistical analysis in Mexico.

The package reads all bundled weekly municipality feature tables from `graphari/data`:

- `2m_mean_dewpoint_temperature`
- `2m_mean_temperature`
- `2m_relative_humidity`
- `total_precipitation`
- `10m_wind_speed`

It also bundles topology and static municipality metadata files:

- `edges` (municipality node metadata and centroids)
- `adjacency_matrix` (distance-weighted municipal adjacency)
- `municipalities` (municipality creation week and population)
- `Epidemiological_Weeks` (helper file)

## Data

The bundled weekly feature tables cover epidemiological weeks `2003/01` through `2024/52` and have one column per municipality `CVEGEO` code. The default period contains 1,148 weekly observations across 2,478 municipalities.

`graphari` builds dynamic graph topology from `edges` and `adjacency_matrix`. Edge weights are centroid distances for adjacent municipalities. Municipalities are only included in a weekly graph on or after their `creation_week`. Each included node contains the exogenous weekly variables plus `mortality_rate`, `population`, `latitude`, `longitude`, and `exists`.

## Usage

```python
import graphari as ga

graphs = ga.build_graphs()
len(graphs)  # 1148 by default

G = graphs["2020/01"]
G.number_of_nodes()  # Varies by week; only municipalities that already exist are included
G.graph["feature_names"]
# ["2m_mean_dewpoint_temperature", "2m_mean_temperature", "2m_relative_humidity", "total_precipitation", "10m_wind_speed"]
G.graph["endogenous_variables"]
# ["mortality_rate"]
G.graph["static_attributes"]
# ["population", "latitude", "longitude"]
G.nodes["23009"]["exists"]  # True for Tulum in 2020/01
G.nodes["23009"]["mortality_rate"]
G.nodes["23009"]["population"]  # 46721

"24059" in ga.build_graph(week="2024/29")
# False
"24059" in ga.build_graph(week="2024/30")
# True

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
