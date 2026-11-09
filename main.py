import json
from datetime import datetime
from pathlib import Path

import numpy as np
import tkinter as tk

from labeler_app import LabelerApp

INPUT_JSON = "data/graph_nodes.json"
LABEL_JSON = "data/labels.json"


def _parse(ts: list) -> tuple:
    timestamps = [datetime.fromisoformat(x["Start"]) for x in ts]
    values = np.array([x["Value"] for x in ts], dtype=float)
    return timestamps, values


print("Loading data…")
with open(INPUT_JSON) as f:
    data = json.load(f)

if Path(LABEL_JSON).exists():
    with open(LABEL_JSON) as f:
        label_db = json.load(f)
else:
    label_db = {}


def save():
    with open(LABEL_JSON, "w") as f:
        json.dump(label_db, f, indent=2)


series_list = []
for i, item in enumerate(data):
    sid = item.get("id", item.get("station_id", f"series_{i}"))
    for metric, ts in item["ts"].items():
        if len(ts) < 2:
            continue
        timestamps, values = _parse(ts)
        series_list.append((sid, metric, timestamps, values))

print(f"Ready — {len(series_list)} series to label.")

root = tk.Tk()
LabelerApp(root, series_list, label_db, save)
root.mainloop()
