# Graph-ARI

Graph-ARI provides `graphari`, a Python package for building dynamic weekly municipal graphs for geostatistical analysis in Mexico.

The package transforms bundled municipality-level weekly covariates and topology into `networkx.Graph` objects where:

- nodes are municipalities (`CVEGEO`)
- edges represent municipal adjacency with distance-based weight
- node attributes combine dynamic exogenous variables, mortality rate, and static metadata
- municipality existence is dynamic over time (a municipality appears only on/after its `creation_week`)

This README follows the complete workflow shown in `notebooks/visaulize.ipynb`.

## Installation

```bash
pip install .
```

Requires Python 3.10+.

## What Is Bundled

Main weekly feature tables in `graphari/data`:

- `2m_mean_dewpoint_temperature.csv`
- `2m_mean_temperature.csv`
- `2m_relative_humidity.csv`
- `total_precipitation.csv`
- `10m_wind_speed.csv`

Topology and metadata tables:

- `edges.csv`: municipality identifiers, names, centroid coordinates, population, creation week
- `adjacency_matrix.csv`: municipal adjacency matrix with distance-based edge weights
- `mortality_rates.csv`: weekly mortality rate per municipality
- `Epidemiological_Weeks.csv`: epidemiological week helper table

Default data span:

- weeks: `2003/01` through `2024/52`
- municipalities: 2,478
- weekly snapshots: 1,148

## Public API

`graphari` exposes the following top-level functions:

- `available_feature_tables()`
- `available_epiweeks()`
- `load_feature_tables(...)`
- `build_graph(...)`
- `build_graphs(...)`
- `get_node_feature_matrix(...)`
- `get_edge_index(...)`

## Complete Usage Walkthrough

### 1. Discover available tables and epidemiological weeks

```python
import graphari as ga

tables = ga.available_feature_tables()
weeks = ga.available_epiweeks()

print(tables)
print(len(weeks), weeks[:5], weeks[-5:])
```

### 2. Build one weekly graph and a time window of graphs

```python
focus_week = "2024/34"
window_start = "2024/01"
window_end = "2024/52"

G = ga.build_graph(week=focus_week)
graphs_window = ga.build_graphs(start_week=window_start, end_week=window_end)

print(G.number_of_nodes(), G.number_of_edges())
print(len(graphs_window), list(graphs_window)[:3], list(graphs_window)[-3:])
```

### 3. Inspect graph-level metadata

```python
summary = {
    "epidemiological_week": G.graph["epidemiological_week"],
    "feature_names": G.graph["feature_names"],
    "exogenous_variables": G.graph["exogenous_variables"],
    "endogenous_variables": G.graph["endogenous_variables"],
    "static_attributes": G.graph["static_attributes"],
    "node_attributes": G.graph["node_attributes"],
}

summary
```

Expected structure:

- `feature_names`: exogenous variables used for model-ready `X`
- `exogenous_variables`: `feature_names + ["exists"]`
- `endogenous_variables`: `["mortality_rate"]`
- `static_attributes`: `["population", "latitude", "longitude"]`

### 4. Verify dynamic municipality creation

Municipality `24059` is absent before `2024/30` and present from `2024/30` onward.

```python
for week in ["2024/29", "2024/30", "2024/31"]:
    Gw = ga.build_graph(week=week)
    print(week, "present" if "24059" in Gw else "absent", Gw.number_of_nodes())
```

### 5. Inspect node and edge attributes

```python
node = "24059" if "24059" in G else "24028"
attrs = G.nodes[node]
neighbor = next(iter(G.neighbors(node)))
edge_attrs = G.edges[(node, neighbor)]

print(node)
print(attrs)
print(edge_attrs)
```

Typical node attributes include:

- climate variables (`2m_mean_temperature`, `total_precipitation`, etc.)
- `mortality_rate`
- `population`, `latitude`, `longitude`
- municipality identifiers and names (`cvegeo`, `state`, `municipality`, ...)
- `exists=True`

Each edge includes:

- `weight`: centroid-distance-based weight from `adjacency_matrix.csv`

### 6. Build model-ready tensors from a graph

```python
X, node_order = ga.get_node_feature_matrix(G)
edge_index = ga.get_edge_index(G, node_order)

print("X shape:", X.shape)                  # (n_nodes, n_features)
print("edge_index shape:", edge_index.shape)  # (2, 2 * n_edges)
print("first nodes:", node_order[:5])
```

- `X[i]` corresponds to node `node_order[i]`
- `edge_index` is COO format with both directions `(u, v)` and `(v, u)`

### 7. Load raw weekly tables directly (pandas workflow)

```python
tables = ga.load_feature_tables(start_week="2024/01", end_week="2024/52")

print(list(tables.keys()))
temperature = tables["2m_mean_temperature"]
print(temperature.shape)
print(temperature.iloc[:3, :3])
```

