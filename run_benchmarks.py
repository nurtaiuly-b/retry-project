"""Run every policy on every scenario with many random seeds.

    python run_benchmarks.py --seeds 20

Outputs (in results/):
    raw.csv          one row per (scenario, policy, seed)
    summary.csv      mean and std over seeds
    summary.md       tables you can paste into your report
    timeseries.npz   per-second curves, averaged over seeds (for the plots)
"""
import argparse
import csv
import os
from multiprocessing import Pool

import numpy as np

from retrysim import POLICIES, SCENARIOS, SimConfig, make_policy, run

METRICS = [
    ("retries_per_request", "Retries / request"),
    ("avg_latency_event_s", "Latency during overload (s)"),
    ("avg_latency_s", "Latency, whole run (s)"),
    ("failure_rate", "Failed requests (fraction)"),
    ("peak_capacity", "Peak capacity of B (req/s)"),
    ("capacity_seconds", "B capacity-seconds (cost proxy)"),
    ("wait_seconds_billed", "A wait-seconds (cost proxy)"),
    ("total_attempts", "Total attempts sent to B"),
]


def one(args):
    scn, pol, seed = args
    m, ts = run(SCENARIOS[scn], make_policy(pol), seed, SimConfig())
    return scn, pol, seed, m, ts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    jobs = [(s, p, seed) for s in SCENARIOS for p in POLICIES for seed in range(a.seeds)]
    with Pool() as pool:
        res = pool.map(one, jobs, chunksize=8)

    # raw
    keys = list(res[0][3].keys())
    with open(f"{a.out}/raw.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "policy", "seed"] + keys)
        for scn, pol, seed, m, _ in res:
            w.writerow([scn, pol, seed] + [m[k] for k in keys])

    # summary
    summ = {}
    for scn in SCENARIOS:
        for pol in POLICIES:
            rows = [m for s, p, _, m, _ in res if s == scn and p == pol]
            summ[(scn, pol)] = {k: (float(np.mean([r[k] for r in rows])), float(np.std([r[k] for r in rows]))) for k in keys}
    with open(f"{a.out}/summary.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "policy"] + [f"{k}_{x}" for k in keys for x in ("mean", "std")])
        for (scn, pol), d in summ.items():
            w.writerow([scn, pol] + [v for k in keys for v in d[k]])

    with open(f"{a.out}/summary.md", "w") as f:
        f.write(f"# Benchmark summary ({a.seeds} seeds per cell, mean ± std)\n\n")
        for scn, S in SCENARIOS.items():
            f.write(f"## {scn}\n{S.description}\n\n")
            f.write("| Policy | " + " | ".join(lbl for _, lbl in METRICS[:6]) + " |\n")
            f.write("|---|" + "---|" * 6 + "\n")
            for pol in POLICIES:
                d = summ[(scn, pol)]
                cells = []
                for k, _ in METRICS[:6]:
                    mu, sd = d[k]
                    cells.append(f"{mu:,.0f} ± {sd:,.0f}" if mu >= 1000 else f"{mu:.3g} ± {sd:.2g}")
                f.write(f"| {make_policy(pol).label} | " + " | ".join(cells) + " |\n")
            f.write("\n")

    # time series (mean over seeds)
    out = {}
    for scn in SCENARIOS:
        for pol in POLICIES:
            sers = [ts for s, p, _, _, ts in res if s == scn and p == pol]
            for k in sers[0]:
                out[f"{scn}|{pol}|{k}"] = np.mean([x[k] for x in sers], axis=0)
    np.savez(f"{a.out}/timeseries.npz", **out)
    print(f"done: {len(res)} runs -> {a.out}/")


if __name__ == "__main__":
    main()
