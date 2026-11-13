"""How sensitive is RetryGuard to its two parameters (threshold, interval)?

    python run_sweep.py --seeds 10      ->  results/sweep.csv
"""
import argparse
import csv
from multiprocessing import Pool

import numpy as np

from retrysim import SCENARIOS, SimConfig, make_policy, run

THRESHOLDS = [0.1, 0.2, 0.4]
INTERVALS = [2, 5, 10, 20, 30]
KEYS = ["retries_per_request", "avg_latency_event_s", "failure_rate", "peak_capacity", "capacity_seconds"]


def one(args):
    scn, thr, itv, seed = args
    m, _ = run(SCENARIOS[scn], make_policy("retryguard", threshold=thr, interval_s=itv), seed, SimConfig())
    return args, m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=10)
    a = ap.parse_args()
    jobs = [(s, t, i, seed) for s in SCENARIOS for t in THRESHOLDS for i in INTERVALS for seed in range(a.seeds)]
    with Pool() as pool:
        res = pool.map(one, jobs, chunksize=8)
    with open("results/sweep.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "threshold", "interval_s"] + [f"{k}_{x}" for k in KEYS for x in ("mean", "std")])
        for scn in SCENARIOS:
            for t in THRESHOLDS:
                for i in INTERVALS:
                    rows = [m for (s, tt, ii, _), m in res if (s, tt, ii) == (scn, t, i)]
                    w.writerow([scn, t, i] + [v for k in KEYS for v in (np.mean([r[k] for r in rows]), np.std([r[k] for r in rows]))])
    print("done -> results/sweep.csv")


if __name__ == "__main__":
    main()
