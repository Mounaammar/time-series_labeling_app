import matplotlib
matplotlib.use("TkAgg")

# Disable matplotlib's built-in key shortcuts
for _k in list(matplotlib.rcParams):
    if _k.startswith("keymap."):
        matplotlib.rcParams[_k] = []

import tkinter as tk
from tkinter import ttk

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# (key, label_name, button_color)
LABELS = [
    ("1", "stable",                "#757575"),
    ("2", "linear_increase",       "#388E3C"),
    ("3", "linear_decrease",       "#D32F2F"),
    ("4", "accelerating_increase", "#1565C0"),
    ("5", "decelerating_increase", "#689F38"),
    ("6", "accelerating_decrease", "#6A1B9A"),
    ("7", "decelerating_decrease", "#E65100"),
]

LABEL_COLOR = {name: color for _, name, color in LABELS}

_rng = np.random.default_rng(0)


def _make_reference_series():
    t = np.linspace(0, 1, 60)
    noise = _rng.normal(0, 0.06, 60)
    return [
        ("stable",                3.0 + noise),
        ("linear_increase",       1.0 + 4.0 * t),
        ("linear_decrease",       5.0 - 4.0 * t),
        ("accelerating_increase", 1.0 + 4.0 * t ** 2),
        ("decelerating_increase", 1.0 + 4.0 * np.sqrt(t)),
        ("accelerating_decrease", 5.0 - 4.0 * t ** 2),
        ("decelerating_decrease", 5.0 - 4.0 * np.sqrt(t)),
    ]


