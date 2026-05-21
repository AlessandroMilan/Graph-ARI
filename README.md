# Graph-ARI

Graph-ARI provides `graphari`, a lightweight Python package for building weekly municipal adjacency graphs for geostatistical analysis in Mexico.

The package reads all bundled weekly municipality feature tables from `graphari/data`:

- `2m_mean_dewpoint_temperature.csv`
- `2m_mean_temperature.csv`
- `2m_relative_humidity.csv`
- `total_precipitation.csv`

It also bundles topology files:

- `edges.csv` (municipality node metadata and centroids)
- `adjacency_matrix.csv` (distance-weighted municipal adjacency)
- `Epidemiological_Weeks.csv` (helper file)

## Data

The bundled weekly feature tables cover epidemiological weeks `2003/01` through `2024/52` and have one column per municipality `CVEGEO` code. The default period contains 1,148 weekly observations across 2,478 municipalities.

`graphari` builds graph topology from `edges.csv` and `adjacency_matrix.csv`. Edge weights are centroid distances for adjacent municipalities.

## Usage

```python
import graphari as ga

graphs = ga.build_graphs()
len(graphs)  # 1148 by default

G = graphs["2020/01"]
G.number_of_nodes()  # 2478 with the full municipal topology files
G.graph["feature_names"]
# ["2m_mean_dewpoint_temperature", "2m_mean_temperature", "2m_relative_humidity", "total_precipitation"]

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
