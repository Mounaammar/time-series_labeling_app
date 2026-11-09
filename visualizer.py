import argparse
import json
import random

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

DATASET = "data/graph_nodes.json"
LABELS = "data/labels.json"

LABEL_COLORS = {
    "stable":                "#9E9E9E",
    "linear_increase":       "#2196F3",
    "linear_decrease":       "#FF5722",
    "accelerating_increase": "#4CAF50",
    "decelerating_increase": "#8BC34A",
    "accelerating_decrease": "#F44336",
    "decelerating_decrease": "#FF9800",
}


def load_data():
    with open(DATASET) as f:
        nodes = json.load(f)
    with open(LABELS) as f:
        labels = json.load(f)
    return nodes, labels


def visualize(node_id=None, metric=None):
    nodes, labels = load_data()

    # mapping here
    node_map = {n["station_id"]: n for n in nodes}
    labeled_sids = [sid for sid in labels if any(labels[sid].values())]

    # select metric and sid
    if node_id is None and metric is None:
        sid = random.choice(labeled_sids)
        available = [m for m in labels[sid] if labels[sid][m]]
        metric = random.choice(available)
    elif node_id is None:
        candidates = [
            sid for sid in labeled_sids
            if metric in labels[sid] and labels[sid][metric]
        ]
        if not candidates:
            print(f"No labeled series found for metric '{metric}'")
            return
        sid = random.choice(candidates)
    elif metric is None:
        if node_id not in labels:
            print(f"No labels found for node '{node_id}'")
            return
        available = [m for m in labels[node_id] if labels[node_id][m]]
        if not available:
            print(f"No labeled metrics for node '{node_id}'")
            return
        metric = random.choice(available)
        sid = node_id
    else:
        sid = node_id

    if sid not in node_map:
        print(f"Node '{sid}' not found in dataset")
        return
    node = node_map[sid]
    ts_data = node["ts"].get(metric)
    if not ts_data:
        print(f"Metric '{metric}' not found for node '{sid}'")
        return

    values = [entry["Value"] for entry in ts_data]
    series_labels = labels.get(sid, {}).get(metric, {})
    n = len(values)

    # create plot for visualization

    fig, (ax_ts, ax_bar) = plt.subplots(
        2, 1,
        figsize=(14, 5),
        gridspec_kw={"height_ratios": [6, 1]},
        sharex=True,
    )

    ax_ts.plot(range(n), values, color="#1565C0", linewidth=1.0)
    ax_ts.set_title(f"{node.get('name', sid)}  —  {metric.replace('_', ' ')}", fontsize=11)
    ax_ts.set_ylabel("Value")
    ax_ts.set_xlim(0, n)
    ax_ts.grid(True, alpha=0.25)

    for window, label_name in series_labels.items():
        i0, i1 = map(int, window.split(":"))
        color = LABEL_COLORS.get(label_name, "#CCCCCC")
        ax_ts.axvspan(i0, i1, color=color, alpha=0.25, linewidth=0)
        ax_bar.barh(0, i1 - i0, left=i0, height=1.0, color=color, edgecolor="white", linewidth=0.3)

    ax_bar.set_ylim(-0.5, 0.5)
    ax_bar.set_yticks([])
    ax_bar.set_xlabel("Index")

    label_order = list(LABEL_COLORS.keys())
    present = sorted(
        {v for v in series_labels.values()},
        key=lambda lbl: label_order.index(lbl) if lbl in label_order else 999,
    )
    legend_patches = [
        mpatches.Patch(color=LABEL_COLORS.get(lbl, "#CCCCCC"), label=lbl.replace("_", " "))
        for lbl in present
    ]
    if legend_patches:
        ax_bar.legend(
            handles=legend_patches,
            loc="upper right",
            fontsize=7,
            ncol=len(legend_patches),
            framealpha=0.8,
        )

    plt.tight_layout(h_pad=0.5)
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize a labeled time-series")
    parser.add_argument("--node", default=None, help="Station ID")
    parser.add_argument("--metric", default=None, help="Metric name (e.g. num_bikes_available)")
    args = parser.parse_args()
    # change node id or metric to view specific time-series or even one specific time-series
    # smoothing is not applied here
    visualize(node_id=args.node, metric=args.metric)