class LabelerApp:
    """
    Tkinter + matplotlib app for manually labeling time-series windows.

    series_list : list of (sid, metric, timestamps, values)
                  timestamps : list[datetime]
                  values     : np.ndarray[float]
    label_db    : dict modified in place;  structure:
                  { sid: { metric: { "i0:i1": label_name } } }
    save_fn     : callable() — persists label_db to disk
    """

    def __init__(self, root: tk.Tk, series_list: list, label_db: dict, save_fn):
        self.root = root
        self.series_list = series_list
        self.label_db = label_db
        self.save_fn = save_fn

        self.idx = 0
        self._selection: tuple[int, int] | None = None

        root.title("Time Series Labeler")
        root.geometry("1350x800")
        root.minsize(960, 620)
        root.protocol("WM_DELETE_WINDOW", self._quit)

        self._build_ui()
        self._load_series()
        self._bind_keys()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self._smooth_window = tk.IntVar(value=5)
        self._build_reference_panel()
        self._build_main_plot()
        self._build_status_bar()
        self._build_controls()

    def _build_reference_panel(self):
        outer = tk.LabelFrame(
            self.root,
            text="Reference shapes",
            font=("Arial", 9, "bold"),
            padx=4, pady=2,
        )
        outer.pack(fill="x", padx=8, pady=(6, 0))

        fig = Figure(figsize=(13.5, 1.55), dpi=88)
        r, g, b = outer.winfo_rgb(outer.cget("bg"))
        fig.patch.set_facecolor((r / 65535, g / 65535, b / 65535))

        refs = _make_reference_series()
        for col, (name, vals) in enumerate(refs, 1):
            ax = fig.add_subplot(1, 7, col)
            color = LABEL_COLOR[name]
            xs = np.arange(len(vals))
            ax.plot(xs, vals, color=color, linewidth=2.0)
            ax.fill_between(xs, vals, vals.min() - 0.05, alpha=0.18, color=color)

            short = (name
                     .replace("_increase", " ↑")
                     .replace("_decrease", " ↓")
                     .replace("_", " "))
            ax.set_title(f"[{col}] {short}", fontsize=7, pad=3, color="#222")
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_edgecolor(color)
                spine.set_linewidth(1.3)

        fig.subplots_adjust(left=0.005, right=0.995, top=0.78, bottom=0.02, wspace=0.16)

        canvas = FigureCanvasTkAgg(fig, outer)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="x")

    def _build_main_plot(self):
        frame = tk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=8, pady=4)

        self.fig = Figure(figsize=(13.5, 4.4), dpi=88)
        self.ax = self.fig.add_subplot(111)
        self.fig.subplots_adjust(left=0.06, right=0.995, top=0.90, bottom=0.20)

        self.canvas = FigureCanvasTkAgg(self.fig, frame)
        self.canvas.mpl_connect("button_press_event", self._on_click)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def _build_status_bar(self):
        bar = tk.Frame(self.root, bg="#e4e4e4")
        bar.pack(fill="x", padx=8)

        self._progress_var = tk.StringVar()
        tk.Label(
            bar, textvariable=self._progress_var,
            bg="#e4e4e4", font=("Arial", 9), anchor="w",
        ).pack(side="left", padx=8, pady=3)

        self._hint_var = tk.StringVar()
        tk.Label(
            bar, textvariable=self._hint_var,
            bg="#e4e4e4", font=("Arial", 9, "italic"), fg="#555", anchor="e",
        ).pack(side="right", padx=8, pady=3)

    def _build_controls(self):
        bar = tk.Frame(self.root, pady=6)
        bar.pack(fill="x", padx=8, pady=(0, 6))

        # -- Navigation --
        nav = tk.Frame(bar)
        nav.pack(side="left", padx=(0, 10))
        tk.Button(nav, text="◀  Prev", command=self._prev, width=9).pack(side="left", padx=2)
        tk.Button(nav, text="Next  ▶", command=self._next, width=9).pack(side="left", padx=2)

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=10)

        # -- Label buttons --
        lf = tk.Frame(bar)
        lf.pack(side="left")
        for key, name, color in LABELS:
            short = (name
                     .replace("_increase", " ↑")
                     .replace("_decrease", " ↓")
                     .replace("_", " "))
            tk.Button(
                lf,
                text=f"[{key}]  {short}",
                command=lambda n=name: self._apply_label(n),
                bg=color, fg="white",
                font=("Arial", 9, "bold"),
                relief="raised", bd=1,
                padx=6, pady=4,
            ).pack(side="left", padx=2)

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=10)

        sf = tk.Frame(bar)
        sf.pack(side="left")
        tk.Label(sf, text="Smooth:", font=("Arial", 9)).pack(side="left")
        tk.Scale(
            sf, from_=1, to=30, orient="horizontal",
            variable=self._smooth_window, length=120,
            command=lambda _: self._render(),
            showvalue=True, font=("Arial", 8),
        ).pack(side="left")

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=10)
        tk.Button(bar, text="Quit", command=self._quit,
                  fg="#bb0000", font=("Arial", 9)).pack(side="left", padx=2)

    def _bind_keys(self):
        for key, name, _ in LABELS:
            self.root.bind_all(f"<Key-{key}>", lambda e, n=name: self._apply_label(n))
        self.root.bind_all("<Right>", lambda e: self._next())
        self.root.bind_all("<Left>", lambda e: self._prev())
        self.root.bind_all("<Escape>", lambda e: self._quit())

    # ------------------------------------------------------------------
    # Smoothing
    # ------------------------------------------------------------------

    def _smooth(self, values: np.ndarray) -> np.ndarray:
        w = self._smooth_window.get()
        if w <= 1:
            return values
        kernel = np.ones(w) / w
        padded = np.pad(values, (w // 2, w - w // 2 - 1), mode="edge")
        return np.convolve(padded, kernel, mode="valid")

    # ------------------------------------------------------------------
    # Series loading / rendering
    # ------------------------------------------------------------------

    def _load_series(self):
        if not self.series_list:
            return

        sid, metric, timestamps, values = self.series_list[self.idx]
        self._sid = sid
        self._metric = metric
        self._timestamps = timestamps
        self._values = values
        self._selection = None

        self._refresh_status()
        self._render()

    def _render(self):
        sid, metric = self._sid, self._metric
        timestamps, values = self._timestamps, self._values
        n = len(timestamps)

        ax = self.ax
        ax.clear()

        xs = np.arange(n)
        ax.plot(xs, values, color="#bbbbbb", linewidth=0.8,
                marker="o", markersize=1.8, zorder=2, alpha=0.7)
        smoothed = self._smooth(values)
        ax.plot(xs, smoothed, color="#222222", linewidth=1.8, zorder=3)
        ax.set_xlim(-0.5, n - 0.5)

        # Highlight already-labeled windows
        for wk, label in self.label_db.get(sid, {}).get(metric, {}).items():
            try:
                i0, i1 = map(int, wk.split(":"))
            except ValueError:
                continue
            i1 = min(i1, n)
            if i0 >= i1:
                continue
            color = LABEL_COLOR.get(label, "#888888")
            ax.axvspan(i0 - 0.5, i1 - 0.5, alpha=0.30, color=color, zorder=1)

        def _fmt(x, _pos):
            i = int(round(x))
            return timestamps[i].strftime("%m-%d\n%H:%M") if 0 <= i < n else ""

        from matplotlib.ticker import FuncFormatter
        ax.xaxis.set_major_formatter(FuncFormatter(_fmt))
        ax.tick_params(axis="x", labelsize=8)
        ax.tick_params(axis="y", labelsize=8)
        ax.set_ylabel(metric, fontsize=9)
        ax.grid(True, alpha=0.25, linestyle="--")
        ax.set_title(f"{sid}  ·  {metric}", fontsize=10, pad=6)

        self._preview_patch = None  # cleared by ax.clear() above
        self.canvas.draw()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cursor(self) -> int:
        """Index where the next window should start: end of the rightmost labeled window."""
        end = 0
        for wk in self.label_db.get(self._sid, {}).get(self._metric, {}):
            try:
                _, a1 = map(int, wk.split(":"))
                end = max(end, a1)
            except ValueError:
                continue
        return end

    def _labeled_at(self, i: int) -> tuple[str, int, int] | None:
        """Return (label, a0, a1) of the window containing index i, or None."""
        for wk, label in self.label_db.get(self._sid, {}).get(self._metric, {}).items():
            try:
                a0, a1 = map(int, wk.split(":"))
            except ValueError:
                continue
            if a0 <= i < a1:
                return label, a0, a1
        return None

    def _clear_preview(self):
        if self._preview_patch is not None:
            self._preview_patch.remove()
            self._preview_patch = None

    # ------------------------------------------------------------------
    # Click handling
    # ------------------------------------------------------------------

    def _on_click(self, event):
        if event.inaxes is not self.ax or event.xdata is None:
            return

        if event.button == 3:
            # Right-click: delete the window under the cursor
            hit = self._labeled_at(int(round(event.xdata)))
            if hit is None:
                self._hint_var.set("No labeled window here — right-click a colored span to delete it")
                return
            label, a0, a1 = hit
            del self.label_db[self._sid][self._metric][f"{a0}:{a1}"]
            self.save_fn()
            self._selection = None
            self._render()
            self._refresh_status()
            self._hint_var.set(f"Deleted '{label}' window [{a0} : {a1}].")

        elif event.button == 1:
            # Left-click: extend a new window from the cursor to the clicked point
            n = len(self._timestamps)
            i1 = min(n, int(round(event.xdata)) + 1)
            i0 = self._cursor()

            if i1 <= i0:
                self._hint_var.set("Click to the right of the last labeled window")
                return

            self._clear_preview()
            self._preview_patch = self.ax.axvspan(
                i0 - 0.5, i1 - 0.5,
                alpha=0.45, color="#FFF176", edgecolor="#F9A825",
                linewidth=1.5, zorder=2,
            )
            self.canvas.draw()

            self._selection = (i0, i1)
            t0 = self._timestamps[i0].strftime("%m-%d %H:%M")
            t1 = self._timestamps[i1 - 1].strftime("%m-%d %H:%M")
            self._hint_var.set(
                f"Selected  [{i0} : {i1}]  ({t0} → {t1})  ·  press 1–7 or click a label button"
            )

    # ------------------------------------------------------------------
    # Labeling
    # ------------------------------------------------------------------

    def _apply_label(self, label_name: str):
        if self._selection is None:
            self._hint_var.set("No selection yet — click on the plot first")
            return

        i0, i1 = self._selection
        sid, metric = self._sid, self._metric

        self.label_db.setdefault(sid, {}).setdefault(metric, {})[f"{i0}:{i1}"] = label_name
        self.save_fn()

        self._clear_preview()
        self.ax.axvspan(i0 - 0.5, i1 - 0.5, alpha=0.30,
                        color=LABEL_COLOR[label_name], zorder=1)
        self.canvas.draw()

        self._selection = None
        self._refresh_status()
        self._hint_var.set(
            f"Labeled as '{label_name}'.  Click further right to select the next window."
        )

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _next(self):
        if self.idx < len(self.series_list) - 1:
            self.idx += 1
            self._load_series()

    def _prev(self):
        if self.idx > 0:
            self.idx -= 1
            self._load_series()

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _refresh_status(self):
        sid, metric = self._sid, self._metric
        total = len(self.series_list)
        n_labeled = len(self.label_db.get(sid, {}).get(metric, {}))
        self._progress_var.set(
            f"Series {self.idx + 1} / {total}  ·  {sid}  ·  {metric}"
            f"  ·  {n_labeled} windows labeled"
        )
        self._hint_var.set(
            "Click to set window end · press 1–7 or click a button to label · right-click a span to delete"
        )

    # ------------------------------------------------------------------
    # Quit
    # ------------------------------------------------------------------

    def _quit(self):
        self.save_fn()
        self.root.quit()
        self.root.destroy()
