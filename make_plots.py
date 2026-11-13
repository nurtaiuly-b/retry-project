"""Make the figures for the report from results/*.  Run after run_benchmarks.py and run_sweep.py.

    python make_plots.py
"""
import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from retrysim import POLICIES, SCENARIOS, make_policy

OUT = "results/figures"
os.makedirs(OUT, exist_ok=True)

# fixed colour order (validated categorical palette); no-retry is a neutral grey reference
COLORS = {
    "retryguard": "#2a78d6",
    "backoff": "#eb6834",
    "jitter": "#1baf7a",
    "retry_budget": "#eda100",
    "circuit_breaker": "#e87ba4",
    "no_retry": "#6b6a66",
}
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e3e2de", "#fcfcfb"
LABEL = {p: make_policy(p).label for p in POLICIES}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
    "axes.titlesize": 11, "axes.titleweight": "semibold", "axes.titlelocation": "left",
})


def load_summary():
    d = {}
    for r in csv.DictReader(open("results/summary.csv")):
        d[(r["scenario"], r["policy"])] = {k: float(v) for k, v in r.items() if k not in ("scenario", "policy")}
    return d


def legend(fig, handles_labels, ncol=6, y=1.0):
    h, l = handles_labels
    fig.legend(h, l, loc="upper center", ncol=ncol, frameon=False, bbox_to_anchor=(0.5, y), handlelength=1.6, columnspacing=1.6)


# ---------------------------------------------------------------- 1. time series
def fig_timeseries():
    ts = np.load("results/timeseries.npz")
    scns = ["heavy", "burst"]
    rows = [("retries_per_s", "Retry attempts sent to B (per second)"), ("capacity", "Capacity of B (req/s)")]
    fig, axes = plt.subplots(2, 2, figsize=(11, 6.4), sharex=True)
    X = np.arange(300)
    for c, scn in enumerate(scns):
        for r, (key, ylabel) in enumerate(rows):
            ax = axes[r, c]
            for pol in POLICIES:
                y = ts[f"{scn}|{pol}|{key}"][:300]
                ax.plot(X, y, color=COLORS[pol], lw=2, ls="--" if pol == "no_retry" else "-", label=LABEL[pol],
                        zorder=10 if pol == "retryguard" else 3)
            if r == 0:
                ax.set_title(SCENARIOS[scn].description.split(":")[0] + f"  ({scn})")
            if c == 0:
                ax.set_ylabel(ylabel)
            if r == 1:
                ax.set_xlabel("time (s)")
            ax.set_ylim(bottom=0)
    legend(fig, axes[0, 0].get_legend_handles_labels())
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(f"{OUT}/fig_timeseries.png", dpi=160)
    plt.close(fig)


# ---------------------------------------------------------------- 2. bar charts
def fig_bars(S):
    metrics = [
        ("retries_per_request", "Retries per request", "{:.2f}"),
        ("avg_latency_event_s", "Avg latency during overload (s)", "{:.2f}"),
        ("peak_capacity", "Peak capacity of B (req/s) - cost", "{:.0f}"),
        ("failure_rate", "Failed requests (fraction)", "{:.2f}"),
    ]
    scns = list(SCENARIOS)
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7))
    w = 0.13
    x = np.arange(len(scns))
    for ax, (key, title, _) in zip(axes.ravel(), metrics):
        for i, pol in enumerate(POLICIES):
            m = [S[(s, pol)][key + "_mean"] for s in scns]
            e = [S[(s, pol)][key + "_std"] for s in scns]
            ax.bar(x + (i - 2.5) * w, m, w * 0.85, yerr=e, color=COLORS[pol], label=LABEL[pol],
                   error_kw=dict(ecolor=INK2, lw=0.8, capsize=2))
        ax.set_xticks(x)
        ax.set_xticklabels(scns)
        ax.set_title(title)
        ax.grid(axis="x", visible=False)
    legend(fig, axes[0, 0].get_legend_handles_labels())
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(f"{OUT}/fig_benchmarks.png", dpi=160)
    plt.close(fig)


# ---------------------------------------------------------------- 3. RetryGuard parameter sweep
def fig_sweep(S):
    rows = list(csv.DictReader(open("results/sweep.csv")))
    cols = {0.1: "#8bb8ee", 0.2: "#2a78d6", 0.4: "#0b3f85"}
    marks = {0.1: "o", 0.2: "s", 0.4: "^"}
    panels = [("retries_per_request", "Retries per request"), ("peak_capacity", "Peak capacity of B (req/s)")]
    scns = ["mild", "heavy", "burst"]
    fig, axes = plt.subplots(2, 3, figsize=(14, 6.4), sharex=True)
    for r, (key, ylabel) in enumerate(panels):
        for c, scn in enumerate(scns):
            ax = axes[r, c]
            for thr, col in cols.items():
                pts = sorted((float(q["interval_s"]), float(q[key + "_mean"]), float(q[key + "_std"]))
                             for q in rows if q["scenario"] == scn and float(q["threshold"]) == thr)
                xs, ys, es = zip(*pts)
                ax.errorbar(xs, ys, es, color=col, lw=2, marker=marks[thr], ms=5, capsize=2, label=f"RetryGuard, threshold {int(thr*100)}%")
            for pol, ls in (("backoff", "-"), ("no_retry", "--")):
                ax.axhline(S[(scn, pol)][key + "_mean"], color=COLORS[pol], lw=1.5, ls=ls, label=LABEL[pol] + " (reference)")
            if r == 0:
                ax.set_title(f"{scn}")
            if c == 0:
                ax.set_ylabel(ylabel)
            if r == 1:
                ax.set_xlabel("RetryGuard detection interval (s)")
            ax.set_ylim(bottom=0)
    legend(fig, axes[0, 0].get_legend_handles_labels(), ncol=5)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(f"{OUT}/fig_retryguard_sweep.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    S = load_summary()
    fig_timeseries()
    fig_bars(S)
    if os.path.exists("results/sweep.csv"):
        fig_sweep(S)
    print("figures saved in", OUT)