This is useful when you want table-based preprocessing before graph construction.

### 8. Build graphs with a custom feature subset

```python
subset_graph = ga.build_graph(
    week="2024/34",
    feature_files=["2m_mean_temperature", "total_precipitation"],
)

print(subset_graph.graph["feature_names"])
subset_X, subset_order = ga.get_node_feature_matrix(subset_graph)
print(subset_X.shape)
```

Use this to control feature dimensionality for experiments.

## Detailed Example: Time Dynamics and Visualization

The notebook includes exploratory plots; below is a direct adaptation you can run in scripts or notebooks.

### Dynamic graph size over a time window

```python
import matplotlib.pyplot as plt
import pandas as pd
import graphari as ga

focus_node = "24059"
graphs = ga.build_graphs(start_week="2024/01", end_week="2024/52")

node_counts = pd.DataFrame(
    {
        "week": list(graphs.keys()),
        "node_count": [g.number_of_nodes() for g in graphs.values()],
        "focus_node_present": [focus_node in g for g in graphs.values()],
    }
)

fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(node_counts["week"], node_counts["node_count"], marker="o", linewidth=2)
ax.set_title("Dynamic number of municipalities per week")
ax.set_xlabel("Epidemiological week")
ax.set_ylabel("Number of nodes")
ax.tick_params(axis="x", rotation=90)

first_presence = node_counts[node_counts["focus_node_present"]].head(1)
for _, row in first_presence.iterrows():
    ax.axvline(row["week"], color="crimson", linestyle="--", alpha=0.8)
    ax.text(row["week"], row["node_count"] + 0.1, f"{focus_node} appears", color="crimson")

plt.tight_layout()
```

### Municipality-level time series from graph node attributes

```python
import matplotlib.pyplot as plt
import pandas as pd
import graphari as ga

stable_node = "24028"
graphs = ga.build_graphs(start_week="2024/01", end_week="2024/52")

rows = []
for week, g in graphs.items():
    if stable_node not in g:
        continue
    n = g.nodes[stable_node]
    rows.append(
        {
            "week": week,
            "mortality_rate": n["mortality_rate"],
            "temperature": n["2m_mean_temperature"],
            "precipitation": n["total_precipitation"],
            "humidity": n["2m_relative_humidity"],
            "wind_speed": n["10m_wind_speed"],
        }
    )

df = pd.DataFrame(rows)

fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
axes[0].plot(df["week"], df["mortality_rate"], marker="o", color="crimson")
axes[0].set_title(f"Mortality rate for municipality {stable_node}")
axes[0].set_ylabel("Mortality rate")

axes[1].plot(df["week"], df["temperature"], marker="o", label="Temperature")
axes[1].plot(df["week"], df["precipitation"], marker="o", label="Precipitation")
axes[1].plot(df["week"], df["humidity"], marker="o", label="Humidity")
axes[1].plot(df["week"], df["wind_speed"], marker="o", label="10m Wind Speed")
axes[1].set_title(f"Exogenous variables for municipality {stable_node}")
axes[1].set_xlabel("Epidemiological week")
axes[1].set_ylabel("Value")
axes[1].legend()
axes[1].tick_params(axis="x", rotation=90)

plt.tight_layout()
```

### One-hop ego network map using municipality latitude/longitude

```python
import matplotlib.pyplot as plt
import networkx as nx
import graphari as ga

G = ga.build_graph(week="2024/34")
center_node = "24028"
ego = nx.ego_graph(G, center_node, radius=1)

positions = {
    node: (ego.nodes[node]["longitude"], ego.nodes[node]["latitude"])
    for node in ego.nodes()
}
node_colors = [ego.nodes[node]["mortality_rate"] for node in ego.nodes()]
node_sizes = [max(80, ego.nodes[node]["population"] / 1000) for node in ego.nodes()]

fig, ax = plt.subplots(figsize=(8, 6))
nx.draw_networkx_edges(ego, positions, alpha=0.35, ax=ax)
nodes = nx.draw_networkx_nodes(
    ego,
    positions,
    node_color=node_colors,
    node_size=node_sizes,
    cmap="rainbow",
    edgecolors="black",
    linewidths=0.5,
    ax=ax,
)
nx.draw_networkx_labels(ego, positions, font_size=9, ax=ax)

ax.set_title(f"Ego network around municipality {center_node} in 2024/34")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_aspect("equal", adjustable="datalim")
cbar = plt.colorbar(nodes, ax=ax)
cbar.set_label("Mortality rate")

plt.tight_layout()
```

## Notes and Validation

- Epidemiological week format is normalized as `YYYY/WW`.
- `build_graph(week=...)` requires a valid week present in the bundled data.
- `feature_files` can be passed with or without `.csv` extension.
- All selected feature tables are aligned by week and municipality columns.

## Notebook

For the full executable walkthrough, open:

- `notebooks/visaulize.ipynb`
